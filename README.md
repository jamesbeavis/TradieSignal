# Tradiesignal

**Know about electrical work opportunities before your competitors.**

Construction opportunity intelligence for electricians in Newcastle, Lake
Macquarie, Maitland, Port Stephens and Cessnock.

This repository contains a **working data product**, not a proposal. The
scripts here pull live NSW government data, score it, and produce a report you
can sell on Monday.

---

## What actually works right now

Run `./run_weekly.sh` and in about six minutes you get:

| Output | What it is |
|---|---|
| `reports/Tradiesignal_Hunter_Report.pdf` | 24-page branded report, ready to send |
| `reports/report_web.html` | Web version of the same |
| `site/landing.html` | Landing and pricing page |
| `site/dashboard.html` | Working dashboard over 1,500 scored projects |
| `data/projects.csv` | Every scored project, for a spreadsheet |
| `data/projects.json` | Full scored dataset |

Last run: **3,903 projects → $3.22bn verified
construction value → 33 high priority.**

---

## The finding that makes this a business

The NSW Planning Portal publishes a **free, no-API-key, CC-BY licensed feed**
of every planning application in the state, refreshed daily:

```
GET https://api.apps1.nsw.gov.au/eplanning/data/v0/{OnlineDA|OnlineCDC|OnlineCC}
```

Three things about it are not obvious and are the difference between this
working and not:

1. **It is a `GET`, and pagination and filters travel as HTTP *headers*.** A
   `POST` returns 404; a `filters` query parameter returns 400.
2. **`OnlineCC` — construction certificates — carries `BuilderLegalName`.**
   That field appears on ~46% of certificates and it names the actual building
   company. No council website exposes it. It turns the product from "here are
   some approvals" into *"ring GWH Build about 309 King Street this week"*.
3. **A misspelled council name returns HTTP 200 with zero records.** Silent
   failure is the most dangerous thing in this pipeline and the collector
   guards against it explicitly.

Cross-validated against news reporting: the $208m "electricity generating
facility" at 1 McIntosh Drive, Mayfield West is the Steel River East battery,
and its certificate names Southern Cross Electrical Engineering as builder.

---

## Read this first

1. **[`GO-LIVE.md`](GO-LIVE.md)** — deploying tradiesignal.com, taking payment,
   and what to do this week.
   **[`docs/08-auto-refresh.md`](docs/08-auto-refresh.md)** — the GitHub Action
   that refreshes the site weekly without you.
2. **[`docs/01-validation-runbook.md`](docs/01-validation-runbook.md)** — how to
   sell the report before building any software. Everything else can wait.

---

## Repository layout

```
GO-LIVE.md                     deployment + first-week checklist
run_weekly.sh                  the whole pipeline, one command
netlify.toml                   static hosting config

.github/workflows/
  refresh-data.yml             weekly auto-refresh — collects, rebuilds, deploys

deploy/                        standalone site, ready for Netlify
  index.html                   landing page
  sample-report/index.html     the report, with download + signup
  demo/index.html              dashboard shell (34KB, fetches its data)
  data/dashboard.json          the project rows the dashboard fetches
  robots.txt, sitemap.xml

src/
  collect_eplanning.py         NSW ePlanning collector (3 services × 5 councils)
  scoring_config.py            EVERY tunable number lives here
  normalise_and_score.py       link → validate → classify → score → estimate
  report_data.py               report slices + the hand-compiled public pipeline
  build_report.py              report renderer (print + web from one source)
  build_landing.py             landing page
  build_dashboard.py           dashboard
  build_site.py                wraps pages into a deployable static site
  export_pdf.cjs               HTML → PDF via Chromium

sql/
  001_schema.sql               tables, enums, indexes, triggers
  002_rls.sql                  row level security + grants
  003_functions.sql            search, digest selection, builder roll-up
  004_seed.sql                 councils, sources, plans, scoring config

supabase/functions/
  collect-eplanning/index.ts   production collector (Deno Edge Function)

docs/
  01-validation-runbook.md     ← start here
  02-sales-kit.md              scripts, templates, objection handling
  03-etl-architecture.md       sources, pipeline, data quality
  04-api-and-app.md            API contract, Stripe, email design
  05-growth-plan.md            market sizing, unit economics, channels
  06-seo-content.md            site architecture, 50 articles
  07-roadmap-and-deployment.md phased build + deployment
  08-auto-refresh.md           how the site keeps itself current

data/
  raw/                         verbatim API snapshots (replay-safe)
  projects.json / .csv         scored output
  summary.json                 aggregates
```

---

## The scoring model

Every project scores 0–100 from five inputs, all configurable in
`src/scoring_config.py`:

```
score = (category_base × stage × value × distance) + signal_bonus
```

**Stage does most of the work.** A construction certificate for a medical
centre outranks a much larger subdivision application, because one needs an
electrician in a fortnight and the other in two years.

Electrical opportunity is estimated as a percentage band of declared cost,
varying by sector — 35–60% for energy projects, 6–10% for new residential.
**These are industry rules of thumb and are labelled as estimates everywhere
they appear.** Recalibrate them against real won-job data as soon as customers
report outcomes.

---

## Data quality

Declared costs are entered by applicants and audited by nobody. The current
dataset contains a **$1,375,000,000 two-dwelling development in Nelson Bay**.

Every figure is cross-checked against floor area, dwelling count and lot count.
Anything that fails is flagged, shown, and excluded from every total. Current
run: 1,623 high confidence, 1,761 medium, 353 low, **44 suspect, 12
unverified**, 110 with no figure lodged.

Two exemptions were found by testing against real records and matter:

- Energy and infrastructure projects are exempt from the per-m² check — the
  Steel River battery legitimately declares $866,667/m².
- The per-dwelling check runs for any project with dwellings, not just
  residential-category ones, or genuine 280-apartment mixed-use towers get
  wrongly suppressed.

---

## Verification status

| Component | Status |
|---|---|
| ePlanning API contract | **Verified live**, 10 Sep 2026 — all three endpoints |
| 4,819 records collected | **Real data** from 5 Hunter councils, 120 days |
| Scoring pipeline | **Deterministic** — byte-identical output across runs |
| SQL schema | **Applied to PostgreSQL 16 + PostGIS**; all 4 migrations clean, 003 re-runnable |
| RLS policies | **Verified by role** — anon sees 8 teaser rows, no-subscription sees 0, service role sees 3,964 |
| `search_projects()` | **Tested** with sector + stage + PostGIS radius against real data |
| `digest_for_profile()` | **Tested** end to end for a seeded subscriber |
| `refresh_builders()` | **Tested** — 286 builders, matching the Python analysis |
| Edge Function | Syntax and protocol-invariant checked; **not deployed** |
| Report figures | **Every quoted number checked** against source data |
| eTendering / AusTender | **Not verified** — CloudFront blocked this sandbox. Endpoints documented; test from a normal host |
| Major Projects register | **No public API found**; scrape target |
| Market size (~400 businesses) | **Estimate, not verified.** IBISWorld paywalled. Check ABS + NSW Fair Trading |

---

## Attribution

Council development data comes from the NSW Planning Portal ePlanning open data
APIs, © State of New South Wales (Department of Planning, Housing and
Infrastructure), used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**Attribution is a licence condition.** It appears on every report page, every
site page, the email footer and every API response. Keep it there.

Public pipeline figures come from the NSW Budget 2026-27 regional papers and
agency announcements, cited individually in the report.

Opportunity scores, electrical estimates and contact timing are Tradiesignal's
own analysis, not official information.

---

## Requirements

```bash
python3          # standard library only — no pip install needed
node             # for PDF export
npm i playwright # Chromium is already at /opt/pw-browsers/chromium
```
