#!/usr/bin/env python3
"""
Tradiesignal :: landing page builder
====================================
Generates site/landing.html for publishing as an Artifact.

The hero backdrop is not decoration: it is every one of the ~3,900 real
projects currently tracked, plotted at its actual coordinates and coloured by
sector, with this fortnight's highest-scoring opportunities picked out. The
featured opportunity cards are real records pulled straight from the scored
dataset, so the sales page and the product cannot drift apart.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from brand import apply_logo  # noqa: E402

DATA = Path("data")
OUT = Path("site")

CAT_COLORS = {
    "Residential": "#1466E0",
    "Commercial": "#E4681A",
    "Industrial": "#C42A62",
    "Government": "#8A7A12",
    "Infrastructure": "#6F52CC",
}

# Hunter bounding box. The feed contains a handful of miskeyed coordinates
# (one lands in Victoria); clipping keeps the map honest.
BOX = {"lon_min": 151.05, "lon_max": 152.25, "lat_min": -33.25, "lat_max": -32.55}


def e(t) -> str:
    return html.escape(str(t if t is not None else ""), quote=True)


def money(v, dp=1) -> str:
    if v is None:
        return "—"
    v = float(v)
    if v >= 1_000_000_000:
        return f"${v/1_000_000_000:.{dp}f}bn"
    if v >= 1_000_000:
        return f"${v/1_000_000:.{dp}f}m"
    if v >= 1_000:
        return f"${v/1_000:,.0f}k"
    return f"${v:,.0f}"


# ---------------------------------------------------------------------------
# hero map
# ---------------------------------------------------------------------------

def hero_map(projects: list[dict]) -> str:
    w, h = 760, 460
    def xy(p):
        fx = (p["lon"] - BOX["lon_min"]) / (BOX["lon_max"] - BOX["lon_min"])
        fy = 1 - (p["lat"] - BOX["lat_min"]) / (BOX["lat_max"] - BOX["lat_min"])
        return fx * w, fy * h

    inside = [
        p for p in projects
        if p.get("lat") and p.get("lon")
        and BOX["lon_min"] <= p["lon"] <= BOX["lon_max"]
        and BOX["lat_min"] <= p["lat"] <= BOX["lat_max"]
    ]
    background = [p for p in inside if p["opportunity_score"] < 80]
    highlight = sorted(
        [p for p in inside if p["opportunity_score"] >= 80],
        key=lambda p: -(p.get("cost") or 0),
    )[:26]

    dots = []
    for p in background:
        x, y = xy(p)
        dots.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" '
            f'fill="#7FA890" opacity=".5"/>'
        )
    marks = []
    for p in highlight:
        x, y = xy(p)
        r = 4.5 if (p.get("cost") or 0) < 10_000_000 else 7.5
        marks.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 3.5:.1f}" fill="#C6F04A" opacity=".22"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#C6F04A" '
            f'stroke="#0B2A1E" stroke-width="1.6"/>'
        )

    return (
        f'<svg class="heromap" viewBox="0 0 {w} {h}" role="img" aria-hidden="true" '
        f'preserveAspectRatio="xMidYMid slice">'
        f'<g class="hm-bg">{"".join(dots)}</g>'
        f'<g class="hm-hi">{"".join(marks)}</g>'
        f"</svg>"
    )


# ---------------------------------------------------------------------------
# featured opportunity cards
# ---------------------------------------------------------------------------

def feature_card(p: dict) -> str:
    colour = CAT_COLORS.get(p["filter_group"], "#1466E0")
    est = p.get("electrical_estimate")
    est_html = (
        f'{money(est[0])} – {money(est[1])}' if est else "not estimated"
    )
    builder = (
        f'<div class="f-builder"><span>Builder on the certificate</span>'
        f'<strong>{e(p["builder"])}</strong></div>'
        if p.get("builder") else
        '<div class="f-builder f-builder-none"><span>Builder</span>'
        '<strong>Not yet appointed — get in early</strong></div>'
    )
    return f"""
<article class="fcard" style="--cat:{colour}">
  <div class="f-top">
    <span class="f-chip" style="--chip:{colour}">{e(p["filter_group"])}</span>
    <span class="f-score">{p["opportunity_score"]}<i>score</i></span>
  </div>
  <h3>{e(p["project_name"])}</h3>
  <p class="f-where">{e(p["address"])}</p>
  <p class="f-stage">{e(p["stage_label"])} · {e(p["council_short"])}</p>
  <dl class="f-facts">
    <div><dt>Project value</dt><dd>{e(money(p.get("cost")))}</dd></div>
    <div><dt>Electrical opportunity</dt><dd>{e(est_html)}</dd></div>
    <div><dt>Act by</dt><dd>{e(p["contact_window"])}</dd></div>
  </dl>
  {builder}
</article>"""


# ---------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------

PRICING = [
    {
        "name": "Starter",
        "price": 49,
        "for": "Sole traders and two-van shops working one patch",
        "features": [
            "One council of your choice",
            "The fortnightly opportunity report by email",
            "Dashboard access, 25 km radius",
            "Residential and commercial approvals",
            "Opportunity scores and electrical estimates",
        ],
        "missing": ["Builder watchlist", "Government and tender coverage", "CSV export"],
        "cta": "Start 14-day free trial",
        "featured": False,
    },
    {
        "name": "Professional",
        "price": 99,
        "for": "The 3–10 van contractor chasing commercial work",
        "features": [
            "All five Hunter councils",
            "Weekly email plus the full dashboard",
            "Every sector, radius up to 100 km",
            "<strong>Builder watchlist</strong> — who is building, and how much",
            "Saved searches and email alerts on your filters",
            "CSV export for your own CRM",
            "Construction certificate alerts within 24 hours",
        ],
        "missing": ["Government tender coverage", "Multiple seats"],
        "cta": "Start 14-day free trial",
        "featured": True,
        "badge": "Most electricians pick this",
    },
    {
        "name": "Premium",
        "price": 199,
        "for": "Contractors bidding commercial, government and infrastructure",
        "features": [
            "Everything in Professional",
            "<strong>Daily</strong> alerts, not weekly",
            "Government tenders and the funded public pipeline",
            "State significant and major project tracking",
            "Three user seats for your estimating team",
            "Data feed access for your own systems",
            "Direct line to us for coverage requests",
        ],
        "missing": [],
        "cta": "Start 14-day free trial",
        "featured": False,
    },
]

FAQ = [
    ("Where does the data actually come from?",
     "The NSW Planning Portal's ePlanning open data feeds, published by the NSW "
     "Department of Planning, Housing and Infrastructure under a Creative Commons "
     "Attribution licence and refreshed daily. We pull development applications, "
     "complying development certificates and construction certificates for all five "
     "Hunter councils, then merge, score and filter them. Government tenders and "
     "funded infrastructure are added on top. It is all public information — the work "
     "we do is finding it, cleaning it, and telling you which of it is worth your time."),
    ("Isn't this just the council DA tracker?",
     "The council trackers show you one council, with no scoring, no filtering, no "
     "electrical estimate, and no way to see across the region. More importantly, they "
     "do not show you construction certificates with the builder's name on them. That "
     "single field is the difference between knowing a project exists and knowing who "
     "to ring about it."),
    ("How do you work out the electrical opportunity?",
     "We apply an industry percentage to the cost of development that the applicant "
     "lodged with council, varying by sector — a battery installation is mostly "
     "electrical, a subdivision is mostly civil. It is an estimate for ranking where "
     "to spend your week. It is not a quote and we present it as a range, never a "
     "single number."),
    ("The dollar figures on council applications are notoriously rubbish. How do you handle that?",
     "By checking them. Declared costs are entered by applicants and never audited, so "
     "the raw feed contains real errors — the current dataset includes a two-dwelling "
     "development lodged at $1.375 billion. We cross-check every figure against floor "
     "area, dwelling count and lot count. Anything that fails is flagged in the report "
     "and excluded from our totals. We would rather show you a project with no number "
     "than a number that is wrong."),
    ("Will every other sparky in Newcastle get the same list?",
     "Subscribers see the same public data — we are not pretending otherwise. What we "
     "sell is time and timing. Most electricians never look at this data at all, and "
     "the ones who do are looking a month too late. We also cap Starter and "
     "Professional subscriptions in each council area so a single list is not being "
     "worked by fifty people."),
    ("I already have more work than I can handle.",
     "Then this is the wrong month to subscribe, and we would rather you said so. Come "
     "back when the pipeline thins out — it always does. The electricians who get the "
     "most out of this are the ones who want to change the mix of their work, not just "
     "the volume: moving from domestic call-outs into commercial fitout, or getting on "
     "a builder's regular list."),
    ("Do you guarantee I will win work?",
     "No, and be suspicious of anyone who does. We guarantee the data is accurate to "
     "the public record, delivered on time, and that you can cancel in one click. If "
     "your first two reports do not turn up a single project worth a phone call, email "
     "us and we will refund you."),
    ("What about work outside the Hunter?",
     "Central Coast is next, then Wollongong and Sydney. The data source is state-wide, "
     "so expansion is a matter of coverage and support, not engineering. Tell us where "
     "you work and we will weight the queue."),
]

HOW = [
    ("Every night", "We pull the day's lodgements",
     "Development applications, complying development certificates and construction "
     "certificates for Newcastle, Lake Macquarie, Maitland, Port Stephens and Cessnock "
     "— straight from the NSW Planning Portal's open data feeds."),
    ("Then", "We merge and check them",
     "The same job can appear three times as it moves through approval. We link records "
     "by address into one project with its full history, then cross-check every dollar "
     "figure against floor area and dwelling counts so obvious errors never reach you."),
    ("Then", "We score what matters",
     "Sector, approval stage, value, distance from you, and high-intent signals like a "
     "named builder or solar and EV scope. A construction certificate for a medical "
     "centre beats a much bigger subdivision application, because one needs a sparky in "
     "a fortnight and the other in two years."),
    ("Every Monday, 6am", "You get a call list",
     "Not a database. A ranked list of the projects worth your time, with the estimated "
     "electrical scope, who to contact, and when to ring them."),
]


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
:root{
  --ink:#10231A; --ink-2:#2B4236; --grey:#56675E; --grey-2:#7D8C84;
  --paper:#FFFFFF; --paper-2:#F5F6F1; --card:#FFFFFF;
  --rule:#DDE3DB; --rule-2:#EDF0EA;
  --navy:#0B2A1E; --navy-2:#0F3827; --navy-3:#1A4D37;
  --blue:#0E5A3A; --blue-ink:#0E5A3A; --blue-wash:#E8F1EB;
  --green:#C6F04A; --green-ink:#0E5A3A; --green-wash:#F1F9DC;
  --on-navy:#F1F5EE; --on-navy-2:#A9BFB2;
  --shadow:0 1px 2px rgba(16,35,26,.06),0 8px 24px rgba(16,35,26,.07);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ink:#EDF2EC; --ink-2:#C4D2C8; --grey:#9DB0A4; --grey-2:#7A8D81;
  --paper:#08110C; --paper-2:#0D1812; --card:#12211A;
  --rule:#243A2E; --rule-2:#1A2C22;
  --navy:#06100B; --navy-2:#0C1D15; --navy-3:#1A3A2A;
  --blue:#237A50; --blue-ink:#9FDDB5; --blue-wash:#13291E;
  --green:#C6F04A; --green-ink:#C6F04A; --green-wash:#1C2A0E;
  --on-navy:#F1F5EE; --on-navy-2:#A9BFB2;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px rgba(0,0,0,.34);
}}
:root[data-theme="dark"]{
  --ink:#EDF2EC; --ink-2:#C4D2C8; --grey:#9DB0A4; --grey-2:#7A8D81;
  --paper:#08110C; --paper-2:#0D1812; --card:#12211A;
  --rule:#243A2E; --rule-2:#1A2C22;
  --navy:#06100B; --navy-2:#0C1D15; --navy-3:#1A3A2A;
  --blue:#237A50; --blue-ink:#9FDDB5; --blue-wash:#13291E;
  --green:#C6F04A; --green-ink:#C6F04A; --green-wash:#1C2A0E;
  --on-navy:#F1F5EE; --on-navy-2:#A9BFB2;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px rgba(0,0,0,.34);
}

*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"IBM Plex Sans","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{font-family:Schibsted Grotesk,"Arial Narrow",Helvetica,sans-serif;margin:0;
  text-wrap:balance;letter-spacing:-.01em;line-height:1.12}
p{margin:0}
a{color:inherit}
.wrap{max-width:1120px;margin:0 auto;padding-inline:20px}
.eyebrow{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--grey-2)}
.num{font-variant-numeric:tabular-nums}

/* ---------------- nav ---------------- */
.nav{position:sticky;top:0;z-index:40;background:var(--navy);
  border-bottom:1px solid var(--navy-3)}
.nav-in{max-width:1120px;margin:0 auto;padding:13px 20px;display:flex;
  align-items:center;gap:18px;flex-wrap:wrap}
.logo{font-family:Schibsted Grotesk,sans-serif;font-weight:800;font-size:21px;color:#fff;
  letter-spacing:-.03em;white-space:nowrap}
.logo .sig{color:var(--green)}
.logo{display:inline-flex;align-items:center;gap:.32em;letter-spacing:-.022em;line-height:1;white-space:nowrap}.logo .sig{font-size:inherit;margin:0;padding:0}.logo-mark{height:1.15em;width:auto;flex:none}
.nav-links{display:flex;gap:20px;margin-left:auto;font-size:14px;flex-wrap:wrap}
.nav-links a{color:var(--on-navy-2);text-decoration:none}
.nav-links a:hover,.nav-links a:focus-visible{color:#fff}
.nav .btn{margin-left:4px}

/* ---------------- buttons ---------------- */
.btn{display:inline-block;font-family:Schibsted Grotesk,sans-serif;font-weight:700;
  font-size:15px;padding:12px 22px;border-radius:3px;text-decoration:none;
  border:2px solid transparent;cursor:pointer;transition:transform .12s ease}
.btn:active{transform:translateY(1px)}
.btn-go{background:var(--green);color:#0B2A1E}
.btn-go:hover{background:#D4F76B}
.btn-line{border-color:#2F5A45;color:var(--on-navy)}
.btn-line:hover{border-color:var(--green);color:#fff}
.btn-blue{background:var(--blue);color:#fff}
.btn-sm{font-size:13.5px;padding:9px 16px}
:focus-visible{outline:3px solid var(--green);outline-offset:2px}

/* ---------------- hero ---------------- */
.hero{position:relative;background:var(--navy);color:var(--on-navy);
  overflow:hidden;border-bottom:3px solid var(--green)}
.heromap{position:absolute;inset:0;width:100%;height:100%;opacity:1;
  pointer-events:none;
  -webkit-mask-image:linear-gradient(96deg,transparent 6%,rgba(0,0,0,.3) 26%,#000 50%,#000 100%);
  mask-image:linear-gradient(96deg,transparent 6%,rgba(0,0,0,.3) 26%,#000 50%,#000 100%)}
.hero::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(96deg,var(--navy) 0%,rgba(11,42,30,.94) 22%,
    rgba(11,42,30,.5) 40%,rgba(11,42,30,.18) 62%,rgba(11,42,30,.4) 100%)}
.hero-in{position:relative;z-index:2;max-width:1120px;margin:0 auto;
  padding:74px 20px 86px;display:grid;grid-template-columns:1.05fr .95fr;
  gap:52px;align-items:center}
.hero h1{font-size:clamp(32px,4.4vw,50px);font-weight:800;color:#fff;
  max-width:19ch}
.hero .sub{margin-top:20px;font-size:clamp(17px,2vw,20px);color:var(--on-navy-2);
  max-width:46ch}
.hero-cta{display:flex;gap:12px;margin-top:30px;flex-wrap:wrap}
.hero-proof{display:grid;grid-template-columns:repeat(4,auto);gap:14px 26px;
  margin-top:32px;padding-top:22px;border-top:1px solid var(--navy-3);
  justify-content:start}
.hero-proof div{min-width:0}
.hero-proof dt{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--on-navy-2);margin-bottom:5px}
.hero-proof dd{margin:0;font-family:Schibsted Grotesk,sans-serif;font-weight:700;
  font-size:23px;color:#fff;font-variant-numeric:tabular-nums;line-height:1}
.maplegend{margin-top:22px;font-size:12px;color:var(--on-navy-2);
  display:flex;align-items:center;gap:9px}
.maplegend i{width:9px;height:9px;border-radius:50%;background:var(--green);
  flex:none;box-shadow:0 0 0 4px rgba(198,240,74,.18)}

/* the live card sitting in the hero */
.livecard{background:rgba(12,36,26,.97);backdrop-filter:blur(3px);border:1px solid var(--navy-3);border-radius:4px;
  padding:22px;box-shadow:0 20px 50px rgba(0,0,0,.45)}
.live-tag{display:flex;align-items:center;gap:8px;font-family:"IBM Plex Mono",monospace;
  font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--green)}
.live-tag i{width:7px;height:7px;border-radius:50%;background:var(--green);flex:none}
.livecard h2{font-size:21px;color:#fff;margin-top:14px;font-weight:700}
.live-addr{color:var(--on-navy-2);font-size:14px;margin-top:5px}
.live-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px;
  padding-top:16px;border-top:1px solid var(--navy-3)}
.live-grid dt{font-size:10px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--on-navy-2);margin-bottom:3px}
.live-grid dd{margin:0;font-weight:600;font-size:17px;color:#fff;
  font-variant-numeric:tabular-nums}
.live-builder{margin-top:16px;padding:12px 14px;background:rgba(198,240,74,.09);
  border-left:3px solid var(--green)}
.live-builder span{display:block;font-size:10px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--green);margin-bottom:3px}
.live-builder strong{color:#fff;font-size:15px}
.live-foot{margin-top:14px;font-size:11.5px;color:var(--on-navy-2);
  font-family:"IBM Plex Mono",monospace}

/* ---------------- generic section ---------------- */
section{padding-block:74px}
.sec-alt{background:var(--paper-2);border-block:1px solid var(--rule)}
.sec-head{max-width:70ch}
.sec-head h2{font-size:clamp(26px,3.6vw,38px);font-weight:800;margin-top:12px}
.sec-head p{margin-top:16px;font-size:17px;color:var(--grey);max-width:62ch}

/* ---------------- problem ---------------- */
.split{display:grid;grid-template-columns:1fr 1fr;gap:42px;margin-top:40px;
  align-items:start}
.panel{border:1px solid var(--rule);border-radius:4px;padding:26px;
  background:var(--card)}
.panel-bad{border-color:var(--rule);background:var(--paper-2)}
.panel h3{font-size:17px;font-weight:700;margin-bottom:16px}
.panel ul{margin:0;padding:0;list-style:none;font-size:15px}
.panel li{padding:9px 0 9px 26px;position:relative;border-bottom:1px solid var(--rule-2);
  color:var(--ink-2)}
.panel li:last-child{border-bottom:0}
.panel-bad li::before{content:"×";position:absolute;left:4px;top:9px;
  color:var(--grey-2);font-weight:700;font-size:17px;line-height:1.4}
.panel-good{border-left:3px solid var(--green)}
.panel-good li::before{content:"";position:absolute;left:2px;top:1.05em;width:11px;
  height:2px;background:var(--green-ink)}
.panel .tally{margin-top:18px;padding-top:16px;border-top:1px solid var(--rule);
  font-size:14px;color:var(--grey)}
.panel .tally b{color:var(--ink);font-size:16px}

/* ---------------- featured ---------------- */
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(292px,1fr));
  gap:20px;margin-top:38px}
.fcard{background:var(--card);border:1px solid var(--rule);
  border-top:3px solid var(--cat);border-radius:4px;padding:22px;
  display:flex;flex-direction:column;box-shadow:var(--shadow)}
.f-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.f-chip{font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:#fff;background:var(--chip);padding:3px 8px;border-radius:2px}
.f-score{font-family:Schibsted Grotesk,sans-serif;font-weight:800;font-size:26px;
  line-height:1;color:var(--green-ink);font-variant-numeric:tabular-nums;
  display:flex;align-items:baseline;gap:5px}
.f-score i{font-family:"IBM Plex Mono",monospace;font-style:normal;font-size:9.5px;
  letter-spacing:.13em;text-transform:uppercase;color:var(--grey-2);font-weight:400}
.fcard h3{font-size:18px;font-weight:700;margin-top:15px}
.f-where{font-size:13.5px;color:var(--grey);margin-top:5px}
.f-stage{font-size:12.5px;color:var(--ink-2);margin-top:8px;font-weight:500}
.f-facts{display:flex;flex-direction:column;gap:11px;margin:17px 0 0;
  padding:15px 0;border-top:1px solid var(--rule-2);border-bottom:1px solid var(--rule-2)}
.f-facts>div{display:flex;justify-content:space-between;gap:12px;align-items:baseline}
.f-facts dt{font-size:12.5px;color:var(--grey)}
.f-facts dd{margin:0;font-weight:600;font-size:14.5px;text-align:right;
  font-variant-numeric:tabular-nums}
.f-builder{margin-top:16px;padding:11px 13px;background:var(--blue-wash);
  border-left:3px solid var(--blue);margin-top:auto}
.f-builder span{display:block;font-size:10px;letter-spacing:.11em;
  text-transform:uppercase;color:var(--blue-ink);margin-bottom:3px}
.f-builder strong{font-size:14px}
.f-builder-none{background:var(--paper-2);border-left-color:var(--grey-2)}
.f-builder-none span{color:var(--grey)}
.f-builder-none strong{font-weight:500;color:var(--ink-2)}
.fnote{margin-top:26px;font-size:14px;color:var(--grey);max-width:74ch}

/* ---------------- how ---------------- */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(232px,1fr));
  gap:0;margin-top:40px;border-top:2px solid var(--ink)}
.step{padding:24px 22px 26px 0;border-right:1px solid var(--rule)}
.step:last-child{border-right:0}
.step-when{font-family:"IBM Plex Mono",monospace;font-size:10.5px;letter-spacing:.13em;
  text-transform:uppercase;color:var(--green-ink);font-weight:600}
.step h3{font-size:18px;font-weight:700;margin-top:10px}
.step p{margin-top:11px;font-size:14.5px;color:var(--ink-2)}

/* ---------------- pricing ---------------- */
.prices{display:grid;grid-template-columns:repeat(auto-fit,minmax(278px,1fr));
  gap:22px;margin-top:42px;align-items:start}
.price{background:var(--card);border:1px solid var(--rule);border-radius:4px;
  padding:28px 24px;display:flex;flex-direction:column;height:100%}
.price-hot{border:2px solid var(--blue);box-shadow:var(--shadow);position:relative}
.price-badge{position:absolute;top:-12px;left:24px;background:var(--blue);color:#fff;
  font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;
  padding:4px 11px;border-radius:2px}
.price h3{font-size:20px;font-weight:800}
.price-for{font-size:13.5px;color:var(--grey);margin-top:7px;min-height:40px}
.price-amt{display:flex;align-items:baseline;gap:5px;margin-top:18px;
  padding-bottom:20px;border-bottom:1px solid var(--rule)}
.price-amt b{font-family:Schibsted Grotesk,sans-serif;font-weight:800;font-size:44px;
  line-height:1;font-variant-numeric:tabular-nums}
.price-amt span{color:var(--grey);font-size:14px}
.price ul{margin:20px 0 0;padding:0;list-style:none;font-size:14.5px;flex:1}
.price li{padding:7px 0 7px 24px;position:relative;color:var(--ink-2)}
.price li::before{content:"";position:absolute;left:2px;top:1em;width:11px;height:2px;
  background:var(--green-ink)}
.price li.no{color:var(--grey-2)}
.price li.no::before{content:"×";background:none;left:5px;top:6px;width:auto;height:auto;
  font-weight:700}
.price .btn{margin-top:22px;text-align:center;display:block}
.price-note{margin-top:11px;font-size:12px;color:var(--grey-2);text-align:center}
.price-foot{margin-top:30px;font-size:14.5px;color:var(--grey);max-width:74ch}

/* ---------------- sample ---------------- */
.sample{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center}
.sample-shot{border:1px solid var(--rule);border-radius:4px;overflow:hidden;
  box-shadow:var(--shadow);background:var(--card)}
.sample-shot .shot-bar{background:var(--navy);padding:11px 16px;display:flex;
  align-items:center;gap:9px}
.shot-bar span{font-family:"IBM Plex Mono",monospace;font-size:10.5px;
  letter-spacing:.1em;text-transform:uppercase;color:var(--on-navy-2)}
.shot-bar i{width:8px;height:8px;border-radius:50%;background:var(--green);flex:none}
.shot-body{padding:20px}
.shot-row{display:flex;gap:12px;align-items:center;padding:11px 0;
  border-bottom:1px solid var(--rule-2);font-size:13.5px}
.shot-row:last-child{border-bottom:0}
.shot-sc{font-family:"IBM Plex Mono",monospace;font-weight:600;color:var(--green-ink);
  font-variant-numeric:tabular-nums;width:30px;flex:none}
.shot-nm{flex:1;min-width:0;font-weight:500;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
.shot-vl{font-variant-numeric:tabular-nums;color:var(--grey);white-space:nowrap}

/* ---------------- quotes ---------------- */
.quotes{display:grid;grid-template-columns:repeat(auto-fit,minmax(268px,1fr));
  gap:20px;margin-top:36px}
.quote{border:1px dashed var(--rule);border-radius:4px;padding:22px;
  background:var(--card)}
.quote p{font-size:15px;color:var(--grey-2);font-style:italic}
.quote footer{margin-top:16px;padding-top:14px;border-top:1px solid var(--rule-2);
  font-size:12.5px;color:var(--grey-2)}
.quote-note{margin-top:24px;font-size:14px;color:var(--grey);max-width:70ch;
  padding:16px 18px;border-left:3px solid var(--blue);background:var(--blue-wash)}

/* ---------------- faq ---------------- */
.faq{margin-top:36px;border-top:1px solid var(--rule)}
details{border-bottom:1px solid var(--rule)}
summary{cursor:pointer;padding:19px 0;font-family:Schibsted Grotesk,sans-serif;font-weight:700;
  font-size:17px;list-style:none;display:flex;justify-content:space-between;
  align-items:center;gap:18px}
summary::-webkit-details-marker{display:none}
summary::after{content:"+";font-family:"IBM Plex Mono",monospace;font-size:21px;
  color:var(--blue);flex:none;font-weight:400}
details[open] summary::after{content:"–"}
details p{padding:0 0 20px;font-size:15px;color:var(--ink-2);max-width:76ch}

/* ---------------- cta ---------------- */
.cta{background:var(--navy);color:var(--on-navy);text-align:center;
  border-top:3px solid var(--green)}
.cta h2{font-size:clamp(27px,3.8vw,40px);color:#fff;font-weight:800;
  max-width:20ch;margin-inline:auto}
.cta p{margin-top:18px;color:var(--on-navy-2);font-size:17px;max-width:56ch;
  margin-inline:auto}
.cta .hero-cta{justify-content:center}
.cta-fine{margin-top:26px;font-size:13px;color:var(--on-navy-2)}

/* ---------------- footer ---------------- */
.foot{background:var(--navy);color:var(--on-navy-2);padding-block:38px;
  border-top:1px solid var(--navy-3);font-size:13.5px}
.foot-in{max-width:1120px;margin:0 auto;padding-inline:20px;display:flex;
  justify-content:space-between;gap:24px;flex-wrap:wrap}
.foot a{color:var(--on-navy-2)}
.foot p{max-width:60ch;line-height:1.6}

@media (max-width:900px){
  .hero-in,.split,.sample{grid-template-columns:1fr;gap:36px}
  .hero-in{padding-block:52px 48px}
  .step{border-right:0;border-bottom:1px solid var(--rule);padding-right:0}
  .step:last-child{border-bottom:0}
  .nav-links{display:none}
  .heromap{width:100%;-webkit-mask-image:linear-gradient(180deg,transparent 0%,#000 40%);
    mask-image:linear-gradient(180deg,transparent 0%,#000 40%);opacity:.5}
  .hero-proof{grid-template-columns:repeat(2,1fr)}
  section{padding-block:56px}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Schibsted+Grotesk:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&'
         'family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">')


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------

def build() -> str:
    projects = json.loads((DATA / "projects.json").read_text(encoding="utf-8"))
    payload = json.loads((DATA / "report_payload.json").read_text(encoding="utf-8"))
    summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    t = payload["totals"]

    live = [p for p in projects if p["stage_key"] != "withdrawn"]

    # Hero card: the single best "ring them today" record we hold.
    hero_pick = next(
        (p for p in payload["act_now"] if p.get("builder")),
        payload["act_now"][0],
    )
    # Featured: three real records across different sectors.
    seen_groups, featured = set(), []
    for p in payload["act_now"] + payload["pipeline"]:
        if p["filter_group"] in seen_groups:
            continue
        seen_groups.add(p["filter_group"])
        featured.append(p)
        if len(featured) == 3:
            break

    builders_identified = sum(1 for p in live if p.get("builder"))

    est = hero_pick.get("electrical_estimate")
    hero_est = f"{money(est[0])} – {money(est[1])}" if est else "—"

    nav = """
<nav class="nav"><div class="nav-in">
  %%LOGO%%
  <div class="nav-links">
    <a href="#problem">The problem</a>
    <a href="#live">This week</a>
    <a href="#how">How it works</a>
    <a href="#pricing">Pricing</a>
    <a href="#sample">Sample report</a>
    <a href="#faq">FAQ</a>
  </div>
  <a class="btn btn-go btn-sm" href="#pricing">Start free trial</a>
</div></nav>"""

    hero = f"""
<header class="hero">
  {hero_map(live)}
  <div class="hero-in">
    <div>
      <span class="eyebrow" style="color:var(--green)">Newcastle · Lake Macquarie · Maitland · Port Stephens · Cessnock</span>
      <h1>Find electrical project opportunities before your competition.</h1>
      <p class="sub">We monitor council approvals, construction activity and government
        projects so you don't have to.</p>
      <div class="hero-cta">
        <a class="btn btn-go" href="#sample">View sample report</a>
        <a class="btn btn-line" href="#pricing">Start free trial</a>
      </div>
      <dl class="hero-proof">
        <div><dt>Projects tracked</dt><dd class="num">{t["tracked_total"]:,}</dd></div>
        <div><dt>Construction value</dt><dd class="num">{money(summary["construction_value_verified"], 1)}</dd></div>
        <div><dt>Builders identified</dt><dd class="num">{builders_identified:,}</dd></div>
        <div><dt>Councils covered</dt><dd class="num">5</dd></div>
      </dl>
      <p class="maplegend"><i></i>Every dot behind this is a real project we are tracking
        right now. The bright green ones are this fortnight's highest scores.</p>
    </div>
    <div class="livecard">
      <span class="live-tag"><i></i>Live in the dashboard today</span>
      <h2>{e(hero_pick["project_name"])}</h2>
      <p class="live-addr">{e(hero_pick["address"])}</p>
      <dl class="live-grid">
        <div><dt>Opportunity score</dt><dd>{hero_pick["opportunity_score"]}/100</dd></div>
        <div><dt>Project value</dt><dd>{e(money(hero_pick.get("cost")))}</dd></div>
        <div><dt>Electrical opportunity</dt><dd>{e(hero_est)}</dd></div>
        <div><dt>Stage</dt><dd style="font-size:14px">{e(hero_pick["stage_label"])}</dd></div>
      </dl>
      <div class="live-builder">
        <span>Builder named on the certificate</span>
        <strong>{e(hero_pick.get("builder") or "Not yet appointed")}</strong>
      </div>
      <p class="live-foot">{e(hero_pick["source_ref"])} · NSW Planning Portal · {e(hero_pick["contact_window"])}</p>
    </div>
  </div>
</header>"""

    problem = f"""
<section id="problem">
  <div class="wrap">
    <div class="sec-head">
      <span class="eyebrow">The problem</span>
      <h2>By the time you hear about a job, the builder has already picked a sparky.</h2>
      <p>Not because you are slower. Because the information is scattered across twenty
        websites, none of which were built for you, and none of which tell you which of
        it is worth a phone call.</p>
    </div>
    <div class="split">
      <div class="panel panel-bad">
        <h3>What finding work looks like now</h3>
        <ul>
          <li>Five separate council DA trackers, each with its own search</li>
          <li>The NSW Planning Portal, if you know it exists</li>
          <li>buy.nsw and AusTender for government work</li>
          <li>Infrastructure and agency announcements scattered across agency sites</li>
          <li>No dollar figures you can trust, no scoring, no filtering</li>
          <li>No way to see who is actually building</li>
          <li>And you are doing all this at 9pm after a full day on the tools</li>
        </ul>
        <p class="tally">Realistically: <b>2–3 hours a week</b>, and you still miss the
          good ones.</p>
      </div>
      <div class="panel panel-good">
        <h3>What it looks like with Tradiesignal</h3>
        <ul>
          <li>One email, Monday 6am, ranked by what is worth your time</li>
          <li>Every approval across all five Hunter councils, merged into one project</li>
          <li>Dollar figures cross-checked against floor area and dwelling counts</li>
          <li>An estimated electrical scope and value for each job</li>
          <li><strong>The builder's name</strong>, straight off the construction certificate</li>
          <li>When to ring, and who to ask for</li>
          <li>Read it with your first coffee, done in ten minutes</li>
        </ul>
        <p class="tally">Realistically: <b>10 minutes a week</b>, and a call list you
          can actually work.</p>
      </div>
    </div>
  </div>
</section>"""

    fcards = "".join(feature_card(p) for p in featured)
    live_sec = f"""
<section id="live" class="sec-alt">
  <div class="wrap">
    <div class="sec-head">
      <span class="eyebrow">Live right now · not a mock-up</span>
      <h2>Three real opportunities from this fortnight.</h2>
      <p>These are genuine records pulled from the NSW Planning Portal in the
        {t["window_days"]} days to {e(t["window_to"])}. Every figure is from the public
        record; the score, the electrical estimate and the timing are ours.</p>
    </div>
    <div class="fgrid">{fcards}</div>
    <p class="fnote">In that same fortnight we tracked <strong>{t["recent_count"]:,}</strong>
      new or updated projects worth <strong>{money(t["recent_value"], 2)}</strong> in
      declared construction value, and filtered them down to
      <strong>{t["recent_high"] + t["recent_medium"]}</strong> worth acting on.
      <strong>{t["builders_named"]}</strong> of them named the building company.</p>
  </div>
</section>"""

    steps = "".join(
        f"""<div class="step">
      <span class="step-when">{e(when)}</span>
      <h3>{e(title)}</h3>
      <p>{e(body)}</p>
    </div>"""
        for when, title, body in HOW
    )
    how = f"""
<section id="how">
  <div class="wrap">
    <div class="sec-head">
      <span class="eyebrow">How it works</span>
      <h2>Public data in. A call list out.</h2>
      <p>There is no magic here and we are not going to pretend there is. The data is
        public. The work is in collecting it every day, checking it, scoring it, and
        cutting 3,900 records down to the dozen that matter to you.</p>
    </div>
    <div class="steps">{steps}</div>
  </div>
</section>"""

    price_cards = []
    for plan in PRICING:
        feats = "".join(f"<li>{f}</li>" for f in plan["features"])
        miss = "".join(f'<li class="no">{e(m)}</li>' for m in plan["missing"])
        badge = f'<span class="price-badge">{e(plan["badge"])}</span>' if plan.get("badge") else ""
        price_cards.append(f"""
<div class="price{' price-hot' if plan['featured'] else ''}">
  {badge}
  <h3>{e(plan["name"])}</h3>
  <p class="price-for">{e(plan["for"])}</p>
  <div class="price-amt"><b>${plan["price"]}</b><span>per month, ex GST</span></div>
  <ul>{feats}{miss}</ul>
  <a class="btn {'btn-blue' if plan['featured'] else 'btn-go'}" href="#cta">{e(plan["cta"])}</a>
  <p class="price-note">No card required. Cancel in one click.</p>
</div>""")

    pricing = f"""
<section id="pricing" class="sec-alt">
  <div class="wrap">
    <div class="sec-head">
      <span class="eyebrow">Pricing</span>
      <h2>Less than an hour of your charge-out rate.</h2>
      <p>One extra commercial fitout a year pays for a decade of Professional. That is
        the whole argument, and if the numbers do not work that way for your business,
        do not subscribe.</p>
    </div>
    <div class="prices">{"".join(price_cards)}</div>
    <p class="price-foot">All plans are month to month with a 14-day free trial and no
      card up front. Prices are in Australian dollars and exclude GST. We cap the number
      of Starter and Professional subscribers per council area so the same list is not
      being worked by everyone in town.</p>
  </div>
</section>"""

    shot_rows = "".join(
        f"""<div class="shot-row">
      <span class="shot-sc">{p["opportunity_score"]}</span>
      <span class="shot-nm">{e(p["project_name"])}</span>
      <span class="shot-vl">{e(money(p.get("cost")))}</span>
    </div>"""
        for p in (payload["act_now"] + payload["pipeline"])[:7]
    )
    sample = f"""
<section id="sample">
  <div class="wrap">
    <div class="sample">
      <div>
        <span class="eyebrow">Sample report</span>
        <h2 style="font-size:clamp(26px,3.6vw,38px);font-weight:800;margin-top:12px">
          Read a real issue before you pay a cent.</h2>
        <p style="margin-top:16px;font-size:17px;color:var(--grey);max-width:56ch">
          Issue 01 is a genuine {t["window_days"]}-day analysis of every approval lodged
          across the five Hunter councils — {t["recent_count"]:,} projects, scored and
          cut down to a call list, with the builder watchlist, the sector breakdown and
          the funded public pipeline.</p>
        <p style="margin-top:14px;font-size:15px;color:var(--grey);max-width:56ch">
          No sign-up wall. If it is not useful, you have lost ten minutes and we have
          lost nothing worth keeping.</p>
        <div class="hero-cta">
          <a class="btn btn-blue" href="#cta">Get the sample report</a>
        </div>
      </div>
      <div class="sample-shot">
        <div class="shot-bar"><i></i><span>Issue 01 · top opportunities</span></div>
        <div class="shot-body">{shot_rows}</div>
      </div>
    </div>
  </div>
</section>"""

    quotes = """
<section id="proof" class="sec-alt">
  <div class="wrap">
    <div class="sec-head">
      <span class="eyebrow">Customer results</span>
      <h2>We have not got any yet.</h2>
      <p>Tradiesignal is new. Rather than invent a testimonial from "Dave, Sparky,
        Newcastle", here is what we will publish the moment we have it — and what we
        are measuring to get there.</p>
    </div>
    <div class="quotes">
      <div class="quote">
        <p>"Placeholder: a named local contractor, their business size, the specific
          project they found through the report, and what it was worth."</p>
        <footer>To be replaced with a real, attributable customer quote</footer>
      </div>
      <div class="quote">
        <p>"Placeholder: a contractor describing a builder relationship that started
          from the watchlist rather than a single job."</p>
        <footer>To be replaced with a real, attributable customer quote</footer>
      </div>
      <div class="quote">
        <p>"Placeholder: time saved, in the customer's own words, against what they
          used to do on a Sunday night."</p>
        <footer>To be replaced with a real, attributable customer quote</footer>
      </div>
    </div>
    <p class="quote-note"><strong>Why this section is empty.</strong> Fake testimonials
      are the fastest way to lose a trade audience — Newcastle is a small town and
      everyone knows everyone. Until a real subscriber says something we can attribute,
      this space stays honest.</p>
  </div>
</section>"""

    faq = "".join(
        f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in FAQ
    )
    faq_sec = f"""
<section id="faq">
  <div class="wrap">
    <div class="sec-head">
      <span class="eyebrow">Questions</span>
      <h2>The things electricians actually ask us.</h2>
    </div>
    <div class="faq">{faq}</div>
  </div>
</section>"""

    cta = f"""
<section id="cta" class="cta">
  <div class="wrap">
    <h2>Stop hearing about jobs after they are let.</h2>
    <p>Fourteen days free, no card, and the first report lands within an hour of you
      signing up. If it is not worth $99 a month to you, cancel and keep the reports
      you have already had.</p>
    <div class="hero-cta">
      <a class="btn btn-go" href="#pricing">Start free trial</a>
      <a class="btn btn-line" href="#sample">Read a sample first</a>
    </div>
    <p class="cta-fine">Covering Newcastle, Lake Macquarie, Maitland, Port Stephens and
      Cessnock. Central Coast next.</p>
  </div>
</section>"""

    foot = f"""
<footer class="foot"><div class="foot-in">
  <div>
    %%LOGO|font-size:18px%%
    <p style="margin-top:10px">Construction opportunity intelligence for Hunter
      electricians. Newcastle, NSW.</p>
  </div>
  <div style="max-width:44ch">
    <p><strong style="color:var(--on-navy)">Data sources.</strong> Council development
      data from the NSW Planning Portal ePlanning open data APIs, © State of New South
      Wales (Department of Planning, Housing and Infrastructure), used under
      <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Public
      pipeline figures from the NSW Budget 2026-27 regional papers and agency
      announcements.</p>
    <p style="margin-top:10px">Scores, electrical estimates and timing advice are
      Tradiesignal's own analysis, not official information. Verify every project
      against the primary source before quoting.</p>
  </div>
</div></footer>"""

    body = nav + hero + problem + live_sec + how + pricing + sample + quotes + faq_sec + cta + foot
    return (
        f"<title>Tradiesignal</title>{FONTS}<style>{CSS}</style>{body}"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page = build()
    (OUT / "landing.html").write_text(apply_logo(page), encoding="utf-8")
    print(f"wrote site/landing.html ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
