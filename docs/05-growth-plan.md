# Customer acquisition: getting to 100 paying subscribers

---

## 1. How big is this market, really?

This matters more than it looks, because it determines whether 100 subscribers
is ambitious or trivial, and therefore how hard you should push on price versus
volume.

**I could not find a verified count of electrical contracting businesses in the
Hunter.** IBISWorld holds the industry figure behind a paywall and blocks
automated access; the ABS *Counts of Australian Businesses* release has the
data at ANZSIC and SA4 level but not in a form I could retrieve here. So this
is a bottom-up estimate with the method shown, and **verifying it is a day-one
task** — the ABS release and the NSW Fair Trading public licence register will
both settle it in an afternoon.

| Step | Figure | Basis |
|---|---|---|
| Hunter region population | ~700,000 | Newcastle + Lake Macquarie + Maitland + Port Stephens + Cessnock |
| Share of Australian population | ~2.6% | ~27m national |
| Australian electrical services businesses | ~35,000–40,000 | industry order of magnitude — **verify** |
| Implied Hunter businesses | **~900–1,050** | population share |
| Of which are one-person domestic operators | ~60% | typical trade distribution |
| **Realistic addressable market** | **~350–420 businesses** | 2+ vans, or a sole trader actively chasing commercial |

Against ~400 addressable businesses, **100 subscribers is a 25% penetration
rate.** That is high but not absurd for a niche B2B tool in a geographically
tight market where everyone knows everyone — and word of mouth in a trade
community is unusually strong.

Two conclusions follow:

1. **Word of mouth has to work.** You cannot buy your way to 25% penetration on
   a $99 product with paid ads. The referral loop is not a nice-to-have.
2. **Get the average revenue per user up, or expand geographically, or both.**
   100 Starter subscribers is $4,900 MRR, which misses the target. The plan
   below is built on a Professional-weighted mix.

If verification shows the addressable market is closer to 200, the answer is to
expand to the Central Coast sooner, not to discount.

---

## 2. Revenue model

### Getting to $10k–20k MRR

| Milestone | Starter $49 | Professional $99 | Premium $199 | Subs | MRR | ARR |
|---|---|---|---|---|---|---|
| Month 1 | 4 | 1 | 0 | **5** | $295 | $3.5k |
| Month 3 | 12 | 7 | 1 | **20** | $1,480 | $17.8k |
| Month 6 | 25 | 20 | 5 | **50** | $4,200 | $50.4k |
| Month 12 | 40 | 45 | 15 | **100** | $9,400 | $112.8k |
| Month 18 (Central Coast) | 55 | 75 | 25 | **155** | $15,095 | $181.1k |
| Month 24 (+ Wollongong) | 70 | 105 | 40 | **215** | $21,785 | $261.4k |

**The brief's $10k–20k MRR target is not reachable at 100 subscribers on this
price list.** 100 subscribers at a realistic mix is about $9,400. Say that out
loud now rather than discovering it in month eleven. Three ways to close the
gap, in order of preference:

1. **Expand coverage.** Central Coast at month 12–15 roughly doubles the
   addressable market for the same pipeline. This is the answer.
2. **Shift the mix.** Every subscriber moved from Starter to Professional adds
   $50. Getting the mix from 40/45/15 to 20/55/25 takes the same 100
   subscribers to $11,400. The builder watchlist is the lever — it is the
   feature people upgrade for.
3. **Add a higher tier.** A $399 "Enterprise" for the handful of Hunter
   contractors with estimating teams — more seats, API access, custom
   territory reports. Five of those is another $1,995, which with the shifted mix reaches $13,395.

Do not close it by raising Starter. $49 is the price that gets a nervous sole
trader to try it, and that is where referrals come from.

### Unit economics

| Metric | Assumption | Note |
|---|---|---|
| Blended ARPU | $94 | at the month-12 mix |
| Gross margin | ~97% | infrastructure is ~$80/month total |
| Target CAC | under $150 | ~1.6 months of revenue |
| Payback | under 2 months | |
| Monthly churn target | under 4% | trade SaaS typically 3–6% |
| Implied lifetime | ~25 months | at 4% |
| **LTV** | **~$2,300** | |
| **LTV:CAC** | **~15:1** | healthy; if you are seeing 3:1, something is wrong |

**Churn is the number that decides this business.** At 4% monthly you keep
about 62% of a cohort through a year. At 8% you keep 37%, and you will spend
every month replacing customers instead of growing. Watch it weekly from
subscriber one, and treat every cancellation as a research interview.

---

## 3. The phases

### Phase 1 — Months 1–2: ten paying customers, no software

Covered in full in `docs/01-validation-runbook.md`. In short: hand-built
reports, sent individually, sold with a single real project as the hook.

Target: **10 subscribers, $500 MRR.** Channels: personal network, one-project
cold email, Facebook groups, wholesaler counters.

The metric that matters is not subscriber count. It is **how many people reply
to the email**. If nobody replies, they are not reading it, and they will churn
in month three whatever the number says.

### Phase 2 — Months 3–5: twenty to fifty, semi-automated

Automate sending and collection. Build self-serve signup with Stripe Checkout.
No dashboard yet.

New channels:

**Referral program.** One month free for both sides, for any referral that
converts and stays 30 days. In a trade community this is the highest-yield
channel available and it costs you nothing until it works. Make it a single
line at the bottom of every report: *"Know a sparky who'd use this? Forward it.
If they subscribe you both get a month free."*

**Google Ads, small and surgical.** $600–900/month, exact match only:

| Keyword | Intent |
|---|---|
| `electrical tenders nsw` | high |
| `construction projects newcastle` | medium |
| `development applications newcastle` | medium |
| `commercial electrical work newcastle` | high |
| `newcastle building approvals` | medium |
| `find construction leads australia` | high |

Send them to a landing page that leads with the sample report, not the pricing
table. Expect $4–9 a click and a 3–6% conversion to trial. Kill any keyword
that has not produced a trial in 60 clicks.

**Content and SEO.** Starts here, pays off in Phase 3. See
`docs/06-seo-content.md`.

**Industry bodies.** NECA NSW Hunter branch and Master Electricians Australia.
Offer to present a 15-minute "what got approved in the Hunter this quarter"
segment at a branch meeting. You are not selling; you are being the person with
the data. Sponsorship comes later, if at all.

Target: **50 subscribers, $4,200 MRR by month 6.**

### Phase 3 — Months 6–12: fifty to a hundred, product-led

Dashboard, saved searches, alerts, builder watchlist. Now the product can be
sold on a free trial without you in the loop.

**The trial has to be instrumented.** Fourteen days, no card. The activation
event is not signup — it is *opening a project detail page and then coming
back*. Track it and email anyone who has not.

**Wholesaler partnerships.** By now you have a track record. Approach
Middendorp, L&H, MM Electrical and CNW with a co-branded quarterly Hunter
construction report for their trade counters. They get content, you get
distribution to exactly your market at zero cost.

**Local sponsorship, chosen carefully.** A Newcastle trades footy team or a
NECA branch event, not a billboard. Budget $2,000–4,000 a year, and only for
things you will physically attend.

**Adjacent trades.** Solar installers, air conditioning, data cablers and fire
services all want this data. The pipeline is identical; only the scoring
weights and scope library change. That is a config file, not a rebuild — see
`ELECTRICAL_SHARE` and `SCOPE_LIBRARY` in `src/scoring_config.py`. A "Tradiesignal
for solar" is a fortnight's work once the platform exists, and it doubles the
market without doubling the cost.

Target: **100 subscribers, $9,400 MRR by month 12.**

### Phase 4 — Months 12–24: geography

Central Coast first: same data source, adjacent market, plenty of Hunter
contractors already work down there. Then Wollongong, then Sydney by region.

Sydney is a different proposition — far bigger, far more competitive, and the
"everyone knows everyone" referral loop does not work at that scale. Do not
treat it as five Newcastles.

---

## 4. Channel summary

| Channel | Cost | Realistic CAC | Volume | Start |
|---|---|---|---|---|
| Personal network | $0 | $0 | 3–8 total | Week 1 |
| One-project cold email | time | ~$40 | 2–5/month | Week 1 |
| Facebook groups | $0 | ~$20 | 1–4/month | Week 2 |
| Referral program | 2 months revenue | ~$100 | scales with base | Month 3 |
| Google Ads | $600–900/mo | $120–200 | 4–8/month | Month 3 |
| SEO and content | time | falls to ~$30 | 0 → 10/month | Month 3, pays month 9 |
| Industry bodies | $0–2k | ~$150 | 1–3/month | Month 4 |
| Wholesaler counters | ~$50/mo | ~$60 | 1–3/month | Month 2 |
| Sponsorship | $2–4k/yr | ~$300 | 1–2/month | Month 8 |
| Adjacent trades | config work | ~$100 | new segment | Month 12 |

---

## 5. Retention, which matters more than any of the above

Acquisition gets attention; retention decides whether this is a business. Five
things to build in from the start:

**1. Make the email indispensable, not comprehensive.** Twelve projects someone
will actually ring beats two hundred they will scroll past. When in doubt, cut.

**2. Show them what they would have missed.** Once a quarter, send a "you found
this here" email listing projects from previous issues that have since gone to
construction. This is the single strongest retention artefact available and it
costs nothing but a query.

**3. Ask, every month, in one line.** *"Anything in here you'd want ranked
differently?"* People who answer do not churn. People who never answer are
already gone.

**4. Handle the seasonal dip honestly.** Trade work slows over Christmas and
people cancel things in January. Offer a pause, not a cancellation, in
December. A paused subscriber comes back; a cancelled one does not.

**5. When someone cancels, ask one question.** Not a survey. *"Fair enough —
what would have made it worth keeping?"* Log the verbatim answer. Twenty of
those answers is your product roadmap.

---

## 6. Metrics to run the business on

Weekly, on one page:

| Metric | Target | Why |
|---|---|---|
| New trials | 8–12 | leading indicator |
| Trial → paid | >35% | below 25% means the trial is not showing value fast enough |
| Email open rate | >55% | trade audiences open genuinely useful email at high rates |
| Email reply rate | >8% | **the real health metric** |
| Dashboard weekly actives | >60% of subs | |
| Monthly churn | <4% | |
| MRR growth | >12%/month early | |
| Referrals sent | >0.3 per subscriber per quarter | |

If you track only one: **email reply rate.** Everything else is downstream of
whether people find it useful enough to answer.

---

## 7. The risks worth naming

| Risk | Likelihood | Impact | What to do about it |
|---|---|---|---|
| The NSW API changes or closes | low | fatal | The data is CC-BY and mandated for all councils; still, keep every raw payload and build a scraper fallback for the DA trackers before you need one |
| Someone copies it | medium | moderate | The data is public and cannot be fenced. The defensibility is the accumulated builder history, the calibrated scoring, and being the known name in a small town — none of which copy quickly |
| Market is smaller than estimated | medium | high | Verify with ABS and the Fair Trading register in week 1. If it is 200, expand geographically earlier |
| Churn runs at 8% | medium | high | Retention section above. Watch weekly from subscriber one |
| An incumbent adds this | low | high | Cordell, BCI and Estimate One already sell construction leads at $2,000–10,000/year to large contractors. They are not going to fight over a $99 product for Hunter sparkies — that is the whole opening |
| You get bored of Sunday nights | **high** | fatal | Automate collection and sending by month 3, before enthusiasm runs out |

That last one is the real risk and it is not a joke. Manual businesses die of
operator fatigue far more often than of market failure. The runbook exists to
get you to ten customers, not to be your life.
