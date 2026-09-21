# Auto-refresh: how the site keeps itself current

The site now updates itself. A GitHub Action collects the latest NSW planning
data every Sunday night, rescores it, rebuilds the pages, and commits. Netlify
is watching the repo, so the commit *is* the deploy.

This is the thing that removes the "I have to be home on Sunday night"
dependency, which is the most likely way this business dies.

---

## 1. What changed

**The dashboard no longer carries its data inside the HTML.** It used to be a
single 1.16 MB page with ~1,500 projects baked into the markup. Now:

| File | Size | Changes each refresh? |
|---|---|---|
| `deploy/demo/index.html` | 34 KB | rarely — only when the UI changes |
| `deploy/data/dashboard.json` | 1.13 MB | yes, every refresh |

The page fetches the JSON on load. Three things this buys:

1. **The page loads immediately** instead of parsing a megabyte of inline data.
2. **A refresh replaces one file**, so git history stays far smaller than it
   would if a 1.16 MB HTML document changed weekly.
3. **The page can tell the reader how old the data is** — because the date
   arrives with the data rather than being frozen into the markup at build time.

The self-contained build still exists. `python3 src/build_dashboard.py` with no
arguments produces the old single-file version, which is what you want for
publishing as a standalone artifact or emailing to someone.

**Both pages now show their own freshness.** The dashboard header reads *"Data
current as at 20 September 2026"*, and the sample report header says *"Compiled
20 September 2026"*. If the data goes stale — more than 14 days for the
dashboard, 21 for the report — the date turns amber and says how many days old
it is.

That last part matters more than it looks. A stale site that *looks* current is
worse than one that admits it, because a subscriber will ring a builder about a
job that was let a month ago and conclude the product is rubbish.

---

## 2. Setting it up

### 2a. The repo has to hold the whole project

The Action runs the Python pipeline, so it needs `src/`, not just the built
site. If your repo currently contains only `tradiesignal-site/`, replace its
contents with the full project (the tarball), which includes:

```
.github/workflows/refresh-data.yml    the Action
netlify.toml                          publish = "deploy"
src/                                  the pipeline
deploy/                               the built site  ← Netlify serves this
data/                                 scored output
```

Then in Netlify → Site configuration → Build & deploy, set **Publish
directory** to `deploy`. (The bundled `netlify.toml` already says this; the UI
setting is belt and braces.)

### 2b. Two repository variables

Settings → Secrets and variables → Actions → **Variables** tab:

| Name | Value | Why |
|---|---|---|
| `SITE_DOMAIN` | `tradiesignal.com` | canonical URLs, sitemap, Open Graph tags |
| `CHECKOUT_URL` | your Stripe payment link | wires up every "Start free trial" button |

These are *variables*, not secrets — they appear in the built HTML anyway.
Neither is required; without them the build falls back to `tradiesignal.com`
and an on-page `#pricing` anchor.

### 2c. Check Actions can write

Settings → Actions → General → Workflow permissions → **Read and write
permissions**. Without this the Action builds everything correctly and then
fails on the push, which is a confusing way to spend twenty minutes.

### 2d. Run it once by hand

Actions tab → *Weekly data refresh* → **Run workflow**. Takes about six
minutes. Watch the summary at the end — it prints the project count, verified
value and the most active builders, which is also a decent weekly read.

---

## 3. What it does, step by step

```
Sunday 18:00 UTC  (Monday 04:00 AEST)
        │
        ├─ collect      3 services × 5 councils from the NSW ePlanning API
        │
        ├─ GUARD        refuse to continue if the collection looks broken
        │               ← this is the important one, see §4
        │
        ├─ score        normalise, link, validate costs, classify, score
        ├─ report data  build the fortnightly slices
        ├─ render       report (print + web), landing page, dashboard + JSON
        ├─ PDF          Chromium print-to-PDF
        ├─ site         assemble deploy/ with canonical URLs and CTAs
        │
        ├─ SANITY       refuse to publish undersized or missing output
        │
        └─ commit+push  → Netlify deploys automatically
```

If nothing has changed — no new lodgements — the Action notices, skips the
commit, and exits quietly. No empty deploys.

---

## 4. The two guards, and why they exist

### The silent-zero guard

This is the failure mode that would actually happen. A misspelled council name,
a renamed council, or a moved endpoint returns **HTTP 200 with zero records** —
not an error. Without a guard, the pipeline would cheerfully score an empty
dataset, build a site with nothing on it, commit, and deploy. The site would go
blank and the Action would report success.

So before anything else runs, the Action checks record counts against floors:

| Service | Floor | Typical (120 days, 5 councils) |
|---|---|---|
| `OnlineDA` | 300 | ~2,000 |
| `OnlineCDC` | 150 | ~1,280 |
| `OnlineCC` | 150 | ~1,430 |

The floors sit far below normal variation, so ordinary quiet weeks never trip
them, but a broken feed always does. Below the floor, the run fails and **the
site keeps showing last week's data** — which is the correct behaviour. Stale
and honest beats blank and confident.

### The build sanity check

After the site is assembled and before anything is committed, it checks each
output file exists and is a plausible size, and that the dashboard JSON holds
at least 200 rows. This catches a half-written file or a template that silently
rendered empty.

### The failure alert

If either guard fires, a second job opens a GitHub issue labelled
`data-refresh` with a link to the run and the three most likely causes,
including the exact `curl` command to test the API by hand. If an issue is
already open it comments on that one rather than stacking up a new issue every
week.

Without this, a failure only appears in the Actions tab, which nobody checks.

---

## 5. Changing the cadence

The cron line is in `.github/workflows/refresh-data.yml`:

```yaml
- cron: '0 18 * * 0'    # Sunday 18:00 UTC = Monday 04:00 AEST
```

| Want | Cron | Trade-off |
|---|---|---|
| Weekly (current) | `0 18 * * 0` | ~50 MB of repo growth a year. Matches the business rhythm. |
| Twice weekly | `0 18 * * 0,3` | ~100 MB/year. Reasonable if the dashboard becomes a selling point. |
| Daily | `0 18 * * *` | ~350 MB/year. The data genuinely updates daily, but the repo gets heavy and the benefit is marginal while the email is the product. |

**Times are UTC.** During daylight saving (October to April) Sydney is UTC+11,
so the same cron fires at 05:00 rather than 04:00. Both are well before anyone
looks at the site, so it is not worth engineering around.

If you go daily, consider skipping the PDF on non-Mondays — it is the largest
file and it changes every run. The workflow already accepts a `skip_pdf` input
for manual runs; making it conditional on the day is a two-line change.

### Cost

GitHub Actions gives 2,000 free minutes a month on private repos. A weekly run
uses about **25 minutes a month**. Even daily is only ~180. This is free in
practice.

---

## 6. Keeping the repo from growing forever

Every refresh commits a new `deploy/data/dashboard.json` (~1.1 MB) and, weekly,
a new PDF (~800 KB). Git stores each as a new blob — JSON and PDF do not delta
well.

At weekly cadence that is roughly 50 MB a year, which is fine and needs no
action. If you go daily and the repo gets uncomfortable after a couple of
years, the simplest fix is to squash the history:

```bash
git checkout --orphan fresh
git add -A
git commit -m "Squash history"
git branch -D main && git branch -m main
git push -f origin main
```

You lose the commit history of the *data*, which has no value — the raw
snapshots were never committed anyway, and every figure is reproducible by
re-running the collector.

---

## 7. What is still manual, and should be

The Action refreshes **data**. It does not:

- **Write the public pipeline section.** The state and federally funded
  projects in the report are hand-compiled from the NSW Budget papers and
  agency announcements, and every row needs a source. That is in
  `src/report_data.py` under `PUBLIC_PIPELINE`. Review it quarterly.
- **Send the weekly email.** Still yours, and should stay yours until at least
  thirty subscribers — the personal first line is what gets replies, and
  replies are the metric that predicts churn.
- **Read the report as a customer.** The most valuable fifteen minutes of your
  week. The Action cannot tell you that the top project is a job nobody would
  ring about; only reading it can.

The automation buys back the mechanical two hours. It does not buy back the
judgement, and you should not want it to.
