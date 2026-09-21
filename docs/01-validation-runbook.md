# The manual runbook: validate before you build

**Read this first.** Everything else in this repository is the plan for a
software business. This document is the plan for finding out whether anyone
will pay for it, and it needs about three hours a week and no software at all.

The whole point: **the report already works.** The scripts in `src/` produced
Issue 01 from live government data in this session. You can sell that report on
Monday. Do not write a line of Next.js until at least ten people have paid for
something.

---

## Why manual first

The temptation is to build the platform, because the platform is the fun part.
Resist it, for three specific reasons:

1. **The riskiest assumption is not technical.** You already know the data
   exists and the pipeline works. What you do not know is whether a Newcastle
   electrician will pay $99 a month for it. No amount of Next.js answers that.
2. **The manual version teaches you the product.** The first five customers
   will tell you the scoring is wrong, that they only care about commercial, or
   that what they actually want is the builder list. Every one of those changes
   is a config edit now and a refactor later.
3. **A PDF sells better than a login.** A tradesperson will open a PDF on their
   phone at smoko. They will not create an account, choose a password, and
   configure a radius filter before they have any reason to trust you.

You need $10k–20k MRR. At $99, that is 100–200 customers. You do not need
software to get the first twenty.

---

## Weekly production: about 2.5 hours

Run it Sunday evening or Monday before 6am. Consistency matters more than the
day — people should know when it lands.

### Step 1 — Collect (10 minutes, mostly waiting)

```bash
cd tradiesignal
python3 src/collect_eplanning.py --days 120 --out data/raw
```

Pulls development applications, complying development certificates and
construction certificates for all five councils. Roughly 4,800 records; takes
about four minutes.

**Check before continuing.** Open `data/raw/manifest_YYYY-MM-DD.json` and
confirm every service returned a plausible count. A zero for a council that had
hundreds last week means the council name no longer matches the API's list —
not that nothing was lodged. Never publish off a silent zero.

### Step 2 — Score (under a minute)

```bash
PYTHONPATH=src python3 src/normalise_and_score.py
```

Writes `data/projects.json`, `data/projects.csv` and `data/summary.json`.
Read the console summary. Sanity checks:

- `projects_live` should be within about 10% of last week.
- `by_priority.high` should be somewhere between 20 and 80. If it is 300, a
  scoring change has gone wrong.
- The `cost_confidence` counts should show `suspect + unverified` under about
  2% of the total.

### Step 3 — Build the report (under a minute)

```bash
PYTHONPATH=src python3 src/report_data.py
PYTHONPATH=src python3 src/build_report.py
node src/export_pdf.cjs
```

Produces `reports/Tradiesignal_Hunter_Report.pdf` and `reports/report_web.html`.

### Step 4 — Read it like a customer (45 minutes)

**This is the step that cannot be skipped and the one you will want to skip.**

Open the PDF and read the "Ring these this week" section as if you were an
electrician deciding where to spend Tuesday. For every card, ask:

- Would I actually ring this? If not, why is it at the top?
- Is the builder name right, or is it a certifier that slipped through?
- Does the dollar figure pass the smell test?
- Is the suggested timing genuinely useful, or is it generic?

Fix what you find in `src/scoring_config.py` and re-run. Every fix compounds —
the model gets better every week for the first two months, then stabilises.

### Step 5 — Verify the top five by hand (30 minutes)

Take the five highest-scoring projects and look each one up on the council's DA
tracker. Confirm the status has not changed and the figure is real. If you find
an error, fix the validator, not just the row.

Search the project address and the builder name in the news. Twice now this has
turned a bare record into a story worth telling — the Steel River battery in
Issue 01 came from exactly this step, and cross-referencing it against the
Hunter New Energy coverage is what turned a line item into the report's
flagship entry.

Note anything worth adding to the **public pipeline** section in
`src/report_data.py`. That section is hand-compiled by design and is a large
part of what a subscriber is paying for.

### Step 6 — Send (20 minutes)

Weeks 1–8, while you are under about 30 subscribers, send them individually
from your own email. Not a mailing list. Individually.

```
Subject: Tradiesignal Issue 04 — 9 jobs worth ringing this week

Morning [name],

Issue 04 attached. Three things I'd look at first:

1. [Project] in [suburb] — [builder] has the CC. That's this week.
2. [Project] — [why it's unusual]
3. [Something specific to their business]

The [sector] section is thinner than last week; [honest reason].

Anything in here you'd want ranked differently?

[you]
```

That last line does the real work. It is a research interview disguised as a
sign-off, and the answers rebuild your scoring model.

At 30+ subscribers, move to Resend and keep the personal note as the first
paragraph, merged per subscriber.

### Step 7 — Log what happened (15 minutes)

Keep one spreadsheet. Not a CRM.

| Column | Why |
|---|---|
| Issue number, date sent | |
| Subscriber, tier, start date | |
| Opened? Replied? | replies matter far more than opens |
| Projects they asked about | tells you what to score higher |
| Feedback verbatim | you will misremember it otherwise |
| Cancelled? Reason? | the single most valuable column |

---

## Selling it: the first ten

### Pricing during validation

Charge from the first customer. A free pilot tells you nothing about
willingness to pay, and converting free users to paid later is harder than
selling to a cold prospect.

- **Founding subscriber: $49/month, locked for 12 months.** Frame it honestly:
  it is early, it is manual, the price reflects that, and it never goes up for
  them. Cap it at the first 20 and say so.
- Take payment by Stripe payment link. No product needed — one link, one price.
- Month to month. Cancel by replying to any email. Mean it.

### Where the first ten actually come from

In rough order of how well they work:

**1. Your own network, and one degree out.** If you know anyone in Hunter
construction, start there. Ten calls to people who already know you beats a
hundred cold emails.

**2. The report itself as the cold outreach.** This is the strongest play
available and it is specific to this product. For each target:

- Look up their business in the data. Find a project within 5km of their base
  that they probably do not know about.
- Send them that one project. Not the report. One project.

```
Subject: 40-unit job on [street], [suburb] — CC issued last week

[Name], you're based in [suburb] so this is probably in your patch.

[Builder] took out a construction certificate on [address] on [date].
[$X]m, [N] dwellings. Electrical on a job that size is usually
somewhere between $[low] and $[high].

Council's got it as [reference] if you want to check it.

I pull this out of the NSW planning data every week for the five Hunter
councils and put it in a report. Happy to send you this week's if it's
useful — no charge, no sign-up.

[you]
```

You are giving away one lead to prove you have more. It costs you nothing and
it is impossible to ignore, because it is about their suburb and their money.

**3. Facebook groups.** *Sparkies Australia*, *Electricians Australia*,
*Newcastle Tradies*, *Hunter Valley Trades & Services*. Read the group rules
before posting; several ban promotion outright. The post that works is not an
ad, it is data:

> Pulled the construction certificates for Newcastle, Lake Mac, Maitland, Port
> Stephens and Cessnock for the last fortnight. 180 CCs issued, $76m of work,
> and 126 of them name the builder. Busiest suburbs were [X], [Y], [Z].
> Happy to post the top 10 if anyone wants it.

Then post the top 10 when asked. The subscription conversation happens in DMs
afterwards, started by them.

**4. Industry bodies.** NECA NSW and Master Electricians Australia both run
Hunter branch events. Do not sponsor anything yet. Go, listen, and talk to
people. A single conversation with a branch organiser is worth more than a
logo on a banner.

**5. Wholesalers.** Middendorp, Lawrence & Hanson, MM Electrical and CNW all
have Newcastle trade counters, and the counter staff know every contractor in
town by name. A stack of printed reports at the counter with your number on it
costs about $40 and reaches exactly the right people at 6:30am.

**6. Local suppliers and adjacent trades.** Air conditioning installers, solar
installers and data cablers see the same jobs. Some will subscribe; some will
refer.

### Handling the objection you will actually get

> *"Can't I just look this up myself?"*

Yes, and say so immediately. The honest answer is the persuasive one:

> Completely. It's public data — five council trackers plus the NSW portal.
> Takes about two hours a week if you know where to look and what you're
> looking for. I do it once for everyone and charge $49. If you'd rather do it
> yourself, the councils' DA trackers are the place to start, and I mean that.

Never pretend the data is proprietary. Newcastle is small, someone will check,
and you will have destroyed the only asset you have.

---

## What "validated" looks like

Do not build the platform until **all** of these are true:

| Gate | Threshold |
|---|---|
| Paying subscribers | 10+ |
| Paid for | 2+ consecutive months |
| Churn | under 2 of the first 10 |
| Unprompted "this was useful" replies | 3+ |
| Someone referred someone | at least once |
| A subscriber has told you about work they won | at least once |

That last one is the real gate. Until a customer can point at a job and say
they heard about it here, you have sold a subscription to a document, not a
business outcome.

**If you cannot get to ten in eight weeks, the problem is not the software.**
It is the offer, the price, or the market. Change one of those before you write
code. The most likely culprits, in order:

1. You are selling to electricians who are already full. Target the ones
   growing, or the ones trying to move from domestic into commercial.
2. $49 is not the objection — relevance is. Fewer, better-matched projects beat
   a longer list.
3. The report is arriving without a human attached to it.

---

## What to automate first, and in what order

Only after the gates above are met. Automate in the order of what hurts most:

1. **Sending.** Resend plus a merge template. Saves 20 minutes a week and stops
   you forgetting someone.
2. **Collection.** A cron job on any cheap box that runs steps 1–3 overnight
   and emails you the PDF. Saves 15 minutes and removes the Sunday-night
   dependency on you being home.
3. **Self-serve signup.** Stripe Checkout plus a Supabase table. Only once you
   are turning away people because onboarding is manual.
4. **The dashboard.** Last. It is the most work and the least proven. Several
   subscribers must have asked for it before you build it.

The full architecture in `docs/` is waiting when you get there. It is not
urgent, and it will be better for the eight weeks of customer conversation you
had first.
