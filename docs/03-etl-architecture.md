# ETL and data architecture

Everything here has been run against the live sources. Where a source could not
be reached, that is stated rather than assumed.

---

## 1. Source inventory — verified 10 September 2026

### 1.1 The spine: NSW ePlanning open data API

This is the whole product. It is free, needs no API key, is licensed CC-BY, and
refreshes daily.

```
GET https://api.apps1.nsw.gov.au/eplanning/data/v0/{service}
```

Three services are live on the open `v0` feed:

| Service | What it is | Why it matters | Records, 5 Hunter LGAs, 120 days |
|---|---|---|---|
| `OnlineDA` | Development applications | The pipeline, 6–24 months out | 2,071 |
| `OnlineCDC` | Complying development certificates | Fast-track; can start in weeks | 1,292 |
| `OnlineCC` | Construction certificates | **Work is imminent, and it names the builder** | 1,456 |

`OnlinePCC`, `OnlineCR`, `STRA`, `OnlineBIC`, `OnlineS68` and `OnlineS107` all
return `404 Resource not found` on this host. They exist only on the
subscription-key council integration APIs, which are a different product.

**The protocol is unusual and undocumented in the dataset listing.** It is a
`GET`, and pagination and filters travel as **HTTP headers**, not query strings:

```http
GET /eplanning/data/v0/OnlineCC HTTP/1.1
Host: api.apps1.nsw.gov.au
PageSize: 100
PageNumber: 1
filters: {"filters":{"CouncilName":["Newcastle City Council"],"LodgementDateFrom":"2026-05-13"}}
```

Failure modes worth knowing before you debug them:

- `POST` to the same path returns `404`, not `405`. Use `GET`.
- A query-string `filters` parameter returns `400 Required parameters for
  OnlineDA endpoint is not met`. It must be a header.
- `CouncilName` must match the API's Appendix 1 spelling **exactly**. A near
  miss returns an empty result set with HTTP 200 — a silent zero, which is the
  most dangerous failure this pipeline has. The collector must assert that a
  known-active council returns non-zero.

Response shape (`TotalCount`, `TotalPages`, `Application[]`) is consistent
across all three services. Fields that matter:

| Field | Present on | Used for |
|---|---|---|
| `PlanningPortalApplicationNumber` | all | primary source key (`PAN-`/`CDC-`/`CFT-`) |
| `CouncilApplicationNumber` | DA | the reference the customer quotes to council |
| `CostOfDevelopment` | all | value, and the thing that needs validating |
| `Location[].X` / `.Y` | all | longitude / latitude — **X is lon, Y is lat** |
| `DevelopmentType[]` | all | classification |
| `BuildingCodeClass[]` | CDC, CC | commercial vs residential signal |
| `ProposedGrossFloorArea`, `ExistingGrossFloorArea` | CC | cost plausibility check |
| `BuilderLegalName`, `BuilderTradingName` | **CC only** | the builder watchlist |
| `NumberOfNewDwellings`, `UnitsProposed` | DA/CDC, CC | scale and plausibility |
| `CurrentBuildingUse`, `ProposedBuildingUse` | CC | classification |

`BuilderLegalName` populated on 665 of 1,456 construction certificates — about
46%. That single field is the strongest differentiator the product has.

**Licence obligation.** CC-BY requires attribution. Every report, page and
export must carry: *© State of New South Wales (Department of Planning, Housing
and Infrastructure), used under CC BY 4.0.* This is not optional and it is
cheap; do it everywhere.

### 1.2 Secondary sources

| Source | Access | Status as tested | Use |
|---|---|---|---|
| Online DA Data API (bulk) | email `data.broker@environment.nsw.gov.au` | Not attempted; the `v0` feed already serves the need | Bulk history backfill if ever needed |
| NSW eTendering / buy.nsw | `tenders.nsw.gov.au/?event=public.api.tender.search` | Endpoints documented on the official GitHub; **CloudFront blocked this sandbox's IP**, so untested here. Works from a normal server. | Government electrical and maintenance contracts |
| AusTender | `tenders.gov.au/public_data/rss/atm.xml` | **403 from this sandbox** (CloudFront). Send a real User-Agent from a normal host. | Federal work, Williamtown defence corridor |
| NSW Major Projects register | `planningportal.nsw.gov.au/major-projects/projects` | **No public API found.** `api.majorprojects.*` and `mpweb.*` do not resolve or 404. | Weekly scrape, low volume / high value |
| NSW Budget regional papers | manual | Verified; used in Issue 01 | The funded public pipeline |
| EnergyCo, Health Infrastructure, Schools Infrastructure | manual / RSS | Verified for Issue 01 | Major project announcements |

Treat every non-ePlanning source as **enrichment**. If all of them broke
tomorrow the product would still be worth $99/month, because the council feed
is the product.

---

## 2. Pipeline shape

```
                     ┌──────────────────────────────────────┐
                     │  Supabase Edge Function (Deno)       │
   pg_cron 01:20 ───▶│  collect-eplanning                   │
   pg_cron 01:30 ───▶│    one invocation per (service,LGA)  │
   pg_cron 01:40 ───▶│                                      │
                     └───────────────┬──────────────────────┘
                                     │ raw JSON
                                     ▼
                     ┌──────────────────────────────────────┐
                     │  applications  (raw jsonb preserved)  │
                     └───────────────┬──────────────────────┘
                                     │ link on normalised address
                                     ▼
                     ┌──────────────────────────────────────┐
   pg_cron 02:10 ───▶│  normalise → validate → classify →    │
                     │  score → estimate                    │
                     │  writes projects + opportunity_scores │
                     └───────────────┬──────────────────────┘
                                     │
                     ┌───────────────┴──────────────────────┐
                     ▼                                      ▼
        refresh_builders()                        source_health()
        (the watchlist)                           (pages you if stale)
                     │
   pg_cron Mon 06:00 ▼
        ┌────────────────────────────┐
        │ send-digest                │──▶ Resend ──▶ email_logs
        │ digest_for_profile() per   │              project_deliveries
        │ subscriber, suppression on │
        └────────────────────────────┘
```

Six stages, each independently replayable:

1. **Collect.** Fetch, page, and write to `applications` with `raw` intact.
   Never transform at this stage. If the parser is wrong, you want to fix it
   and replay, not refetch 5,000 records.
2. **Link.** `normalise_address()` → find or create the `projects` row. A site
   that has a DA, a CDC and a CC is one project with three applications.
3. **Validate.** Cross-check `CostOfDevelopment` against floor area, dwelling
   count and lot count. Assign `cost_confidence`. See §4 — this is not
   optional polish, it is the credibility of the product.
4. **Classify.** Category, filter group, likely electrical scope.
5. **Score.** Apply the active `scoring_configs` row. Write the materialised
   score to `projects` and an immutable copy to `opportunity_scores`.
6. **Distribute.** Digest selection, suppression, send, log.

### Why raw payloads are kept

The scoring model is going to be wrong at launch. The electrical percentages
are rules of thumb until real customers report real job values. When you
recalibrate — and you will, twice in the first year — you must be able to
replay six months of history through the new config and see whether the new
scores would have ranked better. That is impossible if you threw the source
records away. Storage is measured in tens of megabytes a year. Keep it.

---

## 3. Idempotency and change detection

`applications` is unique on `(data_source_id, source_ref)`. Every write is an
upsert:

```sql
insert into applications (data_source_id, source_ref, project_id, ..., raw)
values (...)
on conflict (data_source_id, source_ref) do update
   set status_raw = excluded.status_raw,
       stage = excluded.stage,
       cost_declared = excluded.cost_declared,
       date_determined = excluded.date_determined,
       builder_legal_name = coalesce(excluded.builder_legal_name,
                                     applications.builder_legal_name),
       raw = excluded.raw,
       source_updated_at = excluded.source_updated_at,
       ingested_at = now()
 where applications.source_updated_at is distinct from excluded.source_updated_at;
```

Two things to notice:

- The `where` clause means an unchanged record is not rewritten, so
  `records_updated` in `ingestion_runs` is a true change count, not a row
  count. That number is your early warning that a source has gone stale.
- `builder_legal_name` uses `coalesce` on the **existing** value. Sources
  occasionally drop a field on a later revision; never let a null overwrite a
  builder name you already have.

Incremental windows use `ApplicationLastUpdatedFrom` where the service
supports it, with a 7-day overlap to catch late-arriving amendments. Run a full
120-day sweep weekly to catch anything the incremental window missed.

---

## 4. Data quality — the part that earns the subscription

Declared cost is entered by the applicant and audited by nobody. The current
dataset contains a **$1,375,000,000 two-dwelling development at 48 Yoolarai
Crescent, Nelson Bay**. Publishing that in a paid report ends the business.

The validator cross-checks each figure against whatever physical scale the feed
supplies, and is deliberately narrow: a false "suspect" flag suppresses a real
opportunity, which harms the customer just as much as a fake one.

| Check | Runs when | Passing band |
|---|---|---|
| cost ÷ **new** floor area | new build, category not energy/infrastructure, new GFA > 30 m² | $250 – $35,000 /m² |
| cost ÷ dwellings | any project with dwellings | $60k – $4m residential; ×0.5–×2.5 wider for mixed use |
| cost ÷ lots | subdivision | $5k – $2m |
| uncorroborated ceiling | no check possible, not energy/infrastructure | $30m |

Outcome:

| `cost_confidence` | Meaning | Counted in totals? |
|---|---|---|
| `high` | passed every applicable check | yes |
| `medium` | passed some, or nothing to check but sane | yes |
| `low` | below the useful threshold | yes |
| `suspect` | failed every applicable check | **no** — shown, flagged |
| `unverified` | large and uncorroborated | **no** — shown, flagged |
| `unknown` | no figure lodged | n/a |

Current run: 1,658 high, 1,775 medium, 367 low, 48 suspect, 10 unverified,
106 unknown.

Two exemptions matter and both were found by testing against real records:

- **Equipment-heavy categories are exempt from the per-m² check.** The Steel
  River East battery declares $208m against almost no floor area — $866,667/m².
  That is correct, not an error, and the naive rule suppressed the single best
  opportunity in the dataset.
- **The per-dwelling check runs for any project containing dwellings**, not
  just residential-category ones. Restricting it to residential left a genuine
  280-apartment tower at $80.3m sitting in the unverified bucket.

Both are in `EQUIPMENT_HEAVY` and `validate_cost()` respectively, with the
reasoning in comments. Do not "simplify" them away.

---

## 5. Project linking

The feeds share no project identifier across services, so the join key is a
normalised address:

```sql
upper(regexp_replace(address, '[^A-Za-z0-9]', '', 'g'))
```

`"14 CLAREMONT AVENUE ADAMSTOWN HEIGHTS 2289"` → `14CLAREMONTAVENUEADAMSTOWNHEIGHTS2289`.

Falls back to `lot/plan` when the address is too short to be distinctive, then
to the record's own reference so nothing is ever merged by accident. In the
current data this collapses 4,819 applications into 3,964 distinct projects.

**Known limits, stated honestly:**

- A large site with several street frontages appears as separate projects.
- Staged developments lodged against the same address merge into one.
- Addresses recorded as `2/-/DP1320669` do not link.

Better linking is a lot cadastral join through the NSW Spatial Services
property layer. Worth doing at roughly 200 subscribers; not worth it before.

---

## 6. Scheduling and alerting

| Job | Cadence | Notes |
|---|---|---|
| `collect-eplanning` (DA) | daily 01:20 | upstream refreshes daily |
| `collect-eplanning` (CDC) | daily 01:30 | |
| `collect-eplanning` (CC) | daily 01:40 | the important one |
| `score-projects` | daily 02:10 | after all three collectors |
| `refresh-builders` | daily 02:30 | |
| `collect-tenders` | daily 02:00 | buy.nsw + AusTender |
| `scrape-major-projects` | weekly Mon 03:00 | low volume |
| `send-digest` | weekly Mon 06:00 AEST | subscriber local time |
| `send-daily-alerts` | daily 06:30 | Premium only |
| `health-check` | hourly | calls `source_health()` |

Alert when any of these is true:

- `consecutive_failures >= 3` on an active source.
- No successful run for an active source in 36 hours.
- A collector returns **zero records for a council that returned records
  yesterday** — this is the silent-failure case that a plain error alert misses
  entirely, and the one most likely to actually happen.
- Total records ingested drops more than 60% against the trailing 7-day mean.
- A digest run sends fewer emails than there are active subscribers.

Route to email plus SMS. A weekly product with a broken Sunday night pipeline
has no Monday, and the customer notices before you do.

---

## 7. Cost

At 100 subscribers, five councils, daily ingestion:

| Item | Monthly |
|---|---|
| Supabase Pro | US$25 |
| Vercel Pro | US$20 |
| Resend (≈2,000 emails) | US$0–20 |
| PostHog | free tier |
| Domain, misc | ~$5 |
| **Total** | **≈US$70–90** |

Against $9,900/month of revenue at 100 Professional subscribers. The data costs
nothing; the cost of goods sold here is essentially the operator's Sunday
evening until it is automated.
