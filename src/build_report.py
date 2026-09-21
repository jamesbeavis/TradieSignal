#!/usr/bin/env python3
"""
Tradiesignal :: weekly report builder
=====================================
Renders the fortnightly Hunter Electrical Opportunity Report from
data/report_payload.json into two outputs from one body of markup:

    reports/report_print.html   light-only, A4 @page rules, for PDF export
    reports/report_web.html     theme-aware, for publishing as a web page

Design system
-------------
Palette   ink #0A1628 / navy #12293F / electric blue #0B6BF2 /
          signal green #00E07A / paper #F6F8FB / rule #DDE4EE
          categorical (validated light+dark, fixed order):
          #1466E0 Residential, #E4681A Commercial, #C42A62 Industrial,
          #8A7A12 Government, #6F52CC Infrastructure
          status (reserved, never a series): #00713F good, #8A5107 warn,
          #A32A20 critical
Type      Archivo (display) / IBM Plex Sans (body) / IBM Plex Mono (refs, data)
Layout    A worksite job sheet: navy masthead with a signal rule, a plain row
          of summary figures with tabular numerals, then ranked job cards with
          a priority stripe, a switchboard-style score block, and a call line.
"""

from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

DATA = Path("data")
OUT = Path("reports")

CAT_COLORS = {
    "Residential": "#1466E0",
    "Commercial": "#E4681A",
    "Industrial": "#C42A62",
    "Government": "#8A7A12",
    "Infrastructure": "#6F52CC",
}

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ---------------------------------------------------------------------------
# formatting helpers
# ---------------------------------------------------------------------------

def e(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def money(value, dp: int = 1) -> str:
    """Compact money for a tradesperson reading on a phone."""
    if value is None:
        return "—"
    value = float(value)
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.{dp}f}bn"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.{dp}f}m"
    if value >= 1_000:
        return f"${value / 1_000:,.0f}k"
    return f"${value:,.0f}"


def money_full(value) -> str:
    return "—" if value is None else f"${value:,.0f}"


def band(estimate) -> str:
    if not estimate:
        return "not estimated"
    return f"{money(estimate[0])} – {money(estimate[1])}"


def pretty_date(iso: str | None) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def short_date(iso: str | None) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1][:3]}"


CONF_LABEL = {
    "high": ("Cross-checked", "good"),
    "medium": ("Plausible", "good"),
    "low": ("Low value", "neutral"),
    "suspect": ("Figure looks wrong", "warn"),
    "unverified": ("Unverified figure", "warn"),
    "unknown": ("No figure lodged", "neutral"),
}


# ---------------------------------------------------------------------------
# charts — inline SVG, one scale, direct labels, explicit fills
# ---------------------------------------------------------------------------

def hbar_chart(rows: list[dict], value_key: str, label_fmt, colour, title: str,
               sub: str = "", height_per: int = 34) -> str:
    """
    Horizontal bars. One scale places every mark and every label names a value
    the chart actually reaches. Labels sit outside the plot with room reserved
    in the viewBox, so nothing clips.
    """
    if not rows:
        return ""
    label_w, value_w, pad_t, pad_b = 132, 96, 8, 8
    plot_w = 300
    total_w = label_w + plot_w + value_w
    total_h = pad_t + pad_b + height_per * len(rows)
    peak = max((r[value_key] or 0) for r in rows) or 1

    parts = [
        f'<figure class="chart">',
        f'<figcaption><span class="chart-title">{e(title)}</span>',
        (f'<span class="chart-sub">{e(sub)}</span>' if sub else ""),
        "</figcaption>",
        f'<svg viewBox="0 0 {total_w} {total_h}" role="img" '
        f'aria-label="{e(title)}" class="chart-svg">',
    ]
    bar_h = 14
    for i, row in enumerate(rows):
        y = pad_t + i * height_per
        cy = y + height_per / 2
        val = row[value_key] or 0
        w = max(2.0, (val / peak) * plot_w)
        fill = colour(row) if callable(colour) else colour
        parts.append(
            f'<text x="{label_w - 10}" y="{cy}" text-anchor="end" '
            f'dominant-baseline="central" class="c-lab">{e(row["label"])}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{cy - bar_h / 2:.1f}" width="{w:.1f}" '
            f'height="{bar_h}" rx="4" ry="4" fill="{fill}" />'
        )
        parts.append(
            f'<text x="{label_w + w + 8:.1f}" y="{cy}" dominant-baseline="central" '
            f'class="c-val">{e(label_fmt(row))}</text>'
        )
    parts.append("</svg></figure>")
    return "".join(parts)


def funnel_chart(rows: list[dict]) -> str:
    """
    The approval pipeline as a stepped funnel. Order carries real information
    here — it is the sequence a project actually moves through — so the
    numbered progression is structural, not decoration.
    """
    live = [r for r in rows if r["count"] > 0]
    if not live:
        return ""
    peak = max(r["count"] for r in live) or 1
    label_w, plot_w, value_w = 138, 250, 128
    step = 30
    total_h = 8 + step * len(live) + 8
    parts = [
        '<figure class="chart">',
        '<figcaption><span class="chart-title">Where the fortnight\'s work sits in the '
        'approval pipeline</span><span class="chart-sub">Count of projects, and verified '
        'construction value at each step. Later steps mean sooner work.</span></figcaption>',
        f'<svg viewBox="0 0 {label_w + plot_w + value_w} {total_h}" role="img" '
        'aria-label="Approval pipeline funnel" class="chart-svg">',
    ]
    for i, row in enumerate(live):
        y = 8 + i * step
        cy = y + step / 2
        w = max(2.0, (row["count"] / peak) * plot_w)
        # Later stages are nearer to work starting, so they read stronger.
        t = i / max(1, len(live) - 1)
        fill = f"rgb({int(20 + 0 * t)},{int(102 - 20 * t)},{int(224 - 60 * t)})"
        parts.append(
            f'<text x="{label_w - 10}" y="{cy}" text-anchor="end" '
            f'dominant-baseline="central" class="c-lab">{e(row["label"])}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{cy - 7:.1f}" width="{w:.1f}" height="14" '
            f'rx="4" ry="4" fill="{fill}" />'
        )
        parts.append(
            f'<text x="{label_w + w + 8:.1f}" y="{cy}" dominant-baseline="central" '
            f'class="c-val">{row["count"]} · {e(money(row["value"], 1))}</text>'
        )
    parts.append("</svg></figure>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# card rendering
# ---------------------------------------------------------------------------

def score_block(project: dict) -> str:
    score = project["opportunity_score"]
    return (
        f'<div class="score" data-p="{e(project["priority"])}">'
        f'<span class="score-num">{score}</span>'
        f'<span class="score-cap">score</span>'
        f'<span class="score-meter" aria-hidden="true">'
        f'<span class="score-fill" style="width:{score}%"></span></span>'
        f"</div>"
    )


def job_card(project: dict, rank: int | None = None) -> str:
    conf_text, conf_tone = CONF_LABEL[project["cost_confidence"]]
    cat = project["filter_group"]
    colour = CAT_COLORS.get(cat, "#1466E0")

    facts = []
    if project.get("cost"):
        facts.append(("Declared cost", money_full(project["cost"])))
    if project.get("electrical_estimate"):
        lo, hi = project["electrical_estimate"]
        pct = project["electrical_share_pct"]
        facts.append((
            "Electrical opportunity",
            f'{money(lo)} – {money(hi)} <span class="fine">({pct[0]:g}–{pct[1]:g}% est.)</span>',
        ))
    if project.get("dwellings_new"):
        facts.append(("Dwellings", f'{project["dwellings_new"]:,}'))
    if project.get("lots_proposed"):
        facts.append(("Lots", f'{project["lots_proposed"]:,}'))
    if project.get("gfa_proposed"):
        facts.append(("Proposed floor area", f'{project["gfa_proposed"]:,.0f} m²'))
    if project.get("storeys"):
        facts.append(("Storeys", str(project["storeys"])))
    if project.get("distance_km") is not None:
        facts.append(("From Newcastle CBD", f'{project["distance_km"]:.0f} km'))

    fact_html = "".join(
        f'<div class="fact"><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in facts
    )

    scope_html = "".join(f"<li>{e(s)}</li>" for s in project["scope"][:8])
    signals_html = "".join(f'<li>{e(s)}</li>' for s in project.get("signals", [])[:5])

    builder_html = ""
    if project.get("builder"):
        builder_html = (
            f'<p class="builder"><span class="builder-cap">Builder on the certificate</span>'
            f'<strong>{e(project["builder"])}</strong></p>'
        )

    corr = project.get("corroboration")
    corr_html = ""
    if corr:
        src = (
            f' <a href="{e(corr["source_url"])}">{e(corr["source"])}</a>'
            if corr.get("source_url") else f' {e(corr["source"])}'
        )
        corr_html = (
            f'<aside class="corr"><span class="corr-cap">Cross-checked against '
            f'a second source</span><p>{e(corr["note"])}<span class="src">Source:{src}</span></p></aside>'
        )

    warn_html = ""
    if project["cost_confidence"] in ("suspect", "unverified"):
        flags = ", ".join(project["quality_flags"])
        warn_html = (
            f'<aside class="warn"><strong>Treat the dollar figure with caution.</strong> '
            f'The lodged cost is {money_full(project.get("cost"))} but it fails our '
            f'plausibility check ({e(flags)}). The project is real — the number is not '
            f'confirmed. Verify before you size a quote off it.</aside>'
        )

    rank_html = f'<span class="rank">{rank:02d}</span>' if rank else ""
    second_chip = (
        f'<span class="chip chip-plain">{e(project["category_label"])}</span>'
        if project["category_label"].lower() != cat.lower() else ""
    )

    return f"""
<article class="card" style="--cat:{colour}">
  <header class="card-head">
    <div class="card-id">
      {rank_html}
      <span class="chip" style="--chip:{colour}">{e(cat)}</span>
      {second_chip}
    </div>
    {score_block(project)}
  </header>
  <h3 class="card-title">{e(project["project_name"])}</h3>
  <p class="card-where">{e(project["address"])} · <span class="lga">{e(project["council_short"])}</span></p>
  <p class="card-stage"><span class="dot" aria-hidden="true"></span>{e(project["stage_label"])}
     <span class="sep">·</span> {e(project["status_raw"])}
     <span class="sep">·</span> updated {e(short_date(project.get("date_last_updated")))}
     <span class="conf conf-{conf_tone}">{e(conf_text)}</span></p>
  {warn_html}
  <dl class="facts">{fact_html}</dl>
  {builder_html}
  <div class="cols">
    <div class="col">
      <h4>Likely electrical scope</h4>
      <ul class="scope">{scope_html}</ul>
    </div>
    <div class="col">
      <h4>What to do about it</h4>
      <p class="play"><span class="play-when">{e(project["contact_window"])}</span>
         {e(project["contact_angle"])}</p>
      <p class="play-who"><strong>Who:</strong> {e(project["contact_target"])}</p>
      {f'<h4 class="mt">Why it scored</h4><ul class="sig">{signals_html}</ul>' if signals_html else ""}
    </div>
  </div>
  {corr_html}
  <footer class="card-foot">
    <span class="ref">{e(project["source_ref"])}</span>
    {f'<span class="ref">{e(project["council_ref"])}</span>' if project.get("council_ref") else ""}
    <span class="ref-note">NSW Planning Portal reference · verify on the council DA tracker before quoting</span>
  </footer>
</article>"""


def compact_row(project: dict) -> str:
    return f"""<tr>
  <td class="t-score" data-p="{e(project['priority'])}">{project['opportunity_score']}</td>
  <td class="t-name"><strong>{e(project['project_name'])}</strong>
      <span class="t-addr">{e(project['address'])}</span></td>
  <td class="t-lga">{e(project['council_short'])}</td>
  <td class="t-stage">{e(project['stage_label'])}</td>
  <td class="t-cost">{e(money(project.get('cost')))}</td>
  <td class="t-elec">{e(band(project.get('electrical_estimate')))}</td>
  <td class="t-builder">{e(project.get('builder') or '—')}</td>
</tr>"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

TOKENS_LIGHT = """
  --ink:#0A1628; --ink-2:#243A56; --grey:#5A6B82; --grey-2:#8494A8;
  --paper:#F6F8FB; --card:#FFFFFF; --rule:#DDE4EE; --rule-2:#EDF1F7;
  --navy:#0F2338; --navy-2:#1B3A5A;
  --blue:#0B6BF2; --blue-ink:#0A4FB4; --blue-wash:#EAF2FE;
  --green:#00E07A; --green-ink:#00713F; --green-wash:#E4FAEF;
  --good:#00713F; --warn:#8A5107; --warn-wash:#FDF3E3; --bad:#A32A20;
  --on-navy:#EAF1FA; --on-navy-2:#9DB4CE;
"""

TOKENS_DARK = """
  --ink:#E9EFF7; --ink-2:#BFCEDF; --grey:#93A5BA; --grey-2:#6E8299;
  --paper:#080F1A; --card:#0F1B2B; --rule:#22344A; --rule-2:#17263A;
  --navy:#0A1424; --navy-2:#16293F;
  --blue:#5B9CFF; --blue-ink:#8FBEFF; --blue-wash:#12243D;
  --green:#00E07A; --green-ink:#41E39A; --green-wash:#0B2A1D;
  --good:#41E39A; --warn:#E0A458; --warn-wash:#2B2113; --bad:#F0796B;
  --on-navy:#EAF1FA; --on-navy-2:#9DB4CE;
"""

BASE_CSS = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:"IBM Plex Sans","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:15px;line-height:1.55;font-feature-settings:"kern" 1}
.wrap{max-width:1080px;margin:0 auto;padding-inline:20px;padding-block:0 64px}
h1,h2,h3,h4{font-family:Archivo,"Arial Narrow",Helvetica,sans-serif;
  text-wrap:balance;margin:0;letter-spacing:-.015em}
a{color:var(--blue-ink)}
.mono{font-family:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
.num{font-variant-numeric:tabular-nums}

/* ---------- masthead ---------- */
.mast{background:var(--navy);color:var(--on-navy);padding-block:34px 0;
  border-bottom:3px solid var(--green)}
.mast-in{max-width:1080px;margin:0 auto;padding-inline:20px}
.brandline{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.logo{font-family:Archivo,sans-serif;font-weight:800;font-size:26px;
  letter-spacing:-.03em;color:#fff}
.logo .sig{color:var(--green)}
.issue{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--on-navy-2);border:1px solid #2C4763;
  border-radius:3px;padding:3px 8px}
.mast h1{font-size:clamp(28px,5vw,44px);font-weight:800;color:#fff;
  margin-top:18px;line-height:1.05;max-width:22ch}
.mast .dek{color:var(--on-navy-2);max-width:62ch;margin-top:12px;font-size:16px}
.mast .cover{display:flex;flex-wrap:wrap;gap:8px 22px;margin-top:20px;
  font-size:12.5px;color:var(--on-navy-2)}
.mast .cover b{color:#fff;font-weight:600}

/* the summary strip: label/value pairs, not a row of shadowed cards */
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:1px;background:#2C4763;margin-top:28px;
  border-top:1px solid #2C4763;border-bottom:1px solid #2C4763}
.strip>div{background:var(--navy);padding:16px 18px}
.strip dt{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--on-navy-2);margin:0 0 6px}
.strip dd{margin:0;font-family:Archivo,sans-serif;font-weight:700;font-size:25px;
  color:#fff;font-variant-numeric:tabular-nums;line-height:1.1}
.strip dd small{display:block;font-family:"IBM Plex Sans",sans-serif;
  font-weight:400;font-size:11.5px;color:var(--on-navy-2);margin-top:5px;
  letter-spacing:0;line-height:1.35}

/* ---------- sections ---------- */
section{margin-top:52px}
.sec-head{border-bottom:2px solid var(--ink);padding-bottom:10px;
  display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
.sec-head h2{font-size:clamp(21px,3vw,27px);font-weight:800}
.sec-head .count{font-family:"IBM Plex Mono",monospace;font-size:12px;
  color:var(--grey);letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}
.sec-lede{color:var(--grey);max-width:68ch;margin:14px 0 0;font-size:15px}

/* ---------- job cards ---------- */
.cards{display:flex;flex-direction:column;gap:18px;margin-top:22px}
.card{background:var(--card);border:1px solid var(--rule);
  border-left:4px solid var(--cat);border-radius:2px;padding:20px 22px}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;
  gap:14px;flex-wrap:wrap}
.card-id{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rank{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;
  color:var(--grey-2);letter-spacing:.05em}
.chip{font-size:10.5px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
  color:#fff;background:var(--chip);padding:3px 8px;border-radius:2px}
.chip-plain{background:transparent;color:var(--grey);border:1px solid var(--rule)}

.score{display:grid;grid-template-columns:auto auto;grid-template-rows:auto auto;
  align-items:baseline;gap:0 7px;min-width:104px;
  border:1px solid var(--rule);border-radius:2px;padding:7px 10px 8px;
  background:var(--paper)}
.score-num{font-family:Archivo,sans-serif;font-weight:800;font-size:27px;
  line-height:1;font-variant-numeric:tabular-nums}
.score-cap{font-family:"IBM Plex Mono",monospace;font-size:9.5px;
  letter-spacing:.14em;text-transform:uppercase;color:var(--grey-2)}
.score-meter{grid-column:1/-1;margin-top:8px;height:4px;background:var(--rule);
  border-radius:2px;overflow:hidden}
.score-fill{display:block;height:100%;background:var(--blue)}
.score[data-p="high"] .score-num{color:var(--green-ink)}
.score[data-p="high"] .score-fill{background:var(--green-ink)}
.score[data-p="medium"] .score-num{color:var(--blue-ink)}

.card-title{font-size:20px;font-weight:700;margin-top:14px;line-height:1.2}
.card-where{margin:5px 0 0;color:var(--grey);font-size:14px}
.card-where .lga{font-weight:600;color:var(--ink-2)}
.card-stage{margin:10px 0 0;font-size:13px;color:var(--grey);
  display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.card-stage .dot{width:7px;height:7px;border-radius:50%;background:var(--cat);flex:none}
.card-stage .sep{color:var(--rule)}
.conf{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
  padding:2px 7px;border-radius:2px;border:1px solid currentColor}
.conf-good{color:var(--good)} .conf-warn{color:var(--warn)} .conf-neutral{color:var(--grey-2)}

.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
  gap:14px 20px;margin:18px 0 0;padding:16px 0;
  border-top:1px solid var(--rule-2);border-bottom:1px solid var(--rule-2)}
.fact dt{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--grey-2);margin-bottom:3px}
.fact dd{margin:0;font-weight:600;font-size:16px;font-variant-numeric:tabular-nums}
.fine{font-weight:400;font-size:12px;color:var(--grey)}

.builder{margin:16px 0 0;padding:11px 14px;background:var(--blue-wash);
  border-left:3px solid var(--blue);font-size:15px}
.builder-cap{display:block;font-size:10.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--blue-ink);margin-bottom:3px}

.cols{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px}
.col h4{font-size:11px;letter-spacing:.11em;text-transform:uppercase;
  color:var(--grey-2);margin-bottom:9px;font-weight:600}
.col h4.mt{margin-top:16px}
.scope,.sig{margin:0;padding-left:0;list-style:none;font-size:14px}
.scope li,.sig li{padding-left:15px;position:relative;margin-bottom:4px;color:var(--ink-2)}
.scope li::before{content:"";position:absolute;left:0;top:.62em;width:6px;height:2px;
  background:var(--cat)}
.sig li::before{content:"+";position:absolute;left:0;color:var(--green-ink);font-weight:700}
.play{margin:0;font-size:14px;color:var(--ink-2)}
.play-when{display:inline-block;font-weight:700;color:var(--ink);
  background:var(--green-wash);padding:1px 7px;border-radius:2px;margin-right:5px}
.play-who{margin:9px 0 0;font-size:14px;color:var(--ink-2)}

.warn{margin:16px 0 0;padding:12px 14px;background:var(--warn-wash);
  border-left:3px solid var(--warn);font-size:13.5px;color:var(--ink-2)}
.corr{margin:18px 0 0;padding:13px 15px;border:1px dashed var(--rule);
  border-radius:2px;font-size:13.5px;color:var(--ink-2);background:var(--paper)}
.corr-cap{display:block;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--green-ink);font-weight:600;margin-bottom:5px}
.corr p{margin:0}
.src{display:block;margin-top:7px;font-size:12px;color:var(--grey)}

.card-foot{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:18px;
  padding-top:13px;border-top:1px solid var(--rule-2)}
.ref{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-2);
  background:var(--rule-2);padding:2px 7px;border-radius:2px}
.ref-note{font-size:11.5px;color:var(--grey-2)}

/* ---------- tables ---------- */
.tbl-wrap{overflow-x:auto;margin-top:20px;border:1px solid var(--rule);border-radius:2px}
table{width:100%;border-collapse:collapse;font-size:13.5px;min-width:720px}
thead th{text-align:left;font-family:"IBM Plex Sans",sans-serif;font-size:10.5px;
  letter-spacing:.1em;text-transform:uppercase;color:var(--grey);font-weight:600;
  padding:11px 12px;background:var(--paper);border-bottom:1px solid var(--rule);
  white-space:nowrap}
tbody td{padding:11px 12px;border-bottom:1px solid var(--rule-2);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
.t-score{font-family:"IBM Plex Mono",monospace;font-weight:600;
  font-variant-numeric:tabular-nums;width:44px;color:var(--blue-ink)}
.t-score[data-p="high"]{color:var(--green-ink)}
.t-name strong{display:block;font-weight:600}
.t-addr{display:block;color:var(--grey);font-size:12.5px;margin-top:2px}
.t-cost,.t-elec{font-variant-numeric:tabular-nums;white-space:nowrap}
.t-builder{color:var(--ink-2);font-size:12.5px}
.t-lga,.t-stage{color:var(--grey);white-space:nowrap;font-size:12.5px}

/* ---------- charts ---------- */
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:24px}
.chart{margin:0}
.chart figcaption{margin-bottom:12px}
.chart-title{display:block;font-family:Archivo,sans-serif;font-weight:700;font-size:15px}
.chart-sub{display:block;color:var(--grey);font-size:13px;margin-top:3px;max-width:52ch}
.chart-svg{width:100%;height:auto;display:block;overflow:visible}
.chart-wide{max-width:660px}
.c-lab{font-family:"IBM Plex Sans",sans-serif;font-size:12.5px;fill:var(--ink-2)}
.c-val{font-family:"IBM Plex Mono",monospace;font-size:11.5px;fill:var(--grey);
  font-variant-numeric:tabular-nums}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin-top:16px;font-size:12.5px;
  color:var(--ink-2)}
.legend span{display:flex;align-items:center;gap:7px}
.legend i{width:11px;height:11px;border-radius:2px;flex:none}

/* ---------- pipeline (public projects) ---------- */
.pub{display:flex;flex-direction:column;gap:0;margin-top:22px;
  border-top:1px solid var(--rule)}
.pub-item{padding:18px 0;border-bottom:1px solid var(--rule)}
.pub-top{display:flex;justify-content:space-between;gap:16px;align-items:baseline;
  flex-wrap:wrap}
.pub-item h3{font-size:17px;font-weight:700;max-width:46ch}
.pub-val{font-family:Archivo,sans-serif;font-weight:700;font-size:19px;
  color:var(--blue-ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.pub-meta{display:flex;gap:8px 16px;flex-wrap:wrap;margin-top:6px;font-size:12.5px;
  color:var(--grey)}
.pub-meta b{color:var(--ink-2);font-weight:600}
.pub-item p{margin:11px 0 0;font-size:14px;color:var(--ink-2);max-width:78ch}
.pub-elec{margin-top:10px;padding:11px 14px;background:var(--blue-wash);
  border-left:3px solid var(--blue);font-size:13.5px}
.pub-elec b{display:block;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--blue-ink);margin-bottom:3px}

/* ---------- method / notes ---------- */
.method{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:34px}
.method h3{font-size:15px;font-weight:700;margin-bottom:9px}
.method p{margin:0 0 12px;font-size:14px;color:var(--ink-2);max-width:62ch}
.method ul{margin:0 0 12px;padding-left:18px;font-size:14px;color:var(--ink-2)}
.method li{margin-bottom:5px}
.note{border:1px solid var(--rule);border-left:3px solid var(--blue);
  padding:16px 18px;background:var(--card);margin-top:20px}
.note h3{margin-bottom:8px}
.qtab{margin-top:16px}
.disclaim{margin-top:36px;padding-top:20px;border-top:2px solid var(--ink);
  font-size:12.5px;color:var(--grey);max-width:88ch}
.disclaim strong{color:var(--ink-2)}
.foot{margin-top:34px;padding-top:18px;border-top:1px solid var(--rule);
  display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;
  font-size:12.5px;color:var(--grey)}

@media (max-width:760px){
  .cols,.chart-grid,.method{grid-template-columns:1fr;gap:20px}
  .card{padding:16px 15px}
  .strip dd{font-size:22px}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

PRINT_CSS = """
@page{size:A4;margin:14mm 13mm 16mm}
html{font-size:10.2pt}
body{background:#fff;font-size:9.6pt;line-height:1.45}
.wrap{max-width:none;padding-inline:0;padding-block:0}
.mast{margin-bottom:0;padding-block:0 0;border-bottom:3px solid #00B366}
.mast-in{padding-inline:0;padding-block:9mm 0}
.strip{margin-top:9mm}
.strip>div{padding:9px 11px}
.strip dd{font-size:16pt}
.strip dd small{font-size:7.6pt}
.mast h1{font-size:26pt}
.mast .dek{font-size:10.5pt}
section{margin-top:9mm;page-break-inside:auto}
.sec-head{page-break-after:avoid}
.card{page-break-inside:avoid;border:1px solid #DDE4EE;border-left:4px solid var(--cat);
  margin:0}
.cards{gap:5mm}
.pub-item{page-break-inside:avoid}
.chart{page-break-inside:avoid}
table{min-width:0;font-size:8.4pt}
thead{display:table-header-group}
tr{page-break-inside:avoid}
.tbl-wrap{overflow:visible}
.pagebreak{page-break-before:always;break-before:page}
a{color:#0A4FB4;text-decoration:none}
.no-print{display:none!important}
/* Restore the two-column card body: the phone breakpoint must not apply to A4. */
.cols{grid-template-columns:1fr 1fr!important;gap:14px!important}
.facts{grid-template-columns:repeat(auto-fit,minmax(104px,1fr))!important;
  gap:8px 14px!important;margin-top:10px!important;padding:9px 0!important}
.chart-grid{grid-template-columns:1fr 1fr!important;gap:18px!important}
.method{grid-template-columns:1fr 1fr!important;gap:20px!important}
/* Tighter print rhythm so cards pack two to a page instead of one. */
.card{padding:11px 13px}
.card-title{font-size:12.6pt;margin-top:9px}
.card-where{font-size:8.8pt}
.card-stage{margin-top:6px;font-size:8.4pt}
.fact dd{font-size:10pt}
.builder{margin-top:10px;padding:7px 10px;font-size:9.4pt}
.cols{margin-top:12px}
.scope li,.sig li{margin-bottom:2px}
.scope,.sig,.play,.play-who{font-size:8.8pt}
.card-foot{margin-top:11px;padding-top:8px}
.corr,.warn{margin-top:11px;padding:9px 11px;font-size:8.6pt}
.sec-lede{page-break-after:avoid;margin-top:9px}
.strip dd small{line-height:1.3}
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Archivo:wght@600;700;800&"
    "family=IBM+Plex+Mono:wght@400;500;600&"
    "family=IBM+Plex+Sans:wght@400;500;600;700&display=swap\">"
)


# ---------------------------------------------------------------------------
# body
# ---------------------------------------------------------------------------

def render_body(p: dict, for_print: bool) -> str:
    t = p["totals"]
    q = p["quality"]["cost_confidence"]
    issue_date = pretty_date(p["generated"])
    from_date = pretty_date(t["window_from"])

    # --- masthead ---------------------------------------------------------
    strip = [
        ("New or updated", f'{t["recent_count"]:,}',
         f'projects across five councils in the {t["window_days"]} days to {short_date(t["window_to"])}'),
        ("Worth acting on", f'{t["recent_high"] + t["recent_medium"]}',
         f'{t["recent_high"]} high priority, {t["recent_medium"]} medium — the rest is filtered out for you'),
        ("Verified construction value", money(t["recent_value"], 2),
         "declared cost, cross-checked against floor area and dwelling counts"),
        ("Estimated electrical share", f'{money(t["recent_elec_low"], 1)}+',
         f'range {money(t["recent_elec_low"], 1)} – {money(t["recent_elec_high"], 1)}; an estimate, not a quote'),
        ("Builders named", f'{t["builders_named"]}',
         "certificates that name the building company, so you know who to ring"),
    ]
    strip_html = "".join(
        f"<div><dt>{e(a)}</dt><dd>{e(b)}<small>{e(c)}</small></dd></div>" for a, b, c in strip
    )

    mast = f"""
<header class="mast">
  <div class="mast-in">
    <div class="brandline">
      <span class="logo">Tradie<span class="sig">signal</span></span>
      <span class="issue">Issue {p["issue"]:02d} · {e(short_date(p["generated"]))} {e(p["generated"][:4])}</span>
    </div>
    <h1>Hunter Electrical Opportunity Report</h1>
    <p class="dek">Every development application, complying development certificate and
      construction certificate lodged with the five Hunter councils in the fortnight to
      {e(issue_date)} — scored, filtered, and turned into a call list.</p>
    <div class="cover">
      <span><b>Coverage</b> Newcastle · Lake Macquarie · Maitland · Port Stephens · Cessnock</span>
      <span><b>Period</b> {e(from_date)} to {e(issue_date)}</span>
      <span><b>Source</b> NSW Planning Portal ePlanning open data (CC-BY)</span>
    </div>
    <dl class="strip">{strip_html}</dl>
  </div>
</header>"""

    # --- act now ----------------------------------------------------------
    act_cards = "".join(job_card(x, i + 1) for i, x in enumerate(p["act_now"]))
    act = f"""
<section id="act">
  <div class="sec-head">
    <h2>Ring these this week</h2>
    <span class="count">{len(p["act_now"])} projects · certificate stage</span>
  </div>
  <p class="sec-lede">These have passed the certificate stage, which means the builder is
    appointing trades right now or has just done it. This is the shortest window in the
    whole pipeline and the only section where a phone call this week changes the outcome.
    Where the certificate names the building company, we have printed it.</p>
  <div class="cards">{act_cards}</div>
</section>"""

    # --- pipeline ---------------------------------------------------------
    pipe = ""
    if p["pipeline"]:
        pipe_cards = "".join(job_card(x, i + 1) for i, x in enumerate(p["pipeline"]))
        pipe = f"""
<section id="pipeline" class="pagebreak">
  <div class="sec-head">
    <h2>High and medium priority, further out</h2>
    <span class="count">{len(p["pipeline"])} projects</span>
  </div>
  <p class="sec-lede">Approved or progressing, but the trades are not being appointed yet.
    The play here is a short introduction now so that you are already a name when the
    package goes out.</p>
  <div class="cards">{pipe_cards}</div>
</section>"""

    # --- charts -----------------------------------------------------------
    council_chart = hbar_chart(
        p["by_council"], "value",
        lambda r: f'{money(r["value"], 1)} · {r["count"]}',
        "#1466E0",
        "Where the money is, by council",
        "Verified construction value this fortnight, then project count.",
    )
    group_rows = [r for r in p["by_group"] if r["count"] > 0]
    group_chart = hbar_chart(
        group_rows, "value",
        lambda r: f'{money(r["value"], 1)} · {r["count"]}',
        lambda r: CAT_COLORS.get(r["label"], "#1466E0"),
        "Where the money is, by sector",
        "Residential dominates by count; commercial dominates by value.",
    )
    legend = "".join(
        f'<span><i style="background:{CAT_COLORS[k]}"></i>{e(k)}</span>' for k in CAT_COLORS
    )
    funnel = funnel_chart(p["by_stage"])

    charts = f"""
<section id="numbers" class="pagebreak">
  <div class="sec-head">
    <h2>The fortnight in numbers</h2>
    <span class="count">{t["recent_count"]:,} projects analysed</span>
  </div>
  <div class="chart-grid">{council_chart}{group_chart}</div>
  <div class="legend">{legend}</div>
  <div class="chart-wide" style="margin-top:32px">{funnel}</div>
</section>"""

    # --- sector sections --------------------------------------------------
    sector_blocks = []
    order = ["Commercial", "Industrial", "Government", "Infrastructure", "Residential"]
    for name in order:
        rows = p["sectors"].get(name) or []
        if not rows:
            continue
        body = "".join(compact_row(x) for x in rows)
        sector_blocks.append(f"""
<h3 style="margin-top:30px;font-size:16px;display:flex;align-items:center;gap:9px">
  <span style="width:11px;height:11px;border-radius:2px;background:{CAT_COLORS[name]};
    display:inline-block;flex:none"></span>{e(name)}
  <span style="font-family:'IBM Plex Mono',monospace;font-size:11.5px;font-weight:400;
    color:var(--grey);letter-spacing:.06em">{len(rows)} shown</span>
</h3>
<div class="tbl-wrap"><table>
  <thead><tr><th>Score</th><th>Project</th><th>Council</th><th>Stage</th>
    <th>Cost</th><th>Electrical est.</th><th>Builder</th></tr></thead>
  <tbody>{body}</tbody>
</table></div>""")

    sectors = f"""
<section id="sectors" class="pagebreak">
  <div class="sec-head">
    <h2>By sector</h2>
    <span class="count">score 55 and above</span>
  </div>
  <p class="sec-lede">The same fortnight, sorted the way you probably think about your
    business. Everything below scored 55 or better; the low-value noise — pools, sheds,
    fences, decks — has been removed.</p>
  {"".join(sector_blocks)}
</section>"""

    # --- early big --------------------------------------------------------
    early = ""
    if p["early_big"]:
        rows = "".join(compact_row(x) for x in p["early_big"])
        early = f"""
<section id="early">
  <div class="sec-head">
    <h2>Big applications, early stage</h2>
    <span class="count">{len(p["early_big"])} projects over $3m</span>
  </div>
  <p class="sec-lede">Nothing to quote here for months. It is on the list because the
    cheapest lead you will ever get is the one you knew about before the builder was
    appointed. One introduction email now.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Score</th><th>Project</th><th>Council</th><th>Stage</th>
      <th>Cost</th><th>Electrical est.</th><th>Builder</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>"""

    # --- builder watchlist ------------------------------------------------
    wl_rows = []
    for i, b in enumerate(p["watchlist"], 1):
        top = b.get("top")
        top_html = (
            f'<strong>{e(top["name"])}</strong><span class="t-addr">{money_full(top["cost"])}</span>'
            if top else "—"
        )
        wl_rows.append(f"""<tr>
  <td class="t-score">{i:02d}</td>
  <td class="t-name"><strong>{e(b["builder"])}</strong>
    <span class="t-addr">{e(", ".join(b["councils"]))}</span></td>
  <td class="t-cost">{e(money(b["value"], 1))}</td>
  <td class="t-lga num">{b["jobs"]}</td>
  <td class="t-lga num">{b["recent"]}</td>
  <td class="t-name">{top_html}</td>
</tr>""")
    watchlist = f"""
<section id="builders" class="pagebreak">
  <div class="sec-head">
    <h2>Builder watchlist</h2>
    <span class="count">top {len(p["watchlist"])} by tracked value</span>
  </div>
  <p class="sec-lede">This is the part no council website will give you. Construction
    certificates name the building company, so over time you can see who is actually
    building in the Hunter and how much of it. Treat this as your target account list:
    winning one relationship here is worth more than fifty cold quotes.</p>
  <div class="tbl-wrap"><table>
    <thead><tr><th>#</th><th>Builder</th><th>Tracked value</th><th>Jobs</th>
      <th>New this fortnight</th><th>Largest tracked project</th></tr></thead>
    <tbody>{"".join(wl_rows)}</tbody>
  </table></div>
</section>"""

    # --- hot suburbs ------------------------------------------------------
    sub_chart = hbar_chart(
        [{"label": s["suburb"], "value": s["value"], "count": s["count"]} for s in p["hot_suburbs"]],
        "value",
        lambda r: f'{money(r["value"], 1)} · {r["count"]}',
        "#1466E0",
        "Busiest suburbs this fortnight",
        "Verified construction value, then number of projects. Useful for planning a run of site visits in one trip.",
        height_per=30,
    )
    suburbs = f"""
<section id="suburbs">
  <div class="sec-head">
    <h2>Where to point the ute</h2>
    <span class="count">top {len(p["hot_suburbs"])} suburbs</span>
  </div>
  <div class="chart-wide">{sub_chart}</div>
</section>"""

    # --- public pipeline --------------------------------------------------
    pub_items = []
    for x in p["public_pipeline"]:
        src = (
            f'<a href="{e(x["source_url"])}">{e(x["source"])}</a>'
            if x.get("source_url") else e(x["source"])
        )
        pub_items.append(f"""
<div class="pub-item">
  <div class="pub-top">
    <h3>{e(x["name"])}</h3>
    <span class="pub-val">{e(x["value"])}</span>
  </div>
  <div class="pub-meta">
    <span><b>Where</b> {e(x["where"])}</span>
    <span><b>Stage</b> {e(x["stage"])}</span>
    <span><b>Source</b> {src}</span>
  </div>
  <p>{e(x["detail"])}</p>
  <div class="pub-elec"><b>What it means for an electrician</b>{e(x["electrical"])}</div>
</div>""")

    public = f"""
<section id="public" class="pagebreak">
  <div class="sec-head">
    <h2>The public pipeline</h2>
    <span class="count">{money(t["public_pipeline_value"], 1)} of funded work</span>
  </div>
  <p class="sec-lede">State and federally funded Hunter work does not appear in council
    development application data, because it runs through separate approval pathways.
    This section is compiled by hand from the NSW Budget papers and agency
    announcements. These are the jobs that will still be going in three years.</p>
  <div class="pub">{"".join(pub_items)}</div>
</section>"""

    # --- method -----------------------------------------------------------
    total_q = sum(q.values()) or 1
    checked_pct = round(100 * (q.get("high", 0) + q.get("medium", 0)) / total_q)
    suspect_n = q.get("suspect", 0) + q.get("unverified", 0)

    method = f"""
<section id="method" class="pagebreak">
  <div class="sec-head">
    <h2>How this report is made</h2>
    <span class="count">method and limits</span>
  </div>
  <div class="method">
    <div>
      <h3>Where the data comes from</h3>
      <p>Every council project in this report is drawn from the NSW Planning Portal's
        ePlanning open data feeds, published by the NSW Department of Planning, Housing
        and Infrastructure under a Creative Commons Attribution licence and refreshed
        daily. We pull three separate feeds:</p>
      <ul>
        <li><strong>Development applications</strong> — the pipeline, typically 6 to 24
          months before anyone picks up a tool.</li>
        <li><strong>Complying development certificates</strong> — fast-tracked work that
          can start almost immediately.</li>
        <li><strong>Construction certificates</strong> — the strongest signal there is.
          A certificate means the job is about to be built, and it often names the
          building company.</li>
      </ul>
      <p>Records for the same address across all three feeds are merged into one project
        so you see a single entry with its history, not the same job three times.</p>

      <h3>How the score works</h3>
      <p>Each project is scored out of 100 from five inputs: the kind of development,
        how far through approval it is, the declared cost, the distance from Newcastle,
        and specific high-intent signals such as a named builder, a large dwelling
        count, or solar and EV scope in the application. Sector and stage do most of the
        work — a construction certificate for a medical centre outranks a much larger
        development application for a subdivision, because one needs an electrician in
        a fortnight and the other in two years.</p>
    </div>
    <div>
      <h3>What is fact and what is our estimate</h3>
      <p><strong>Fact, straight from the government feed:</strong> the address, the
        development type, the approval stage and dates, the declared cost of
        development, the dwelling and lot counts, the floor area, the building code
        class, and the builder's name where a certificate records it.</p>
      <p><strong>Our estimate, not a quote:</strong> the opportunity score, the
        electrical share of the cost, the likely scope of works, and the suggested
        timing. The electrical percentages are industry rules of thumb applied to a
        declared cost. Use them to rank where to spend your week, never to price a job.</p>

      <h3>Data quality</h3>
      <p>Declared costs on planning applications are entered by applicants and are not
        audited, so the raw feed contains obvious errors — this fortnight it included a
        two-dwelling development in Nelson Bay lodged at $1.375 billion. We cross-check
        every figure against floor area, dwelling count and lot count where the feed
        supplies them.</p>
      <ul>
        <li><strong>{checked_pct}%</strong> of costs passed a plausibility cross-check.</li>
        <li><strong>{suspect_n}</strong> records were flagged as implausible or
          uncorroborated. They are still listed, because the project is real, but the
          dollar figure is marked and excluded from every total in this report.</li>
        <li><strong>{q.get("unknown", 0)}</strong> records lodged no cost at all.</li>
      </ul>

      <h3>What this report cannot tell you</h3>
      <ul>
        <li>Who holds the electrical package. A named builder is a door, not a contract.</li>
        <li>Whether a job is already let. Always ask.</li>
        <li>Private work under the certificate threshold, or maintenance and service work,
          which never appears in planning data at all.</li>
      </ul>
    </div>
  </div>

  <div class="note">
    <h3>Verify before you quote</h3>
    <p>Every entry carries its NSW Planning Portal reference and, where available, the
      council's own application number. Before you price anything, look the reference up
      on the council's DA tracker to confirm the current status. Approvals get modified,
      withdrawn and appealed, and this report is a snapshot dated
      {e(issue_date)}.</p>
  </div>

  <p class="disclaim"><strong>Sources and licence.</strong> Council development data:
    NSW Planning Portal ePlanning open data APIs, © State of New South Wales
    (Department of Planning, Housing and Infrastructure), used under a Creative Commons
    Attribution 4.0 licence. Public pipeline figures: NSW Budget 2026-27 regional
    papers, EnergyCo NSW, and the sources cited against each item.
    <strong>Not financial or contractual advice.</strong> Tradiesignal aggregates public
    records and applies its own scoring. Figures described as estimates are estimates.
    Verify every project against the primary source before committing time or money.</p>
</section>"""

    foot = f"""
<footer class="foot">
  <span>Tradiesignal · Hunter Electrical Opportunity Report · Issue {p["issue"]:02d}</span>
  <span>Compiled {e(issue_date)} · Newcastle NSW</span>
</footer>"""

    return (
        mast
        + '<div class="wrap">'
        + act + pipe + charts + sectors + early + watchlist + suburbs + public + method + foot
        + "</div>"
    )


def render(p: dict, for_print: bool) -> str:
    if for_print:
        css = f":root{{{TOKENS_LIGHT}}}\n{BASE_CSS}\n{PRINT_CSS}"
        head_extra = ""
    else:
        css = (
            f":root{{{TOKENS_LIGHT}}}\n"
            f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{{TOKENS_DARK}}}}}\n'
            f':root[data-theme="dark"]{{{TOKENS_DARK}}}\n'
            f"{BASE_CSS}"
        )
        head_extra = ""
    title = "Hunter Electrical Opportunity Report"
    body = render_body(p, for_print)
    doctype = "<!doctype html>\n<html lang=\"en-AU\"><head><meta charset=\"utf-8\">" \
              "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" if for_print else ""
    if for_print:
        return (
            f"{doctype}<title>{title}</title>{FONT_LINK}<style>{css}</style>"
            f"{head_extra}</head><body>{body}</body></html>"
        )
    # Artifact publish path: the tool supplies the skeleton, so emit content only.
    return f"<title>{title}</title>{FONT_LINK}<style>{css}</style>{body}"


def main() -> None:
    payload = json.loads((DATA / "report_payload.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report_print.html").write_text(render(payload, True), encoding="utf-8")
    (OUT / "report_web.html").write_text(render(payload, False), encoding="utf-8")
    for name in ("report_print.html", "report_web.html"):
        size = (OUT / name).stat().st_size
        print(f"wrote reports/{name}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
