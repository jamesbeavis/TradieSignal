-- =====================================================================
-- Tradiesignal :: search, matching and digest selection
-- =====================================================================
-- These are the three queries the product actually runs. They live in the
-- database because they need PostGIS distance and because the weekly email
-- job must not be able to drift from what the dashboard shows.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Address normalisation and project linking
-- ---------------------------------------------------------------------
-- The NSW feeds give no cross-service project id, so a normalised address is
-- the join key. Keep this deterministic: changing it re-partitions history.

create or replace function normalise_address(addr text) returns text
language sql immutable as $$
  select upper(regexp_replace(coalesce(addr,''), '[^A-Za-z0-9]', '', 'g'))
$$;

create or replace function normalise_company(name text) returns text
language sql immutable as $$
  select trim(regexp_replace(
    upper(coalesce(name,'')),
    '\y(PTY|LTD|LIMITED|PROPRIETARY|THE|TRUSTEE|FOR|GROUP|NSW|AUSTRALIA)\y|[^A-Z0-9 ]',
    ' ', 'g'))
$$;
comment on function normalise_company is
  'Collapses "GWH BUILD PTY LTD" and "GWH Build Pty Limited" onto one builder record.';

-- Find or create the project a freshly ingested application belongs to.
create or replace function link_project(
  p_council_id smallint,
  p_address    text,
  p_lot_ref    text
) returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_norm text := normalise_address(p_address);
  v_id   uuid;
begin
  if length(v_norm) > 8 then
    select id into v_id from projects
     where address_normalised = v_norm and council_id = p_council_id
     limit 1;
  end if;

  if v_id is null and p_lot_ref is not null and p_lot_ref <> '' then
    select id into v_id from projects
     where lot_ref = p_lot_ref and council_id = p_council_id
     limit 1;
  end if;

  return v_id;  -- null means the caller inserts a new project
end $$;


-- Signatures change as the product grows, and CREATE OR REPLACE creates a new
-- overload rather than replacing one when a parameter type differs. Drop first
-- so the migration is re-runnable and only ever one signature exists.
drop function if exists search_projects(uuid, filter_group[], smallint[], project_stage[],
  smallint, numeric, numeric, geography, date, text, text, integer, integer);
drop function if exists search_projects(uuid, filter_group[], smallint[], project_stage[],
  integer, numeric, numeric, geography, date, text, text, integer, integer);
drop function if exists digest_for_profile(uuid, date, integer);
drop function if exists refresh_builders();
drop function if exists source_health();

-- ---------------------------------------------------------------------
-- 2. The dashboard query
-- ---------------------------------------------------------------------
-- One function serves the dashboard, the API and the digest so all three can
-- never disagree about what a filter means.

create or replace function search_projects(
  p_profile_id  uuid    default null,
  p_groups      filter_group[] default null,
  p_councils    smallint[] default null,
  p_stages      project_stage[] default null,
  p_min_score   integer  default 0,
  p_min_cost    numeric  default null,
  p_radius_km   numeric  default null,
  p_origin      geography default null,
  p_since       date     default null,
  p_query       text     default null,
  p_sort        text     default 'score',
  p_limit       integer  default 50,
  p_offset      integer  default 0
)
returns table (
  id uuid, public_ref text, name text, address text, suburb text,
  council text, filter_group filter_group, category project_category,
  stage project_stage, stage_label text, cost_declared numeric,
  cost_confidence cost_confidence, opportunity_score smallint,
  priority priority_tier, electrical_low numeric, electrical_high numeric,
  builder_name text, dwellings_new integer, date_last_activity date,
  distance_km numeric, total_count bigint
)
language sql stable security definer set search_path = public as $$
  with origin as (
    select coalesce(
      p_origin,
      (select base_geom from profiles where id = p_profile_id)
    ) as g
  ),
  filtered as (
    select p.*, c.short_name as council_short,
           case when o.g is null or p.geom is null then null
                else round((st_distance(p.geom, o.g) / 1000)::numeric, 1) end as dist_km
    from projects p
    join councils c on c.id = p.council_id
    cross join origin o
    where p.stage <> 'withdrawn'
      and p.opportunity_score >= coalesce(p_min_score, 0)::smallint
      and (p_groups   is null or p.filter_group = any(p_groups))
      and (p_councils is null or p.council_id   = any(p_councils))
      and (p_stages   is null or p.stage        = any(p_stages))
      and (p_min_cost is null or p.cost_declared >= p_min_cost)
      and (p_since    is null or p.date_last_activity >= p_since)
      and (p_query    is null or p.search_tsv @@ plainto_tsquery('english', p_query))
      and (
        p_radius_km is null or o.g is null or p.geom is null
        or st_dwithin(p.geom, o.g, p_radius_km * 1000)
      )
  ),
  counted as (select count(*) as n from filtered)
  select f.id, f.public_ref, f.name, f.address, f.suburb,
         f.council_short, f.filter_group, f.category,
         f.stage, f.stage_label, f.cost_declared, f.cost_confidence,
         f.opportunity_score, f.priority, f.electrical_low, f.electrical_high,
         f.builder_name, f.dwellings_new, f.date_last_activity,
         f.dist_km, counted.n
  from filtered f cross join counted
  order by
    case when p_sort = 'score'    then f.opportunity_score end desc nulls last,
    case when p_sort = 'value'    then f.cost_declared end desc nulls last,
    case when p_sort = 'new'      then f.date_last_activity end desc nulls last,
    case when p_sort = 'distance' then f.dist_km end asc nulls last,
    f.opportunity_score desc
  limit greatest(1, least(p_limit, 500))
  offset greatest(0, p_offset)
$$;


-- ---------------------------------------------------------------------
-- 3. Digest selection
-- ---------------------------------------------------------------------
-- Picks the projects for one subscriber's weekly email, honouring their
-- filters, their plan's council entitlement, and — critically — the
-- suppression list, so the same project is not emailed twice unless its stage
-- has actually advanced.

create or replace function digest_for_profile(
  p_profile_id uuid,
  p_since      date default (current_date - 7),
  p_limit      integer default 20
)
returns table (
  id uuid, public_ref text, name text, address text, council text,
  filter_group filter_group, stage project_stage, stage_label text,
  cost_declared numeric, cost_confidence cost_confidence,
  opportunity_score smallint, priority priority_tier,
  electrical_low numeric, electrical_high numeric,
  builder_name text, contact_window text, contact_angle text,
  distance_km numeric, reason text
)
language sql stable security definer set search_path = public as $$
  with me as (
    select pr.*,
           (select max_councils from plans pl
             join subscriptions s on s.tier = pl.tier
            where s.profile_id = pr.id and s.status in ('active','trialing')
            limit 1) as max_councils
    from profiles pr where pr.id = p_profile_id
  )
  select p.id, p.public_ref, p.name, p.address, c.short_name,
         p.filter_group, p.stage, p.stage_label,
         p.cost_declared, p.cost_confidence,
         p.opportunity_score, p.priority,
         p.electrical_low, p.electrical_high,
         p.builder_name, p.contact_window, p.contact_angle,
         case when me.base_geom is null or p.geom is null then null
              else round((st_distance(p.geom, me.base_geom)/1000)::numeric, 1) end,
         -- The "why is this in your email" line. Never send an unexplained row.
         case
           when p.stage = 'cc_determined' and p.builder_name is not null
             then 'Construction certificate issued and the builder is named'
           when p.stage in ('cc_determined','cc_lodged')
             then 'Construction certificate stage — trades are being appointed now'
           when p.category = 'energy'
             then 'Energy project — electrical work is the bulk of the job'
           when p.cost_declared >= 5000000
             then 'Large project in your area'
           when p.dwellings_new >= 10
             then p.dwellings_new || ' dwellings — repeatable, schedulable work'
           when p.priority = 'high'
             then 'Scored ' || p.opportunity_score || ' out of 100'
           else 'Matches your saved filters'
         end
  from projects p
  join councils c on c.id = p.council_id
  cross join me
  where p.stage <> 'withdrawn'
    and p.date_last_activity >= p_since
    and p.opportunity_score >= me.min_score
    and (cardinality(me.sectors)  = 0 or p.filter_group = any(me.sectors))
    and (
      me.max_councils is null
      or cardinality(me.councils) = 0
      or p.council_id = any(me.councils)
    )
    and (
      me.base_geom is null or p.geom is null
      or st_dwithin(p.geom, me.base_geom, me.radius_km * 1000)
    )
    -- Suppression: skip anything already sent, unless the stage advanced.
    and not exists (
      select 1 from project_deliveries d
      where d.profile_id = p_profile_id
        and d.project_id = p.id
        and d.last_stage = p.stage
    )
  order by p.opportunity_score desc, p.cost_declared desc nulls last
  limit greatest(1, least(p_limit, 60))
$$;


-- ---------------------------------------------------------------------
-- 4. Builder roll-up
-- ---------------------------------------------------------------------
-- Run after each ingestion so the watchlist reflects the day's certificates.

create or replace function refresh_builders() returns integer
language plpgsql security definer set search_path = public as $$
declare
  n integer;
begin
  insert into builders (name, name_normalised)
  select distinct on (normalise_company(p.builder_name))
         p.builder_name, normalise_company(p.builder_name)
  from projects p
  where p.builder_name is not null
    and normalise_company(p.builder_name) <> ''
  on conflict (name_normalised) do nothing;

  update projects p
     set builder_id = b.id,
         builder_normalised = b.name_normalised
    from builders b
   where b.name_normalised = normalise_company(p.builder_name)
     and p.builder_name is not null
     and (p.builder_id is distinct from b.id);

  with roll as (
    select p.builder_id,
           count(*) as n,
           coalesce(sum(p.cost_declared) filter (
             where p.cost_confidence in ('high','medium','low')), 0) as v,
           array_agg(distinct c.short_name) as lgas,
           max(p.date_last_activity) as seen
    from projects p
    join councils c on c.id = p.council_id
    where p.builder_id is not null
    group by p.builder_id
  )
  update builders b
     set project_count = roll.n,
         tracked_value = roll.v,
         councils      = roll.lgas,
         last_seen_at  = coalesce(roll.seen::timestamptz, b.last_seen_at)
    from roll where roll.builder_id = b.id;

  get diagnostics n = row_count;
  return n;
end $$;


-- ---------------------------------------------------------------------
-- 5. Health check — the query that pages someone
-- ---------------------------------------------------------------------
-- A silently stale feed is worse than a loud failure: the product keeps
-- sending emails that look fine and contain nothing new.

create or replace function source_health()
returns table (key text, name text, last_success_at timestamptz,
               hours_stale numeric, consecutive_failures int, alert boolean)
language sql stable security definer set search_path = public as $$
  select s.key, s.name, s.last_success_at,
         round(extract(epoch from (now() - s.last_success_at))/3600, 1),
         s.consecutive_failures,
         (s.consecutive_failures >= 3
          or s.last_success_at is null
          or s.last_success_at < now() - interval '36 hours')
  from data_sources s
  where s.is_active
  order by 4 desc nulls first
$$;


-- ---------------------------------------------------------------------
-- 6. Function grants
-- ---------------------------------------------------------------------
-- These sit here, not in 002, because a grant cannot name a function that
-- does not exist yet and the files run in numeric order.

grant execute on function search_projects(uuid, filter_group[], smallint[],
  project_stage[], integer, numeric, numeric, geography, date, text, text,
  integer, integer) to anon, authenticated, service_role;
grant execute on function digest_for_profile(uuid, date, integer) to service_role;
grant execute on function refresh_builders() to service_role;
grant execute on function source_health() to service_role, authenticated;
grant execute on function normalise_address(text) to service_role;
grant execute on function normalise_company(text) to service_role;
grant execute on function link_project(smallint, text, text) to service_role;
