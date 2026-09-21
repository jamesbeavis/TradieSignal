-- =====================================================================
-- Tradiesignal :: Supabase / PostgreSQL schema
-- =====================================================================
-- Run in order against a fresh Supabase project:
--   001_schema.sql   this file  — extensions, enums, tables, indexes
--   002_rls.sql                 — row level security policies
--   003_functions.sql           — scoring, search and email selection
--   004_seed.sql                — councils, data sources, plans
--
-- Design notes
-- ------------
-- * The unit the customer cares about is a PROJECT (a physical site), not an
--   application. One project accumulates many APPLICATIONS as it moves DA ->
--   CDC -> CC. projects.* holds the merged view; applications.* holds the
--   evidence. Never delete an application; supersede it.
-- * Every ingested row keeps its raw payload so a scoring change can be
--   replayed over history without re-fetching from the source.
-- * Scores are materialised on projects for fast filtering, and also versioned
--   in opportunity_scores so we can prove why something scored what it did on
--   the day we emailed it.
-- * Money is numeric(14,2). Never float.
-- =====================================================================

create extension if not exists "uuid-ossp";
create extension if not exists postgis;
create extension if not exists pg_trgm;      -- fuzzy search on builder/address
create extension if not exists pg_cron;      -- scheduled ingestion

-- ---------------------------------------------------------------------
-- enums
-- ---------------------------------------------------------------------

create type plan_tier        as enum ('trial','starter','professional','premium');
create type sub_status       as enum ('trialing','active','past_due','canceled','paused');
create type project_category as enum (
  'energy','infrastructure','healthcare','education','industrial','retail',
  'commercial','subdivision','residential_new','residential_reno','low_value','other'
);
create type filter_group     as enum (
  'Residential','Commercial','Industrial','Government','Infrastructure'
);
create type project_stage    as enum (
  'da_lodged','da_assessment','da_exhibition','da_info','da_determined',
  'cdc_lodged','cdc_approved','cc_lodged','cc_determined','withdrawn'
);
create type cost_confidence  as enum ('high','medium','low','suspect','unverified','unknown');
create type priority_tier    as enum ('high','medium','watch','low');
create type source_kind      as enum ('eplanning_api','tender_api','scrape','rss','manual','csv');
create type run_status       as enum ('running','success','partial','failed');
create type email_kind       as enum ('weekly_digest','daily_alert','saved_search','onboarding','billing');
create type email_state      as enum ('queued','sent','delivered','opened','clicked','bounced','complained','failed');


-- =====================================================================
-- 1. Reference data
-- =====================================================================

create table councils (
  id               smallserial primary key,
  name             text not null unique,           -- exactly as the NSW API spells it
  short_name       text not null,
  slug             text not null unique,
  state            text not null default 'NSW',
  region           text not null default 'Hunter',
  centroid         geography(point,4326) not null,
  da_tracker_url   text,
  is_active        boolean not null default true,  -- false = tracked but not sold yet
  created_at       timestamptz not null default now()
);
comment on table councils is
  'Local government areas we ingest. name must match the ePlanning API council list exactly.';

create table data_sources (
  id               smallserial primary key,
  key              text not null unique,           -- 'eplanning_da', 'buynsw_tenders', ...
  name             text not null,
  kind             source_kind not null,
  endpoint         text,
  licence          text,
  attribution      text,
  docs_url         text,
  refresh_cron     text,                           -- cron expression for the collector
  is_active        boolean not null default true,
  last_success_at  timestamptz,
  consecutive_failures int not null default 0,
  notes            text,
  created_at       timestamptz not null default now()
);
comment on column data_sources.consecutive_failures is
  'Alerting threshold. 3+ pages the operator; a silent stale feed is the worst failure mode.';

-- Scoring is configuration, not code. Changing a weight must not need a deploy,
-- and every score we ever sent must be explainable by the config of that day.
create table scoring_configs (
  id               serial primary key,
  version          text not null unique,           -- '2026.09.1'
  is_active        boolean not null default false,
  base_scores      jsonb not null,                 -- category -> base score
  stage_weights    jsonb not null,                 -- stage -> multiplier + weeks
  value_bands      jsonb not null,
  distance_bands   jsonb not null,
  signal_bonuses   jsonb not null,
  electrical_share jsonb not null,                 -- category -> [low, high]
  quality_rules    jsonb not null,
  notes            text,
  created_at       timestamptz not null default now(),
  activated_at     timestamptz
);
create unique index one_active_scoring_config
  on scoring_configs ((is_active)) where is_active;


-- =====================================================================
-- 2. Projects and their applications
-- =====================================================================

create table projects (
  id                    uuid primary key default uuid_generate_v4(),
  public_ref            text not null unique,       -- 'TS-NEWC-661569'
  slug                  text not null unique,

  name                  text not null,              -- derived; the feed has no name
  description           text,
  council_id            smallint not null references councils(id),

  address               text not null,
  address_normalised    text not null,              -- the linking key
  suburb                text,
  postcode              text,
  lot_ref               text,
  geom                  geography(point,4326),

  category              project_category not null,
  filter_group          filter_group not null,
  development_types     text[] not null default '{}',
  building_classes      text[] not null default '{}',

  stage                 project_stage not null,
  stage_label           text not null,
  status_raw            text,

  cost_declared         numeric(14,2),
  cost_confidence       cost_confidence not null default 'unknown',
  quality_flags         text[] not null default '{}',

  dwellings_new         integer,
  lots_proposed         integer,
  storeys               integer,
  gfa_proposed          numeric(12,2),
  gfa_existing          numeric(12,2),
  land_area             numeric(12,2),
  use_current           text,
  use_proposed          text,

  builder_name          text,
  builder_normalised    text,
  builder_id            uuid,                       -- fk added after builders table

  opportunity_score     smallint not null default 0,
  priority              priority_tier not null default 'low',
  electrical_low        numeric(14,2),
  electrical_high       numeric(14,2),
  electrical_scope      text[] not null default '{}',
  signals               text[] not null default '{}',

  contact_window        text,
  contact_target        text,
  contact_angle         text,

  date_submitted        date,
  date_lodged           date,
  date_determined       date,
  date_last_activity    date,                       -- drives "new this week"

  first_seen_at         timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  scoring_version       text,

  -- Maintained by the projects_tsv trigger below, not GENERATED: array_to_string
  -- is only STABLE, so Postgres rejects it in a generated expression.
  search_tsv            tsvector,

  constraint cost_non_negative check (cost_declared is null or cost_declared >= 0),
  constraint score_range check (opportunity_score between 0 and 100)
);

-- Query patterns, in order of how often the app runs them.
create index projects_score_idx      on projects (opportunity_score desc, cost_declared desc nulls last);
create index projects_activity_idx   on projects (date_last_activity desc nulls last);
create index projects_council_idx    on projects (council_id, opportunity_score desc);
create index projects_group_idx      on projects (filter_group, opportunity_score desc);
create index projects_stage_idx      on projects (stage);
create index projects_priority_idx   on projects (priority) where priority in ('high','medium');
create index projects_geom_idx       on projects using gist (geom);
create index projects_search_idx     on projects using gin (search_tsv);
create index projects_builder_trgm   on projects using gin (builder_normalised gin_trgm_ops);
create index projects_addr_norm_idx  on projects (address_normalised);
comment on column projects.address_normalised is
  'Upper-cased, punctuation-stripped address. The only cross-feed join key the NSW data gives us.';

create table applications (
  id                    uuid primary key default uuid_generate_v4(),
  project_id            uuid not null references projects(id) on delete cascade,
  data_source_id        smallint not null references data_sources(id),

  source_ref            text not null,              -- PAN-661569 / CDC-351460 / CFT-946476
  council_ref           text,                       -- DA2026/01800
  service               text not null,              -- OnlineDA | OnlineCDC | OnlineCC
  application_type      text,
  status_raw            text,
  stage                 project_stage not null,

  cost_declared         numeric(14,2),
  date_submitted        date,
  date_lodged           date,
  date_determined       date,
  exhibition_start      date,
  exhibition_end        date,
  determination_authority text,

  builder_legal_name    text,
  builder_trading_name  text,

  raw                   jsonb not null,             -- verbatim payload; replay-safe
  source_updated_at     timestamptz,
  ingested_at           timestamptz not null default now(),
  superseded_at         timestamptz,

  unique (data_source_id, source_ref)
);
create index applications_project_idx on applications (project_id, date_lodged desc);
create index applications_ref_idx     on applications (source_ref);
create index applications_raw_idx     on applications using gin (raw jsonb_path_ops);
comment on column applications.raw is
  'The untouched source record. Lets us re-derive every field after a parser fix without refetching.';

-- Score history: what we published, and why, on the day we published it.
create table opportunity_scores (
  id                uuid primary key default uuid_generate_v4(),
  project_id        uuid not null references projects(id) on delete cascade,
  scoring_version   text not null,
  score             smallint not null,
  priority          priority_tier not null,
  category_base     smallint not null,
  stage_multiplier  numeric(4,2) not null,
  value_multiplier  numeric(4,2) not null,
  distance_multiplier numeric(4,2) not null,
  signal_bonus      smallint not null,
  breakdown         jsonb not null,
  computed_at       timestamptz not null default now()
);
create index opp_scores_project_idx on opportunity_scores (project_id, computed_at desc);


-- =====================================================================
-- 3. Builders — the differentiating asset
-- =====================================================================
-- Construction certificates name the building company. Accumulating that over
-- time produces a picture of who actually builds in the Hunter that exists
-- nowhere else, and it is the single strongest reason to stay subscribed.

create table builders (
  id                uuid primary key default uuid_generate_v4(),
  name              text not null,
  name_normalised   text not null unique,
  abn               text,
  trading_names     text[] not null default '{}',
  first_seen_at     timestamptz not null default now(),
  last_seen_at      timestamptz not null default now(),
  project_count     integer not null default 0,
  tracked_value     numeric(16,2) not null default 0,
  councils          text[] not null default '{}',
  is_verified       boolean not null default false,  -- a human confirmed it is a builder
  notes             text
);
create index builders_trgm_idx on builders using gin (name_normalised gin_trgm_ops);
create index builders_value_idx on builders (tracked_value desc);

alter table projects
  add constraint projects_builder_fk
  foreign key (builder_id) references builders(id) on delete set null;
create index projects_builder_idx on projects (builder_id);


-- =====================================================================
-- 4. Customers, subscriptions, billing
-- =====================================================================

create table profiles (
  id                uuid primary key references auth.users(id) on delete cascade,
  email             text not null,
  full_name         text,
  business_name     text,
  phone             text,
  licence_number    text,                            -- NSW electrical licence, optional
  base_suburb       text,
  base_geom         geography(point,4326),
  radius_km         smallint not null default 50,
  councils          smallint[] not null default '{}', -- empty = all in plan
  sectors           filter_group[] not null default '{}',
  min_score         smallint not null default 55,
  digest_day        smallint not null default 1,      -- 1 = Monday
  digest_hour       smallint not null default 6,      -- local time
  timezone          text not null default 'Australia/Sydney',
  email_opt_in      boolean not null default true,
  onboarded_at      timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint radius_sane check (radius_km between 5 and 300),
  constraint score_sane  check (min_score between 0 and 100)
);
comment on column profiles.base_geom is
  'Radius filtering and the distance term in scoring are both relative to this point.';

create table plans (
  tier              plan_tier primary key,
  name              text not null,
  price_cents       integer not null,
  currency          text not null default 'AUD',
  stripe_price_id   text,
  max_councils      smallint,                        -- null = unlimited
  max_radius_km     smallint,
  max_seats         smallint not null default 1,
  includes_builders boolean not null default false,
  includes_tenders  boolean not null default false,
  includes_export   boolean not null default false,
  daily_alerts      boolean not null default false,
  seat_cap_per_lga  smallint                         -- scarcity: cap subs per council
);

create table subscriptions (
  id                     uuid primary key default uuid_generate_v4(),
  profile_id             uuid not null references profiles(id) on delete cascade,
  tier                   plan_tier not null references plans(tier),
  status                 sub_status not null default 'trialing',
  stripe_customer_id     text,
  stripe_subscription_id text unique,
  current_period_start   timestamptz,
  current_period_end     timestamptz,
  trial_ends_at          timestamptz,
  cancel_at_period_end   boolean not null default false,
  canceled_at            timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);
create index subs_profile_idx on subscriptions (profile_id);
create index subs_status_idx  on subscriptions (status) where status in ('active','trialing');

-- Raw Stripe events, so billing state can always be rebuilt from the source of truth.
create table billing_events (
  id                text primary key,                -- Stripe event id; natural idempotency
  type              text not null,
  payload           jsonb not null,
  processed_at      timestamptz,
  error             text,
  received_at       timestamptz not null default now()
);


-- =====================================================================
-- 5. Saved searches, notifications, email
-- =====================================================================

create table saved_searches (
  id            uuid primary key default uuid_generate_v4(),
  profile_id    uuid not null references profiles(id) on delete cascade,
  name          text not null,
  filters       jsonb not null,      -- {groups, councils, stages, min_score, radius_km, q}
  alert_enabled boolean not null default true,
  alert_frequency text not null default 'weekly',  -- weekly | daily | instant
  last_run_at   timestamptz,
  last_match_at timestamptz,
  created_at    timestamptz not null default now()
);
create index saved_searches_profile_idx on saved_searches (profile_id);

create table notifications (
  id              uuid primary key default uuid_generate_v4(),
  profile_id      uuid not null references profiles(id) on delete cascade,
  project_id      uuid references projects(id) on delete cascade,
  saved_search_id uuid references saved_searches(id) on delete set null,
  title           text not null,
  body            text,
  read_at         timestamptz,
  created_at      timestamptz not null default now()
);
create index notifications_unread_idx
  on notifications (profile_id, created_at desc) where read_at is null;

create table email_logs (
  id             uuid primary key default uuid_generate_v4(),
  profile_id     uuid references profiles(id) on delete set null,
  kind           email_kind not null,
  subject        text not null,
  provider_id    text,                 -- Resend message id
  state          email_state not null default 'queued',
  project_ids    uuid[] not null default '{}',
  project_count  smallint not null default 0,
  period_start   date,
  period_end     date,
  error          text,
  sent_at        timestamptz,
  updated_at     timestamptz not null default now(),
  created_at     timestamptz not null default now()
);
create index email_logs_profile_idx on email_logs (profile_id, created_at desc);
create index email_logs_state_idx   on email_logs (state) where state in ('queued','failed');
-- One digest per subscriber per period, enforced by the database rather than
-- by hoping the scheduler never double-fires.
create unique index email_logs_one_digest_per_period
  on email_logs (profile_id, kind, period_start)
  where kind = 'weekly_digest' and profile_id is not null;

-- Every project we have ever put in front of a given subscriber. Without this
-- the weekly email repeats itself and people unsubscribe.
create table project_deliveries (
  profile_id   uuid not null references profiles(id) on delete cascade,
  project_id   uuid not null references projects(id) on delete cascade,
  first_sent_at timestamptz not null default now(),
  send_count   smallint not null default 1,
  last_stage   project_stage not null,
  primary key (profile_id, project_id)
);
comment on table project_deliveries is
  'Suppression list. A project is re-sent only when its stage advances materially.';


-- =====================================================================
-- 6. Ingestion observability
-- =====================================================================

create table ingestion_runs (
  id                uuid primary key default uuid_generate_v4(),
  data_source_id    smallint not null references data_sources(id),
  status            run_status not null default 'running',
  council_id        smallint references councils(id),
  window_from       date,
  window_to         date,
  records_fetched   integer not null default 0,
  records_new       integer not null default 0,
  records_updated   integer not null default 0,
  records_rejected  integer not null default 0,
  projects_created  integer not null default 0,
  projects_updated  integer not null default 0,
  error             text,
  duration_ms       integer,
  started_at        timestamptz not null default now(),
  finished_at       timestamptz
);
create index ingestion_runs_source_idx on ingestion_runs (data_source_id, started_at desc);
create index ingestion_runs_failed_idx on ingestion_runs (started_at desc)
  where status in ('failed','partial');

-- Rows the pipeline refused, kept so a bad parse is visible rather than silent.
create table ingestion_rejects (
  id             uuid primary key default uuid_generate_v4(),
  run_id         uuid not null references ingestion_runs(id) on delete cascade,
  source_ref     text,
  reason         text not null,
  raw            jsonb,
  created_at     timestamptz not null default now()
);

-- Manually curated state and federally funded work that never appears in
-- council DA feeds. Compiled by hand each cycle; every row needs a source.
create table public_pipeline (
  id             uuid primary key default uuid_generate_v4(),
  name           text not null,
  location       text not null,
  council_id     smallint references councils(id),
  value_text     text not null,
  value_numeric  numeric(16,2),
  stage          text not null,
  detail         text,
  electrical_note text,
  source_name    text not null,
  source_url     text,
  verified_at    date not null,
  is_active      boolean not null default true,
  created_at     timestamptz not null default now()
);
comment on table public_pipeline is
  'Hand-compiled. source_name and verified_at are mandatory: nothing goes in a paid report unattributed.';


-- =====================================================================
-- 7. Triggers
-- =====================================================================

create or replace function touch_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

create or replace function projects_build_tsv() returns trigger
language plpgsql as $$
begin
  new.search_tsv := to_tsvector('english',
      coalesce(new.name,'')         || ' ' ||
      coalesce(new.address,'')      || ' ' ||
      coalesce(new.suburb,'')       || ' ' ||
      coalesce(new.builder_name,'') || ' ' ||
      coalesce(array_to_string(new.development_types,' '),''));
  return new;
end $$;

create trigger projects_tsv before insert or update of
  name, address, suburb, builder_name, development_types on projects
  for each row execute function projects_build_tsv();

create trigger projects_touch      before update on projects
  for each row execute function touch_updated_at();
create trigger profiles_touch      before update on profiles
  for each row execute function touch_updated_at();
create trigger subscriptions_touch before update on subscriptions
  for each row execute function touch_updated_at();
create trigger email_logs_touch    before update on email_logs
  for each row execute function touch_updated_at();
