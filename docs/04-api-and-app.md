# API architecture, app structure and email

---

## 1. Stack

| Layer | Choice | Why this one |
|---|---|---|
| Frontend | Next.js 15 App Router, TypeScript, Tailwind | Server components mean the programmatic SEO pages render on the server with no extra work |
| Database | Supabase Postgres + PostGIS | Radius filtering is a first-class product feature; doing it in Postgres beats doing it in JavaScript |
| Auth | Supabase Auth, magic link | Tradespeople will not remember a password. Magic link removes the single biggest signup drop-off |
| Jobs | Supabase Edge Functions + pg_cron | No separate worker infrastructure to run or pay for |
| Payments | Stripe Checkout + Billing Portal | Do not build billing UI. Checkout and the Portal handle cards, invoices, dunning and tax |
| Email | Resend + React Email | The weekly digest is the product; it must render in Outlook and Gmail on a phone |
| Analytics | PostHog | Funnels and session replay in one tool at this scale |
| Hosting | Vercel | Sydney region |
| Errors | Sentry | |

Total infrastructure cost at 100 subscribers: about **US$70–90/month** against
$9,400 MRR.

---

## 2. Route map

```
app/
  (marketing)/
    page.tsx                              landing
    pricing/page.tsx
    sample-report/page.tsx                ungated — the conversion asset
    construction/[council]/page.tsx        ISR, revalidate daily
    development-applications/[suburb]/page.tsx
    builders/[slug]/page.tsx
    sectors/[sector]/page.tsx
    for/[audience]/page.tsx
    guides/[slug]/page.tsx

  (app)/
    dashboard/page.tsx                     the opportunity list
    projects/[id]/page.tsx                 detail
    saved/page.tsx                         saved searches
    account/page.tsx                       profile, base location, radius
    billing/page.tsx                       redirects to Stripe Portal

  api/
    projects/route.ts                      GET   search
    projects/[id]/route.ts                 GET   detail
    projects/export/route.ts               GET   CSV  (entitlement: export)
    builders/route.ts                      GET   watchlist (entitlement: builders)
    saved-searches/route.ts                GET POST
    saved-searches/[id]/route.ts           PATCH DELETE
    profile/route.ts                       GET PATCH
    stripe/checkout/route.ts               POST
    stripe/portal/route.ts                 POST
    stripe/webhook/route.ts                POST  (no auth; signature verified)
    cron/health/route.ts                   GET   (Vercel Cron)

supabase/functions/
  collect-eplanning/                       per service, per council
  collect-tenders/
  score-projects/
  send-digest/
  send-daily-alerts/
```

---

## 3. API contract

### `GET /api/projects`

The one endpoint the dashboard uses. It is a thin wrapper over the
`search_projects()` database function so the dashboard, the API and the weekly
email can never disagree about what a filter means.

**Query parameters**

| Param | Type | Default | Notes |
|---|---|---|---|
| `groups` | csv | all | `Residential,Commercial,Industrial,Government,Infrastructure` |
| `councils` | csv of ids | plan default | clamped to entitlement |
| `stages` | csv | all | `cc_determined`, `cdc_approved`, `da_determined`, … |
| `minScore` | int | profile default | |
| `minCost` | int | — | |
| `radiusKm` | int | profile default | clamped to `plans.max_radius_km` |
| `since` | date | — | |
| `q` | string | — | full-text |
| `sort` | enum | `score` | `score` \| `value` \| `new` \| `distance` |
| `limit` | int | 50 | max 200 |
| `offset` | int | 0 | |

**Response**

```json
{
  "data": [{
    "id": "…", "publicRef": "TS-1-1024947",
    "name": "Mixed use development (280 dwellings), Newcastle West",
    "address": "309 King Street Newcastle West 2302",
    "suburb": "Newcastle West", "council": "Newcastle",
    "filterGroup": "Commercial", "category": "commercial",
    "stage": "cc_lodged", "stageLabel": "Construction certificate lodged",
    "cost": 80300000, "costConfidence": "high",
    "electrical": { "low": 7227000, "high": 12045000, "sharePct": [9, 15] },
    "score": 100, "priority": "high",
    "builder": "GWH BUILD PTY LTD",
    "dwellings": 280, "distanceKm": 1.5,
    "lastActivity": "2026-09-02"
  }],
  "meta": { "total": 1107, "limit": 50, "offset": 0,
            "attribution": "© State of New South Wales (Department of Planning, Housing and Infrastructure), CC BY 4.0" }
}
```

The `attribution` field is in every response on purpose. It is a licence
obligation, and putting it in the payload means no consumer can forget it.

**Errors** are `{ "error": { "code", "message", "detail" } }` with:

| Code | HTTP | When |
|---|---|---|
| `unauthenticated` | 401 | no session |
| `no_subscription` | 402 | signed in, no live subscription |
| `entitlement_required` | 403 | feature not on plan; `detail` names the feature and the tier that has it |
| `invalid_parameter` | 400 | |
| `rate_limited` | 429 | with `Retry-After` |

`402` and `403` are distinct deliberately: one means "subscribe", the other
means "upgrade", and the UI should say different things.

### Entitlement enforcement

Enforced in **three** places, and all three are needed:

1. **RLS** — the floor. Even a leaked anon key cannot read a Premium row.
2. **Route handler** — returns a clean `403` with an upgrade path rather than
   an empty array, because an empty array is indistinguishable from "no
   results" and makes users think the product is broken.
3. **UI** — shows the feature greyed out with the tier that unlocks it. Never
   hide a feature entirely; a visible locked feature is the best upgrade prompt
   you have.

### Rate limits

| Tier | Requests/min | Export/day |
|---|---|---|
| anon | 20 | — |
| trial / starter | 60 | — |
| professional | 120 | 10 |
| premium | 300 | 50 |

---

## 4. Stripe integration

### Checkout

```ts
// app/api/stripe/checkout/route.ts
const session = await stripe.checkout.sessions.create({
  mode: "subscription",
  line_items: [{ price: PRICE_ID[tier], quantity: 1 }],
  customer_email: user.email,
  client_reference_id: user.id,            // ties the session back to the profile
  subscription_data: {
    trial_period_days: 14,
    metadata: { profile_id: user.id, tier },
  },
  allow_promotion_codes: true,             // referral codes
  automatic_tax: { enabled: true },        // GST
  success_url: `${SITE}/dashboard?welcome=1`,
  cancel_url: `${SITE}/pricing`,
});
```

No card on the trial. For a $49–199 product aimed at people who have been burned
by auto-renewing subscriptions, requiring a card is worth more lost trials than
it saves in tyre-kickers.

### Webhook

Handle these and only these:

| Event | Action |
|---|---|
| `checkout.session.completed` | create/activate the subscription row |
| `customer.subscription.updated` | sync tier, status, period end |
| `customer.subscription.deleted` | mark canceled; keep the profile |
| `invoice.payment_failed` | `past_due`; start dunning |
| `invoice.payment_succeeded` | clear `past_due` |

**Three rules that will save you a bad week:**

1. **Verify the signature before parsing the body.** Use the raw body; Next.js
   will happily hand you a parsed one that fails verification.
2. **Insert into `billing_events` first, keyed on the Stripe event id.** The
   primary key gives you idempotency for free — Stripe retries, and a
   double-processed `subscription.deleted` cancels a paying customer.
3. **Return 200 fast, process after.** Stripe times out at 20 seconds and
   retries with backoff. Acknowledge, then do the work.

Never trust a `tier` value from the client. It comes from the Stripe price id
or it does not come at all.

---

## 5. The weekly email

This is the product. The dashboard is the upsell; the email is what people pay
for. It has to render on a five-year-old Android phone at 6am.

### Constraints

- **Table layout, inline CSS.** Outlook renders with Word's engine. No flexbox,
  no grid, no CSS variables, no web fonts.
- **Under 102 KB.** Gmail clips beyond that and hides your unsubscribe link,
  which is both a bad experience and a compliance problem.
- **One column, 600px.** Two columns collapse unpredictably.
- **Every project links to its detail page** with the project id, so opens can
  be attributed to interest in specific projects — which is how you learn what
  to score higher.
- **Real text, not an image.** An image-only email is a spam signal and is
  useless to anyone with images off, which is most people on mobile data.

### Structure

```
Subject:  Top electrical opportunities this week — 9 worth ringing
Preheader: [Builder] took out a CC on [address]. Plus 8 more across the Hunter.

┌─────────────────────────────────────────┐
│ TRADIESIGNAL          Issue 07 · 10 Sep │   navy bar, green rule
├─────────────────────────────────────────┤
│ Morning [name],                          │   personal line, merged
│ [one sentence about this week]           │
├─────────────────────────────────────────┤
│ THIS WEEK          9 worth ringing       │
│ 1,107 tracked · $1.22bn · 126 builders   │
├─────────────────────────────────────────┤
│ ▌HIGH PRIORITY                           │
│  ┌────────────────────────────────────┐  │
│  │ 100  Mixed use dev (280 dwellings) │  │
│  │      309 King St, Newcastle West   │  │
│  │      $80.3m · elec $7.2m–$12.0m    │  │
│  │      ▸ GWH BUILD PTY LTD           │  │
│  │      Why: CC lodged — packages     │  │
│  │      are being priced now          │  │
│  │      [View full brief →]           │  │
│  └────────────────────────────────────┘  │
│  … up to 5                               │
├─────────────────────────────────────────┤
│ ▌MEDIUM PRIORITY            (compact)    │
├─────────────────────────────────────────┤
│ ▌COMMERCIAL   ▌RESIDENTIAL   ▌GOVERNMENT │
├─────────────────────────────────────────┤
│ Anything you'd want ranked differently?  │   ← the retention line
│ Just reply.                              │
├─────────────────────────────────────────┤
│ Source: NSW Planning Portal, CC BY 4.0   │
│ Manage preferences · Unsubscribe         │
└─────────────────────────────────────────┘
```

### Subject lines

Test these. Specificity beats cleverness with this audience every time.

| Variant | Rationale |
|---|---|
| `Top electrical opportunities this week — 9 worth ringing` | the brief's line, plus a number |
| `9 Hunter jobs worth a phone call this week` | benefit-led |
| `GWH just took out a CC on King Street (+8 more)` | **specific — usually wins** |
| `$1.2bn of Hunter construction lodged this fortnight` | scale |

Never use the same subject twice; it trains people to skip.

### Sending rules

- **One digest per subscriber per period**, enforced by a unique index on
  `email_logs`, not by trusting the scheduler.
- **Suppression via `project_deliveries`.** A project is re-sent only when its
  stage advances. Nothing kills a weekly email faster than the same job three
  weeks running.
- **Send in the subscriber's local time**, from `profiles.timezone`.
- **If a subscriber has fewer than three matches**, widen the radius by 50% for
  that send and say so in the email: *"quiet week in your patch — widened to
  75km so this wasn't empty."* Honest, and better than an empty email.
- **Never send an empty digest.** Skip it and log why. An empty email is worse
  than no email.

---

## 6. Environment

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=          # server only — never NEXT_PUBLIC_

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
STRIPE_PRICE_STARTER=
STRIPE_PRICE_PROFESSIONAL=
STRIPE_PRICE_PREMIUM=

# Email
RESEND_API_KEY=
EMAIL_FROM="Tradiesignal <reports@tradiesignal.com.au>"
EMAIL_REPLY_TO="james@tradiesignal.com.au"   # a real inbox someone reads

# Analytics / errors
NEXT_PUBLIC_POSTHOG_KEY=
SENTRY_DSN=

# App
NEXT_PUBLIC_SITE_URL=https://tradiesignal.com.au
CRON_SECRET=                        # shared secret for cron endpoints
```

`EMAIL_REPLY_TO` must be a monitored human inbox. The single most valuable
retention mechanism in this business is that replying to the weekly email
reaches a person.
