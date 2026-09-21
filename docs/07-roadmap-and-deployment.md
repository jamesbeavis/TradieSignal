# Build roadmap and deployment

---

## 1. Roadmap

The sequencing rule throughout: **do not build the next thing until the current
thing has customers who complain about its absence.**

### Phase 0 — Weeks 1–8 · Validation (no software)

Already done in this repository. What remains is selling.

- [x] ePlanning collector for three services across five councils
- [x] Normalisation, address linking, cost validation, scoring
- [x] Branded report generator (PDF + web)
- [x] Landing page and dashboard demo
- [ ] Verify the addressable market against ABS and NSW Fair Trading
- [ ] Register the domain, set up a real email address
- [ ] Stripe payment link at $49 founding price
- [ ] **Sell 10 subscriptions**

**Gate to Phase 1: 10 paying subscribers, retained 2 months.**

### Phase 1 — Weeks 9–16 · Automate the boring parts

- Supabase project; run the four migrations
- Port the Python pipeline to Edge Functions (the logic is proven — this is a
  translation, not a redesign)
- pg_cron schedules for the three collectors and the scorer
- Resend integration; React Email template for the digest
- Stripe Checkout and webhook; self-serve signup
- Magic-link auth, minimal account page
- Health monitoring and the silent-zero alert

Deliberately **not** in Phase 1: the dashboard. Subscribers must ask for it
first, and they will tell you which three filters they actually want, which is
worth more than guessing at twelve.

**Gate to Phase 2: 25 subscribers, digest sending reliably for 4 weeks.**

### Phase 2 — Months 5–8 · The application

- Opportunity dashboard: filters, sort, detail panel
- Saved searches with alerts
- Builder watchlist (Professional and above)
- CSV export
- Map view — genuinely useful for planning a day's site visits, and the data is
  already geocoded
- Marketing site: council and suburb programmatic pages
- Free trial with activation instrumentation

**Gate to Phase 3: 50 subscribers, under 5% monthly churn.**

### Phase 3 — Months 9–14 · Depth

- Tender and public pipeline coverage (Premium)
- Major projects register scraper
- Daily alerts
- Builder profile pages, both as a product feature and as SEO surface
- Team seats
- Scoring recalibration against real won-job data from customers — the first
  time the electrical percentages stop being rules of thumb
- Quarterly Hunter Construction Report as a public data release

**Gate to Phase 4: 100 subscribers, $9k+ MRR.**

### Phase 4 — Months 15–24 · Expand

- Central Coast, then Wollongong, then Sydney by region
- Adjacent trades: solar, data, air conditioning, fire — a config change, not a
  rebuild
- Public API for Premium
- Mobile app **only if** usage data shows it is needed; a good responsive site
  usually is enough for this audience

### Later, if the business earns it

| Idea | Value | Why it is not sooner |
|---|---|---|
| Outcome tracking ("did you win it?") | very high — closes the scoring feedback loop and proves ROI | needs enough customers to produce signal |
| Predicted approval timing from historical council data | high | needs 2+ years of history |
| Builder contact details | very high | genuine privacy and data-protection care needed; do it properly or not at all |
| Automatic intro email drafting | medium | easy to do badly and damage the customer's reputation |
| White-label for wholesalers | medium | a distribution deal, not a product |
| Materials demand forecasting for suppliers | high — a different, larger customer | a separate business on the same pipeline |

---

## 2. Deployment

### 2.1 Supabase

```bash
npx supabase init
npx supabase link --project-ref <ref>

# Extensions: enable postgis, pg_trgm, pg_cron, uuid-ossp in
# Dashboard → Database → Extensions before the first migration.

npx supabase db push          # runs sql/001 → 004 in order
```

The migrations have been validated against PostgreSQL 16 with PostGIS: all four
apply cleanly to an empty database, 003 is re-runnable, and RLS was verified by
role (anonymous sees only the teaser set, a signed-in user with no subscription
sees nothing, service role sees everything).

Two things that are Supabase-provided and therefore stubbed in local testing:
the `auth` schema, and the `anon` / `authenticated` / `service_role` roles.

### 2.2 Edge Functions

```bash
npx supabase functions deploy collect-eplanning
npx supabase functions deploy score-projects
npx supabase functions deploy send-digest

npx supabase secrets set RESEND_API_KEY=... EMAIL_FROM=...
```

### 2.3 Scheduling

```sql
select cron.schedule('collect-da',  '20 15 * * *', $$
  select net.http_post(
    url := 'https://<ref>.supabase.co/functions/v1/collect-eplanning',
    headers := jsonb_build_object('Authorization','Bearer '||current_setting('app.service_key'),
                                  'Content-Type','application/json'),
    body := '{"service":"OnlineDA","council":"Newcastle City Council","days":45}'::jsonb
  ) $$);
```

**Times are UTC.** `15:20 UTC` is `01:20` next day in Sydney during AEST. Get
this wrong and the collector runs at lunchtime; get it wrong in the other
direction and the Monday digest goes out on Sunday afternoon. One schedule per
(service, council) — fifteen jobs for five councils — which keeps each
invocation well inside the Edge Function timeout and makes a single failure
isolable.

### 2.4 Vercel

```bash
vercel link
vercel env add NEXT_PUBLIC_SUPABASE_URL production
# … and the rest from docs/04-api-and-app.md §6
vercel --prod
```

Set the region to `syd1`. Round trips to Sydney matter for a mobile audience on
patchy reception.

### 2.5 Stripe

1. Create three products with monthly AUD prices: $49, $99, $199.
2. Copy the price ids into env and into `plans.stripe_price_id`.
3. Webhook endpoint → `https://tradiesignal.com.au/api/stripe/webhook`,
   subscribed to the five events in `docs/04-api-and-app.md` §4.
4. Enable Stripe Tax for GST.
5. Configure the Billing Portal to allow plan changes and cancellation.
6. **Test in test mode end to end**: subscribe, upgrade, fail a payment with
   `4000000000000341`, cancel. Confirm the database matches Stripe at each step.

### 2.6 Go-live checklist

- [ ] All four migrations applied; `select * from source_health()` returns rows
- [ ] Collector run manually per council; `ingestion_runs` shows `success` and
      non-zero counts for all five
- [ ] Scorer run; spot-check ten projects against the council DA trackers
- [ ] Stripe test-mode lifecycle verified
- [ ] Digest sent to yourself; opened on an actual phone, in Gmail and Outlook
- [ ] Unsubscribe link works and is honoured
- [ ] CC-BY attribution present on every page, every export, and in the email footer
- [ ] Sentry receiving errors; PostHog receiving events
- [ ] `robots.txt` and segmented sitemaps; `/dashboard` is `noindex`
- [ ] Health check alerting to email **and** SMS
- [ ] Silent-zero alert tested by deliberately misspelling a council name
- [ ] A real human monitors the reply-to inbox

---

## 3. Operating rhythm once live

| Cadence | Task |
|---|---|
| Daily | Glance at `source_health()`. Read any replies to yesterday's email. |
| Weekly | Read the digest as a customer before it sends. Check churn, replies, trial conversion. |
| Monthly | Review the scoring config against what customers actually asked about. Reconcile Stripe against `subscriptions`. |
| Quarterly | Publish the Hunter Construction Report. Recalibrate the electrical percentages against reported job values. Review the source inventory for changes. |
| Annually | Re-verify every data source's terms of use and licence. |

---

## 4. The two failure modes to watch for

**Silent data staleness.** The pipeline reports success, the email goes out, and
it contains nothing new because a council name changed or an endpoint moved.
The customer notices before you do, and they do not complain — they just
cancel. This is why the silent-zero guard exists in the collector and why the
health check compares against the previous run rather than just checking for
errors.

**Scoring drift.** The model is calibrated on assumptions today. If nobody ever
recalibrates it against real outcomes, it slowly becomes confident nonsense
delivered on a reliable schedule. Build outcome tracking as soon as there are
enough customers to produce signal, and until then treat the monthly config
review as non-optional.
