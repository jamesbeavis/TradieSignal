-- =====================================================================
-- Tradiesignal :: row level security
-- =====================================================================
-- Threat model: the anon key ships in the browser. Assume any authenticated
-- user will try to read every row in the database, and that a Starter
-- subscriber will try to read Premium data. Policy, not application code, is
-- what stops them.
--
-- Entitlement lives in one place — has_entitlement() — so a pricing change is
-- a data change, not a policy rewrite.
-- =====================================================================

alter table profiles           enable row level security;
alter table subscriptions      enable row level security;
alter table saved_searches     enable row level security;
alter table notifications      enable row level security;
alter table email_logs         enable row level security;
alter table project_deliveries enable row level security;
alter table projects           enable row level security;
alter table applications       enable row level security;
alter table builders           enable row level security;
alter table opportunity_scores enable row level security;
alter table public_pipeline    enable row level security;
alter table councils           enable row level security;
alter table data_sources       enable row level security;
alter table plans              enable row level security;
alter table ingestion_runs     enable row level security;
alter table billing_events     enable row level security;


-- ---------------------------------------------------------------------
-- helpers
-- ---------------------------------------------------------------------

-- The caller's live tier, or null if they have no paying/trialing sub.
create or replace function current_tier() returns plan_tier
language sql stable security definer set search_path = public as $$
  select s.tier
  from subscriptions s
  where s.profile_id = auth.uid()
    and s.status in ('active','trialing')
    and (s.current_period_end is null or s.current_period_end > now())
  order by array_position(
    array['premium','professional','starter','trial']::plan_tier[], s.tier)
  limit 1
$$;

create or replace function has_entitlement(feature text) returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    case feature
      when 'builders' then p.includes_builders
      when 'tenders'  then p.includes_tenders
      when 'export'   then p.includes_export
      when 'daily'    then p.daily_alerts
      else false
    end, false)
  from plans p
  where p.tier = current_tier()
$$;

-- Council entitlement: Starter is limited to the councils on their profile;
-- higher tiers see every active council.
create or replace function may_see_council(cid smallint) returns boolean
language sql stable security definer set search_path = public as $$
  select case
    when current_tier() is null then false
    when (select max_councils from plans where tier = current_tier()) is null then true
    else cid = any(
      select unnest(councils) from profiles where id = auth.uid()
    )
  end
$$;

create or replace function is_subscriber() returns boolean
language sql stable security definer set search_path = public as $$
  select current_tier() is not null
$$;

create or replace function is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin', false)
$$;


-- ---------------------------------------------------------------------
-- own-row tables
-- ---------------------------------------------------------------------

create policy profiles_self_read   on profiles for select using (id = auth.uid() or is_admin());
create policy profiles_self_write  on profiles for update using (id = auth.uid())
                                                   with check (id = auth.uid());
create policy profiles_self_insert on profiles for insert with check (id = auth.uid());

-- Subscriptions are written only by the Stripe webhook (service role), never
-- by the client. A client that can write its own tier is a client that can
-- grant itself Premium.
create policy subs_self_read on subscriptions for select
  using (profile_id = auth.uid() or is_admin());

create policy saved_self_all on saved_searches for all
  using (profile_id = auth.uid()) with check (profile_id = auth.uid());

create policy notif_self_read   on notifications for select using (profile_id = auth.uid());
create policy notif_self_update on notifications for update using (profile_id = auth.uid())
                                                        with check (profile_id = auth.uid());

create policy email_self_read on email_logs for select
  using (profile_id = auth.uid() or is_admin());

create policy deliveries_self_read on project_deliveries for select
  using (profile_id = auth.uid());


-- ---------------------------------------------------------------------
-- the product data
-- ---------------------------------------------------------------------
-- Projects are readable by any live subscriber, limited to the councils their
-- plan covers. Anonymous visitors get a small teaser set for the landing page.

create policy projects_subscriber_read on projects for select
  using (is_subscriber() and may_see_council(council_id));

-- Teaser: the marketing site shows a handful of high scorers to anonymous
-- visitors. Deliberately narrow — enough to prove the product is real, not
-- enough to be the product.
create policy projects_public_teaser on projects for select
  to anon
  using (opportunity_score >= 90 and date_last_activity > current_date - 21);

create policy projects_admin_all on projects for all
  using (is_admin()) with check (is_admin());

create policy applications_read on applications for select
  using (
    is_admin() or exists (
      select 1 from projects p
      where p.id = applications.project_id
        and is_subscriber() and may_see_council(p.council_id)
    )
  );

create policy scores_read on opportunity_scores for select
  using (
    is_admin() or exists (
      select 1 from projects p
      where p.id = opportunity_scores.project_id
        and is_subscriber() and may_see_council(p.council_id)
    )
  );

-- The builder watchlist is a paid feature, gated on the plan flag rather than
-- hidden in the UI.
create policy builders_read on builders for select
  using (is_admin() or (is_subscriber() and has_entitlement('builders')));

create policy pipeline_read on public_pipeline for select
  using (is_admin() or (is_subscriber() and has_entitlement('tenders')));


-- ---------------------------------------------------------------------
-- reference data: readable by anyone, written by service role only
-- ---------------------------------------------------------------------

create policy councils_read on councils   for select using (true);
create policy plans_read    on plans      for select using (true);
create policy sources_read  on data_sources for select using (is_admin());
create policy runs_read     on ingestion_runs for select using (is_admin());
create policy billing_read  on billing_events for select using (is_admin());

-- Note: no INSERT/UPDATE/DELETE policies are defined for projects,
-- applications, builders, councils, data_sources, ingestion_runs,
-- public_pipeline or billing_events. With RLS enabled and no permissive
-- policy, those writes are denied to anon and authenticated. Only the service
-- role — which bypasses RLS and is used exclusively by Edge Functions — can
-- write them. That is the intended design; do not "fix" it by adding policies.


-- ---------------------------------------------------------------------
-- grants
-- ---------------------------------------------------------------------
-- Supabase creates these roles and grants table privileges by default. They
-- are restated here so the schema is self-contained on any Postgres, and so
-- the intent is explicit: RLS decides WHICH rows, grants decide WHETHER the
-- role may touch the table at all. Both are needed.

grant usage on schema public to anon, authenticated, service_role;

grant select on projects, applications, opportunity_scores, builders,
                councils, plans, public_pipeline
  to anon, authenticated;

grant select, insert, update, delete on profiles, saved_searches, notifications
  to authenticated;
grant select on subscriptions, email_logs, project_deliveries to authenticated;

-- The pipeline. service_role bypasses RLS; it still needs table privileges.
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;

-- Function grants live at the end of 003_functions.sql, where the functions
-- they refer to already exist.
