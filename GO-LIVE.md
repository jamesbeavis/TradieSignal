# Go live: tradiesignal.com

You have the domain. Here is exactly what to do with the files, in order.

---

## 0. What you actually have

| Folder | What it is | Do you need it now? |
|---|---|---|
| `deploy/` | **Complete standalone site.** Drag into Netlify. | **Yes — today** |
| `reports/` | The sellable PDF and its web version | **Yes — today** |
| `src/` | The pipeline that regenerates everything | **Yes — weekly** |
| `data/projects.csv` | 3,964 scored projects for prospecting | **Yes — this week** |
| `docs/` | Runbook, sales kit, strategy | Read 01 and 02 now, the rest later |
| `sql/`, `supabase/` | The platform build | **Not for months** |

The important thing to internalise: **`sql/` and `supabase/` are not the next
step.** They are the plan for month three onward. The next step is selling a
PDF you already have.

---

## 1. Get the site up (about 40 minutes)

You already work this way with GitHub and Netlify, so this is the familiar path.

### 1a. Repo

```bash
cd tradiesignal
git init
git add .
git commit -m "Tradiesignal: pipeline, site and strategy"
gh repo create tradiesignal --private --source=. --push
```

Keep it **private**. The scoring model and the sales kit are the only
proprietary things here, and there is no upside to publishing them.

Add a `.gitignore` first:

```
data/raw/
node_modules/
__pycache__/
.env
```

`data/raw/` is ~7MB of API snapshots that regenerate in four minutes. No point
versioning them.

### 1b. Netlify

Netlify → **Add new site → Import an existing project** → pick the repo.

| Setting | Value |
|---|---|
| Build command | *(leave empty)* |
| Publish directory | `deploy` |

`netlify.toml` in the repo root already sets this, plus security headers and
three redirects. It should just pick it up.

### 1c. DNS at GoDaddy

Two options. **Take the first one** unless you have a reason not to.

**Option A — Netlify DNS (recommended).** In Netlify, add the custom domain
`tradiesignal.com`, then choose "Set up Netlify DNS". Netlify gives you four
nameservers. In GoDaddy: *My Products → Domains → tradiesignal.com → DNS →
Nameservers → Change → I'll use my own* and paste all four.

This is more resilient than the alternative, handles the apex properly, and
provisions HTTPS automatically.

**Option B — keep GoDaddy DNS.** GoDaddy does not support ALIAS/ANAME records,
so you need the A-record fallback:

| Type | Host | Value |
|---|---|---|
| A | `@` | `75.2.60.5` |
| CNAME | `www` | `<your-site>.netlify.app` |

Delete GoDaddy's default parking records first — the `@` A record pointing at
their park page, and any `www` CNAME to `_domainconnect`. Leaving them there is
the most common reason this appears not to work.

Either way: allow up to 24 hours for propagation, though it is usually under
an hour. Netlify provisions the Let's Encrypt certificate once DNS resolves.

### 1d. Check it

- `https://tradiesignal.com` → landing page
- `https://tradiesignal.com/sample-report/` → the report, with a download button
- `https://tradiesignal.com/demo/` → the dashboard
- Open the sample report link on your phone. That is how most people will see it.
- Paste the sample-report link into a WhatsApp or Messenger chat with yourself
  and check the preview card renders. That preview is doing a lot of work when
  someone forwards it into a trade group.

---

## 2. The money plumbing (about an hour, do it before you pitch anyone)

**You cannot take payment without an ABN.** If you do not have one, apply free
at abr.gov.au — usually issued immediately.

Then:

1. **Stripe account**, Australian entity, ABN on file.
2. **Two payment links**, not a full Checkout integration:
   - *Founding subscriber* — $49/month recurring
   - *Professional* — $99/month recurring
   Stripe Dashboard → Payment links → recurring. Takes ten minutes.
3. **Turn on Stripe Tax** for GST handling.
4. Rebuild the site with the real link so the buttons work:

```bash
python3 src/build_site.py --domain tradiesignal.com --checkout https://buy.stripe.com/xxxxx
git commit -am "wire checkout" && git push
```

Netlify redeploys on push.

### On GST

You only *must* register for GST above $75k turnover. Below that it is
optional, and staying unregistered means you do not charge GST and do not lodge
BAS — simpler while you are small. Worth ten minutes with an accountant before
you set prices, since it changes whether $49 is $49 or $53.90. **I am not an
accountant and this is not tax advice** — but it is the specific question to
ask.

### On .com versus .com.au

`.com` is fine and it is what you have. Two things worth knowing:

- For a Newcastle trade audience, `.com.au` carries genuine trust weight —
  it signals a local business rather than a random website.
- `.com.au` requires an ABN, which you will have anyway for Stripe.

So once the ABN is issued, consider grabbing `tradiesignal.com.au` for ~$20/yr
and 301-redirecting it to the `.com`. It is cheap insurance against a
competitor taking it, and you can switch which one is canonical later. Not
urgent. Not a blocker.

---

## 3. Verify the market (half a day, this week)

The single number I could not confirm is how many electrical contracting
businesses are in the Hunter. My estimate of ~400 addressable businesses makes
100 subscribers a 25% penetration rate — high but plausible. If the real number
is 200, the whole plan changes and you expand to the Central Coast much sooner.

Two free sources settle it:

- **ABS Counts of Australian Businesses**, filtered to ANZSIC E3232 (Electrical
  Services) and the Hunter Valley / Newcastle & Lake Macquarie SA4s.
- **NSW Fair Trading public licence register** — searchable by licence class
  and postcode.

Do this before you spend money on ads. It is the cheapest way to find out
whether the plan is sized correctly.

---

## 4. Send the first ten emails (this week)

This is the actual business. Everything above is preparation.

```bash
# Highest-scoring projects with a named builder, closest to Newcastle
python3 - <<'PY'
import csv
rows = [r for r in csv.DictReader(open('data/projects.csv'))
        if r['builder'] and r['priority_label'] in ('High priority','Medium priority')]
rows.sort(key=lambda r: -int(r['opportunity_score']))
for r in rows[:25]:
    print(f"{r['opportunity_score']:>3} {r['suburb']:<22} {r['builder'][:34]:<34} ${float(r['cost'] or 0):>12,.0f}  {r['project_name'][:44]}")
PY
```

Pick ten electricians. For each, find a project within about 5km of them, and
send the one-project email from `docs/02-sales-kit.md §1`. Not the report. One
project.

The template is already filled in with a real example — 309 King Street,
Newcastle West, GWH Build, CFT-1024947 — so you can see exactly what a good one
looks like.

**Target: ten sent by Friday.** Not ten subscribers. Ten sent.

---

## 5. The weekly rhythm

Every Sunday evening or Monday before 6am:

```bash
cd tradiesignal
./run_weekly.sh                                    # ~6 minutes
python3 src/build_site.py --domain tradiesignal.com --checkout <link>
git commit -am "issue $(date +%Y-%m-%d)" && git push
```

Then read the report as a customer, fix anything wrong in
`src/scoring_config.py`, re-run, and send it.

`docs/01-validation-runbook.md` has the full version, including the checks that
matter and the ones you can skip.

---

## 6. Honest caution

You are running a demanding transformation program by day. The failure mode for
this kind of business is not the market and it is not the technology — it is
week seven, when Sunday night comes around and you cannot face it.

Two things protect against that:

1. **Automate collection early.** Even a cron job on a cheap VPS that runs
   `run_weekly.sh` overnight and emails you the PDF removes the "I have to be
   home to do this" dependency. That is a two-hour job and it buys you months.
2. **Ten customers is the gate, and it is deliberately low.** If ten people are
   paying and replying by week eight, it is real and worth continuing. If they
   are not, stop — and you will have spent eight weekends, not eight months.

The report works. The data is real and free. The thing that is unproven is
whether Hunter electricians will pay for it, and the only way to find that out
is to ask ten of them this week.
