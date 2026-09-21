# SEO and content strategy

---

## 1. The strategic bet

Almost nobody searches "electrical project opportunities Newcastle". The
category does not exist in people's heads, so there is no meaningful demand to
capture on the money keyword.

What people *do* search is the underlying question: **"what's being built in
Newcastle?"** — asked by electricians, builders, suppliers, property people and
locals. That query has real volume, and Tradiesignal is the only site in the
region that can answer it with current, structured, comprehensive data.

So the strategy is not to rank for the product. It is to **become the reference
source for Hunter construction activity**, and convert a small slice of that
traffic into subscribers.

Three consequences:

1. **Programmatic pages built from the database are the main engine**, not blog
   posts. There are hundreds of council × suburb × sector combinations, each
   with genuinely unique data that updates weekly. That is defensible in a way
   an article never is.
2. **The free layer has to be genuinely useful.** A programmatic page showing
   nothing until you sign up will not rank and will not earn links.
3. **Links come from being cited**, by the Newcastle Herald, Newcastle Weekly,
   local property blogs and industry newsletters. Quarterly data releases are
   what earn those citations.

---

## 2. Site architecture

```
/                                    Landing page
/pricing
/sample-report                       Ungated. The core conversion asset.
/dashboard                           App (noindex)

/construction/                       HUB: "What's being built in the Hunter"
  /construction/newcastle            council pages, updated weekly
  /construction/lake-macquarie
  /construction/maitland
  /construction/port-stephens
  /construction/cessnock

/development-applications/           HUB: approvals explained + live data
  /development-applications/newcastle
  /development-applications/<suburb>       ~60 suburb pages, top LGAs only

/builders/                           HUB: who is building in the Hunter
  /builders/<builder-slug>           from the builders table

/sectors/
  /sectors/commercial-construction-newcastle
  /sectors/industrial-construction-hunter
  /sectors/residential-development-hunter
  /sectors/government-projects-hunter
  /sectors/energy-projects-hunter

/tenders/
  /tenders/electrical-nsw
  /tenders/hunter-government-contracts

/for/                                Audience pages
  /for/electricians
  /for/solar-installers
  /for/data-cablers
  /for/air-conditioning

/guides/                             Evergreen explainers
/reports/                            Quarterly data releases — the link magnets
/blog/
```

**Rule for programmatic pages:** never publish one with thin data. A suburb
with three approvals in the last quarter gets folded into its council page. A
few hundred substantial pages beat a thousand thin ones, and thin
programmatic pages are the fastest way to a site-wide quality problem.

---

## 3. Target pages: titles, meta, intent

| URL | Title tag | Meta description | Primary keyword | Intent |
|---|---|---|---|---|
| `/` | Tradiesignal — Find Electrical Work Before Your Competition \| Newcastle NSW | Council approvals, construction certificates and government projects across the Hunter, scored and delivered weekly. See who's building and who to call. 14-day free trial. | newcastle electrician leads | commercial |
| `/construction/newcastle` | What's Being Built in Newcastle — Live Construction Activity | Every development application and construction certificate lodged with Newcastle City Council, updated weekly. Project values, stages and builders. | construction projects newcastle nsw | informational |
| `/development-applications/newcastle` | Newcastle Development Approvals — Updated Weekly | Recent DAs approved by Newcastle City Council with values, addresses and status. Free to browse, sourced from the NSW Planning Portal. | development approvals newcastle | informational |
| `/builders/` | Who's Building in the Hunter — Builder Activity Index | The construction companies with the most active certificates across Newcastle, Lake Macquarie, Maitland, Port Stephens and Cessnock. | newcastle builders list | informational |
| `/builders/<slug>` | \<Builder> — Current Hunter Projects and Activity | Construction certificates and approvals recorded for \<Builder> across the Hunter, with values and locations. Updated weekly. | \<builder name> projects | navigational |
| `/sectors/commercial-construction-newcastle` | Commercial Construction Pipeline — Newcastle & Hunter | Commercial developments approved or under certificate across the Hunter, with estimated electrical scope and value. | commercial construction newcastle | informational |
| `/tenders/electrical-nsw` | Electrical Tenders NSW — Current Government Opportunities | Government electrical contracts and maintenance tenders open to NSW contractors, filtered for the Hunter. | electrical tenders nsw | **high commercial** |
| `/for/electricians` | Construction Leads for Electricians — Newcastle & Hunter | Stop searching twenty council websites. One weekly email with the jobs worth ringing about, the builder's name and when to call. | electrical contracts newcastle | **high commercial** |
| `/sample-report` | Sample Report — Hunter Electrical Opportunity Report | See a real issue: every approval across five Hunter councils, scored and turned into a call list. No sign-up. | (branded / conversion) | commercial |
| `/guides/how-to-find-building-projects-before-they-start` | How to Find Building Projects Before Construction Starts | The public data sources that show you a job months before the builder appoints trades — and how to read them. | find construction projects before they start | informational |

### Title conventions

- Under 60 characters where possible; the important words first.
- "Newcastle" or "Hunter" in every local page title. This is a geo play.
- No year in evergreen titles — it dates the page and forces annual rewrites.
  Put "Updated weekly" in the meta description instead, and back it up.

---

## 4. Internal linking

The structure carries the ranking signal, so it needs to be deliberate:

- **Hub → spoke → hub.** Every council page links to its suburb pages; every
  suburb page links back to its council page and across to two or three
  neighbouring suburbs.
- **Data creates links automatically.** A project on `/construction/newcastle`
  links to its builder page. The builder page links back to every council it
  operates in. As the database grows the internal link graph densifies on its
  own — this is the main structural advantage of the programmatic approach.
- **Every informational page gets exactly one contextual conversion link**, in
  prose, roughly a third of the way down. Not a banner. Something like: *"We
  track this across all five Hunter councils and send the ones worth ringing
  about every Monday — here's a sample issue."*
- **Sector pages link to the matching `/for/` audience page** and vice versa.
- **The quarterly report is linked from every hub page** for the quarter it
  covers. It is the link magnet; feed it internal authority.
- Breadcrumbs on every programmatic page, with `BreadcrumbList` schema.

---

## 5. Technical SEO

- **Server-render the programmatic pages.** Next.js App Router with ISR,
  revalidating daily. A client-rendered data page is a page Google may never
  see the data on.
- `Dataset` and `Place` schema on council and suburb pages; `Organization` on
  builder pages; `FAQPage` on the landing page and guides.
- `lastmod` in the sitemap must be real. Weekly-updated pages that claim daily
  freshness get their `lastmod` discounted entirely.
- Segment the sitemap: `/sitemap-councils.xml`, `/sitemap-suburbs.xml`,
  `/sitemap-builders.xml`, `/sitemap-content.xml`. Easier to diagnose which
  segment is indexing.
- `noindex` the app itself: `/dashboard`, `/account`, `/login`.
- Canonicals on any filtered view of a programmatic page.
- **Attribution on every data page** — CC-BY requires it, and it doubles as a
  credibility signal to both readers and search engines.
- Core Web Vitals: the audience is on phones, often on patchy reception at a
  site. Ship almost no JavaScript on the marketing and programmatic pages.

---

## 6. Fifty article ideas

Grouped by the job each one does. The ones marked ★ are the highest priority —
write those first.

### Live data and pipeline (the traffic engine)

1. ★ What's being built in Newcastle right now — a live pipeline
2. ★ Latest development approvals in Newcastle, updated weekly
3. Lake Macquarie development applications: what's in the pipeline
4. Maitland's construction boom — what's actually approved
5. Port Stephens development activity: Nelson Bay to Raymond Terrace
6. Cessnock and the Hunter Valley: what's being approved
7. ★ Commercial construction pipeline, Newcastle and the Hunter
8. Industrial development in the Hunter: warehouses, workshops and light industry
9. Every childcare centre approved in the Hunter this year
10. Medical and health facility approvals across the Hunter
11. The Hunter's residential pipeline, by suburb
12. Subdivision activity in Maitland and Cessnock
13. What got knocked back: refused DAs and what they tell you
14. ★ Newcastle West: inside the region's densest construction corridor

### Builders and who to call

15. ★ Who's actually building in Newcastle — the builder activity index
16. The ten most active builders in the Hunter this quarter
17. How to get on a builder's subcontractor list
18. What a construction certificate tells you that a DA doesn't
19. ★ How electricians can find builders before construction starts
20. Reading a builder's pipeline to time your approach
21. Which Hunter builders do the most commercial work
22. Project home builders in the Hunter: volume work and how it's let

### Understanding the data (evergreen, earns links)

23. ★ How to read a NSW development application
24. DA, CDC or CC — what each one means for a tradesperson
25. ★ How to use the NSW Planning Portal to find work
26. What "cost of development" actually means (and why it's often wrong)
27. Building Code classes explained for electricians
28. How long from DA approval to trades on site, really
29. Understanding the NSW planning approval pathway
30. What a construction certificate is and why it's the signal that matters

### Government and tenders

31. ★ How to find and win NSW government electrical contracts
32. Getting on the NSW government prequalification schemes
33. AusTender for tradespeople: a practical guide
34. What buy.nsw means for small contractors
35. School infrastructure work in the Hunter: how it gets let
36. Health infrastructure projects and how trades get engaged
37. Winning maintenance contracts vs chasing new builds

### The Hunter energy transition

38. ★ The Hunter's battery boom: what it means for electricians
39. Renewable energy zones and the electrical work they create
40. Grid-scale battery projects in the Hunter: a tracker
41. What the Hunter-Central Coast REZ means for local contractors
42. Getting qualified for utility-scale solar and battery work
43. EV charging infrastructure: where the Hunter work is coming from

### Business and trade

44. ★ How much electrical work is in a $10m commercial building?
45. Pricing commercial fitout electrical work
46. Moving from domestic to commercial electrical work
47. How to quote a job you found through public data
48. Should you chase government work? An honest assessment
49. Building a pipeline instead of waiting for the phone
50. What Hunter electricians are charging: a rates snapshot

### Quarterly link magnets (highest value, four a year)

- **The Hunter Construction Report, Q[N]** — total approvals, value, sector
  mix, busiest suburbs, most active builders. Pitch to the Newcastle Herald,
  Newcastle Weekly, Hunter Business Review and the Property Council's Hunter
  chapter. Real numbers about a real place is exactly what local media has no
  budget to produce and every incentive to cover.

---

## 7. Publishing cadence

| Phase | Cadence | Focus |
|---|---|---|
| Months 1–2 | nothing | Sell reports. Do not write blog posts before you have customers. |
| Months 3–5 | 2 posts/month + council pages live | The ★ evergreen explainers, which age well |
| Months 6–9 | 4 posts/month + suburb and builder pages | Volume and internal link density |
| Months 10+ | 2 posts/month + quarterly report | Programmatic pages carry the traffic by now |

**Do not start with content.** SEO takes six to nine months to pay, and if the
business does not survive to month six the posts are worthless. The runbook
comes first.

---

## 8. What success looks like

| Month | Organic sessions/month | Indexed pages | Trials from organic |
|---|---|---|---|
| 3 | ~50 | 20 | 0–1 |
| 6 | ~400 | 120 | 2–4 |
| 9 | ~1,200 | 250 | 5–10 |
| 12 | ~2,500 | 400 | 10–18 |
| 18 | ~6,000 | 700 | 25–40 |

At month 12, organic should be producing enough trials to be the largest single
channel, at a CAC well under paid. That is the payoff, and it is why content
starts in month 3 rather than month 1 — early enough to compound, late enough
that the business exists to benefit.
