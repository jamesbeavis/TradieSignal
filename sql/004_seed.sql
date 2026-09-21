-- =====================================================================
-- Tradiesignal :: seed data
-- =====================================================================
-- Council names MUST match the NSW ePlanning API's Appendix 1 list exactly —
-- the API filters on the literal string and silently returns nothing for a
-- near miss.
-- =====================================================================

insert into councils (name, short_name, slug, centroid, da_tracker_url, is_active) values
  ('Newcastle City Council',      'Newcastle',      'newcastle',
   st_point(151.7817, -32.9283)::geography,
   'https://www.newcastle.nsw.gov.au/council/access-to-information/application-tracker', true),
  ('Lake Macquarie City Council', 'Lake Macquarie', 'lake-macquarie',
   st_point(151.6167, -32.9667)::geography,
   'https://www.lakemac.com.au/Development/Development-applications', true),
  ('Maitland City Council',       'Maitland',       'maitland',
   st_point(151.5500, -32.7333)::geography,
   'https://www.maitland.nsw.gov.au/development/development-applications', true),
  ('Port Stephens Council',       'Port Stephens',  'port-stephens',
   st_point(152.0667, -32.7500)::geography,
   'https://www.portstephens.nsw.gov.au/development/development-applications', true),
  ('Cessnock City Council',       'Cessnock',       'cessnock',
   st_point(151.3500, -32.8333)::geography,
   'https://www.cessnock.nsw.gov.au/Development/Development-applications', true),
  -- Staged for expansion; ingested early so there is history on day one of sale.
  ('Central Coast Council',       'Central Coast',  'central-coast',
   st_point(151.3400, -33.4270)::geography, null, false),
  ('Singleton Council',           'Singleton',      'singleton',
   st_point(151.1700, -32.5670)::geography, null, false),
  ('Dungog Shire Council',        'Dungog',         'dungog',
   st_point(151.7550, -32.4030)::geography, null, false),
  ('Muswellbrook Shire Council',  'Muswellbrook',   'muswellbrook',
   st_point(150.8890, -32.2650)::geography, null, false);


insert into data_sources (key, name, kind, endpoint, licence, attribution, docs_url, refresh_cron, notes) values
  ('eplanning_da', 'NSW ePlanning — Development Applications', 'eplanning_api',
   'https://api.apps1.nsw.gov.au/eplanning/data/v0/OnlineDA',
   'CC BY 4.0',
   '© State of New South Wales (Department of Planning, Housing and Infrastructure)',
   'https://www.planningportal.nsw.gov.au/opendata/dataset/online-da-data-api',
   '20 15 * * *',
   'GET. Pagination and filters travel as HTTP HEADERS (PageSize, PageNumber, filters). '
   'No API key required. Filters JSON is {"filters":{...}}. Upstream refreshes daily.'),

  ('eplanning_cdc', 'NSW ePlanning — Complying Development Certificates', 'eplanning_api',
   'https://api.apps1.nsw.gov.au/eplanning/data/v0/OnlineCDC',
   'CC BY 4.0',
   '© State of New South Wales (Department of Planning, Housing and Infrastructure)',
   'https://www.planningportal.nsw.gov.au/opendata/dataset/online-da-data-api',
   '30 15 * * *',
   'Same header protocol as OnlineDA. Adds BuildingCodeClass. Fast-track work: '
   'approval to site start can be weeks.'),

  ('eplanning_cc', 'NSW ePlanning — Construction Certificates', 'eplanning_api',
   'https://api.apps1.nsw.gov.au/eplanning/data/v0/OnlineCC',
   'CC BY 4.0',
   '© State of New South Wales (Department of Planning, Housing and Infrastructure)',
   'https://www.planningportal.nsw.gov.au/opendata/dataset/online-da-data-api',
   '40 15 * * *',
   'THE MOST VALUABLE FEED. Carries BuilderLegalName / BuilderTradingName, '
   'ProposedGrossFloorArea, LandArea, CurrentBuildingUse and ProposedBuildingUse. '
   'A CC means work is imminent.'),

  ('buynsw_tenders', 'buy.nsw / NSW eTendering', 'tender_api',
   'https://www.tenders.nsw.gov.au/?event=public.api.tender.search',
   'NSW Government terms of use',
   'NSW Government buy.nsw',
   'https://github.com/NSW-eTendering/NSW-eTendering-API',
   '0 16 * * *',
   'NSW eTendering now sits under buy.nsw. Event-based endpoints; rate limited by IP. '
   'Filter to Hunter agencies and electrical/construction categories.'),

  ('austender', 'AusTender — federal opportunities', 'rss',
   'https://www.tenders.gov.au/public_data/rss/atm.xml',
   'Commonwealth terms of use', 'AusTender',
   'https://www.tenders.gov.au/', '15 16 * * *',
   'Federal ATMs. Relevant for Williamtown defence and aerospace work. '
   'CloudFront fronted — send a real User-Agent and back off on 403.'),

  ('major_projects', 'NSW Major Projects register', 'scrape',
   'https://www.planningportal.nsw.gov.au/major-projects/projects',
   'CC BY 4.0 (site terms)',
   '© State of New South Wales (Department of Planning, Housing and Infrastructure)',
   'https://www.planningportal.nsw.gov.au/major-projects', '0 17 * * 1',
   'No public API found as at 2026-09-10. Weekly scrape of the state significant '
   'register, filtered to Hunter LGAs. Low volume, high value.'),

  ('public_pipeline_manual', 'NSW Budget and agency announcements', 'manual',
   null, 'Public information', 'NSW Government', null, null,
   'Hand-compiled each cycle from the NSW Budget regional papers, EnergyCo, '
   'Health Infrastructure, Schools Infrastructure and Transport for NSW. '
   'Every row requires source_name and verified_at.');


insert into plans (tier, name, price_cents, stripe_price_id, max_councils, max_radius_km,
                   max_seats, includes_builders, includes_tenders, includes_export,
                   daily_alerts, seat_cap_per_lga) values
  ('trial',        'Free trial',    0,     null,                        null, 100, 1, true,  false, false, false, null),
  ('starter',      'Starter',       4900,  'price_REPLACE_starter',     1,    25,  1, false, false, false, false, 40),
  ('professional', 'Professional',  9900,  'price_REPLACE_professional',null, 100, 1, true,  false, true,  false, 25),
  ('premium',      'Premium',       19900, 'price_REPLACE_premium',     null, 300, 3, true,  true,  true,  true,  null);


-- The scoring configuration that produced Issue 01. Keep old versions:
-- reproducing a past report is how you answer "why did you send me that?".
insert into scoring_configs (version, is_active, base_scores, stage_weights,
  value_bands, distance_bands, signal_bonuses, electrical_share, quality_rules, notes,
  activated_at)
values (
  '2026.09.1', true,
  '{"energy":100,"infrastructure":92,"healthcare":90,"education":88,"industrial":84,
    "retail":82,"commercial":80,"subdivision":78,"residential_new":70,
    "residential_reno":48,"other":40,"low_value":12}'::jsonb,
  '{"cc_determined":{"m":1.00,"weeks":2},"cc_lodged":{"m":0.96,"weeks":6},
    "cdc_approved":{"m":0.94,"weeks":4},"cdc_lodged":{"m":0.86,"weeks":10},
    "da_determined":{"m":0.90,"weeks":20},"da_exhibition":{"m":0.72,"weeks":44},
    "da_assessment":{"m":0.74,"weeks":40},"da_info":{"m":0.66,"weeks":48},
    "da_lodged":{"m":0.70,"weeks":44},"withdrawn":{"m":0.00,"weeks":0}}'::jsonb,
  '[[50000,0.35],[150000,0.55],[500000,0.75],[1500000,0.90],[5000000,1.00],
    [20000000,1.10],[100000000,1.20],[null,1.28]]'::jsonb,
  '[[10,1.00],[25,0.97],[50,0.90],[100,0.78],[null,0.60]]'::jsonb,
  '{"builder_named":6,"multi_dwelling":5,"large_dwelling_count":8,"large_gfa":4,
    "commercial_class":4,"subdivision_lots":5,"ev_or_solar_hint":5,"vpa":3,
    "state_significant":8}'::jsonb,
  '{"energy":[0.35,0.60],"infrastructure":[0.12,0.22],"healthcare":[0.14,0.22],
    "education":[0.11,0.17],"industrial":[0.10,0.18],"retail":[0.10,0.16],
    "commercial":[0.09,0.15],"subdivision":[0.04,0.09],"residential_new":[0.06,0.10],
    "residential_reno":[0.05,0.11],"other":[0.06,0.12],"low_value":[0.02,0.08]}'::jsonb,
  '{"cost_per_sqm_min":250,"cost_per_sqm_max":35000,"cost_per_dwelling_min":60000,
    "cost_per_dwelling_max":4000000,"uncorroborated_cost_ceiling":30000000,
    "minimum_useful_cost":20000}'::jsonb,
  'Launch configuration. Electrical share percentages are industry rules of thumb and '
  'MUST be recalibrated against real won-job data once 20+ customers report outcomes.',
  now()
);
