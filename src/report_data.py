#!/usr/bin/env python3
"""
Tradiesignal :: report data builder
===================================
Turns the scored project set into the exact slices the weekly report and the
dashboard need, plus the manually curated "public pipeline" of state-funded
Hunter projects that never appear in council DA data.

Writes data/report_payload.json.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA = Path("data")
WINDOW_DAYS = 14  # the reporting fortnight


# ---------------------------------------------------------------------------
# The public pipeline
# ---------------------------------------------------------------------------
# State and federally funded Hunter work. This does NOT appear in council DA
# feeds because it runs through state pathways, so it is compiled by hand each
# cycle from the NSW Budget papers and agency announcements. Every figure here
# is sourced; the source is printed in the report.

PUBLIC_PIPELINE = [
    {
        "name": "Hunter-Central Coast Renewable Energy Zone network infrastructure",
        "where": "Upper Hunter to Central Coast, incl. Newcastle, Lake Macquarie, Port Stephens",
        "value": "up to $3.9bn private investment",
        "value_num": 3_900_000_000,
        "stage": "Construction from early 2026",
        "detail": "Ausgrid selected to design, build, finance, operate and maintain. "
                  "Adds 1 GW of transfer capacity by 2028. Includes 85 km of sub-transmission "
                  "line Kurri Kurri to Muswellbrook and 18 km of underground fibre. "
                  "Forecast average 590 direct construction jobs a year.",
        "electrical": "HV transmission and sub-transmission, substations, protection and "
                      "control, comms and fibre, construction power. Tier-1 principal "
                      "contractors — target subcontract packages, not the head contract.",
        "source": "EnergyCo NSW",
        "source_url": "https://www.energyco.nsw.gov.au/news/major-energy-infrastructure-upgrade-approved-hunter",
    },
    {
        "name": "John Hunter Health and Innovation Precinct",
        "where": "New Lambton Heights, Newcastle",
        "value": "$890.0m",
        "value_num": 890_000_000,
        "stage": "Funded, delivery underway",
        "detail": "Largest single health capital allocation in the region.",
        "electrical": "Essential services, UPS and standby generation, AS/NZS 3003 body-"
                      "protected areas, nurse call, medical gas alarms, data density, "
                      "specialist lighting, security and access control.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Belmont Desalination Plant",
        "where": "Belmont, Lake Macquarie",
        "value": "$530.0m",
        "value_num": 530_000_000,
        "stage": "Design and construction funded",
        "detail": "Hunter Water's permanent desalination capacity.",
        "electrical": "HV supply and substation, MCCs and VSDs for high-pressure pumping, "
                      "SCADA and instrumentation, hazardous-area work, standby generation.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "M1 Pacific Motorway extension to Raymond Terrace",
        "where": "Black Hill to Raymond Terrace",
        "value": "$390.5m (2026-27 allocation)",
        "value_num": 390_500_000,
        "stage": "Under construction",
        "detail": "Includes new bridges over the Hunter River.",
        "electrical": "Road and high-mast lighting, ITS and variable message signage power, "
                      "communications pits and conduit, tunnel/underpass services.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Muswellbrook bypass",
        "where": "Muswellbrook (Upper Hunter — outside core coverage, watch item)",
        "value": "$258.2m (2026-27 allocation)",
        "value_num": 258_200_000,
        "stage": "Works underway",
        "detail": "Upper Hunter corridor upgrade programme.",
        "electrical": "Road lighting, intersection and signal power, comms infrastructure.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Cessnock Hospital redevelopment",
        "where": "Cessnock",
        "value": "$138.0m",
        "value_num": 138_000_000,
        "stage": "Redevelopment funded",
        "detail": "Full hospital redevelopment in the coverage area.",
        "electrical": "Essential and standby supply, body-protected wiring, nurse call, "
                      "theatre and imaging power, data, security.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Singleton bypass",
        "where": "Singleton (Upper Hunter — watch item)",
        "value": "$119.1m (2026-27 allocation)",
        "value_num": 119_100_000,
        "stage": "Construction",
        "detail": "New Hunter River crossing and bypass alignment.",
        "electrical": "Road lighting, signals, comms.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Nelson Bay Road upgrade",
        "where": "Williamtown to Bobs Farm, Port Stephens",
        "value": "$87.4m (2026-27 allocation)",
        "value_num": 87_400_000,
        "stage": "Construction",
        "detail": "Duplication through the Williamtown defence and aerospace corridor.",
        "electrical": "Road lighting, intersection power, service relocations, comms conduit.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Flood management asset repairs, Hunter",
        "where": "Across the Hunter valley",
        "value": "$73.1m",
        "value_num": 73_100_000,
        "stage": "Programme of works",
        "detail": "Critical repairs to damaged flood management assets — many small "
                  "discrete packages rather than one head contract.",
        "electrical": "Pump station power and controls, telemetry, switchboards, "
                      "standby generation. Well suited to mid-size local contractors.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Maitland Integrated Community and Community Mental Health Service",
        "where": "Maitland",
        "value": "$22.0m",
        "value_num": 22_000_000,
        "stage": "Funded",
        "detail": "Plus $7.5m for the Maitland Hospital car park.",
        "electrical": "Consulting-suite power and data, nurse call/duress, lighting "
                      "controls, car park lighting and EV provision.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Broadmeadow precinct and Newcastle Entertainment Centre planning",
        "where": "Broadmeadow, Newcastle",
        "value": "$14.0m (planning)",
        "value_num": 14_000_000,
        "stage": "Planning and business case",
        "detail": "Early planning money for a precinct expected to generate a very large "
                  "construction programme. Worth tracking now, not quoting.",
        "electrical": "Nothing to quote yet. The value of knowing early is relationship "
                      "building with the delivery agencies and shortlisted designers.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
    {
        "name": "Net Zero Manufacturing Centre of Excellence, TAFE NSW Tighes Hill",
        "where": "Tighes Hill, Newcastle",
        "value": "Funded (amount not itemised)",
        "value_num": 0,
        "stage": "Funded",
        "detail": "TAFE facility tied to the region's energy transition training pipeline.",
        "electrical": "Training-rig power, three-phase distribution, workshop lighting, "
                      "solar and battery training installations, data.",
        "source": "NSW Budget 2026-27, Hunter regional paper",
        "source_url": "https://www.nsw.gov.au/business-and-economy/nsw-budget/2026-27-budget-papers/regional-nsw/hunter",
    },
]

# Cross-checks that corroborate specific records in the council data.
CORROBORATIONS = {
    # keyed by a distinctive fragment of the address
    "Mcintosh Drive": {
        "note": "Independently corroborated: this is the Steel River East battery energy "
                "storage system, 400 MWh, developed by PLUS Grid Storage (an Ausgrid "
                "entity), planning approval March 2026, construction from mid-2026. The "
                "construction certificate names Southern Cross Electrical Engineering as "
                "builder, so the head electrical package is already let — target "
                "subcontract and labour-hire packages.",
        "source": "Hunter New Energy",
        "source_url": "https://hunternewenergy.com.au/steel-river-project-at-the-centre-of-nsw-battery-rollout-plans/",
    },
    "Hunter Street Newcastle West": {
        "note": "Newcastle West is the densest concentration of live high-value "
                "construction certificates in the region this cycle.",
        "source": "Tradiesignal analysis of NSW ePlanning data",
        "source_url": "",
    },
}


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def age_days(iso: str | None, today: date) -> int:
    if not iso:
        return 9999
    try:
        return (today - date.fromisoformat(iso)).days
    except ValueError:
        return 9999


def corroboration_for(address: str) -> dict | None:
    for fragment, payload in CORROBORATIONS.items():
        if fragment.lower() in (address or "").lower():
            return payload
    return None


def build() -> dict:
    projects = load("projects.json")
    summary = load("summary.json")
    today = date.today()

    live = [p for p in projects if p["stage_key"] != "withdrawn"]
    for p in live:
        p["age_days"] = age_days(p.get("date_last_updated"), today)
        p["corroboration"] = corroboration_for(p.get("address", ""))

    recent = [p for p in live if p["age_days"] <= WINDOW_DAYS]
    recent.sort(key=lambda p: (-p["opportunity_score"], -(p.get("cost") or 0)))

    def verified(p):
        return p.get("cost") and p["cost_confidence"] in ("high", "medium", "low")

    # --- Act this week: highest scores where there is a named builder to ring
    act_now = [
        p for p in recent
        if p["priority"] in ("high", "medium")
        and p["stage_key"] in ("cc_determined", "cc_lodged", "cdc_approved")
    ][:12]
    act_ids = {p["id"] for p in act_now}

    # --- High priority pipeline: everything else scoring high/medium
    pipeline = [p for p in recent if p["priority"] in ("high", "medium") and p["id"] not in act_ids][:14]
    pipe_ids = act_ids | {p["id"] for p in pipeline}

    # --- Big-ticket DAs: early-stage but very large, worth relationship work
    early_big = [
        p for p in recent
        if p["id"] not in pipe_ids
        and (p.get("cost") or 0) >= 3_000_000
        and p["stage_key"].startswith("da")
    ][:10]

    # --- Sector sections for the email and report
    sectors: dict[str, list] = defaultdict(list)
    for p in recent:
        if p["opportunity_score"] >= 55:
            sectors[p["filter_group"]].append(p)
    for group in sectors:
        sectors[group].sort(key=lambda p: (-p["opportunity_score"], -(p.get("cost") or 0)))
        sectors[group] = sectors[group][:8]

    # --- Chart series -----------------------------------------------------
    council_order = ["Newcastle", "Lake Macquarie", "Maitland", "Port Stephens", "Cessnock"]
    by_council = []
    for name in council_order:
        rows = [p for p in recent if p["council_short"] == name]
        by_council.append({
            "label": name,
            "count": len(rows),
            "value": round(sum(p["cost"] for p in rows if verified(p))),
            "high": sum(1 for p in rows if p["priority"] in ("high", "medium")),
        })

    stage_order = [
        ("da_lodged", "DA lodged"),
        ("da_assessment", "Under assessment"),
        ("da_exhibition", "On exhibition"),
        ("da_info", "Info requested"),
        ("da_determined", "DA approved"),
        ("cdc_lodged", "CDC lodged"),
        ("cdc_approved", "CDC approved"),
        ("cc_lodged", "CC lodged"),
        ("cc_determined", "CC issued"),
    ]
    by_stage = []
    for key, label in stage_order:
        rows = [p for p in recent if p["stage_key"] == key]
        by_stage.append({
            "label": label,
            "count": len(rows),
            "value": round(sum(p["cost"] for p in rows if verified(p))),
        })

    group_order = ["Residential", "Commercial", "Industrial", "Government", "Infrastructure"]
    by_group = []
    for name in group_order:
        rows = [p for p in recent if p["filter_group"] == name]
        elec_lo = sum(p["electrical_estimate"][0] for p in rows if p.get("electrical_estimate"))
        elec_hi = sum(p["electrical_estimate"][1] for p in rows if p.get("electrical_estimate"))
        by_group.append({
            "label": name,
            "count": len(rows),
            "value": round(sum(p["cost"] for p in rows if verified(p))),
            "electrical_low": round(elec_lo),
            "electrical_high": round(elec_hi),
        })

    # --- Builder watchlist: the target account list ------------------------
    builders: dict[str, dict] = defaultdict(
        lambda: {"jobs": 0, "value": 0.0, "councils": set(), "top": None, "recent": 0}
    )
    for p in live:
        if not p.get("builder"):
            continue
        b = builders[p["builder"]]
        b["jobs"] += 1
        b["councils"].add(p["council_short"])
        if p["age_days"] <= WINDOW_DAYS:
            b["recent"] += 1
        if verified(p):
            b["value"] += p["cost"]
            if not b["top"] or p["cost"] > b["top"]["cost"]:
                b["top"] = {"name": p["project_name"], "cost": p["cost"], "suburb": p.get("suburb")}
    watchlist = sorted(
        (
            {
                "builder": name,
                "jobs": v["jobs"],
                "recent": v["recent"],
                "value": round(v["value"]),
                "councils": sorted(v["councils"]),
                "top": v["top"],
            }
            for name, v in builders.items()
            if v["jobs"] >= 1
        ),
        key=lambda x: (-x["value"], -x["jobs"]),
    )[:15]

    # --- Suburb concentration --------------------------------------------
    suburbs: dict[str, dict] = defaultdict(lambda: {"count": 0, "value": 0.0, "council": ""})
    for p in recent:
        if not p.get("suburb"):
            continue
        s = suburbs[p["suburb"]]
        s["count"] += 1
        s["council"] = p["council_short"]
        if verified(p):
            s["value"] += p["cost"]
    hot_suburbs = sorted(
        ({"suburb": k, **v, "value": round(v["value"])} for k, v in suburbs.items()),
        key=lambda x: -x["value"],
    )[:12]

    totals = {
        "window_days": WINDOW_DAYS,
        "window_from": (today - timedelta(days=WINDOW_DAYS)).isoformat(),
        "window_to": today.isoformat(),
        "tracked_total": len(live),
        "recent_count": len(recent),
        "recent_high": sum(1 for p in recent if p["priority"] == "high"),
        "recent_medium": sum(1 for p in recent if p["priority"] == "medium"),
        "recent_value": round(sum(p["cost"] for p in recent if verified(p))),
        "recent_elec_low": round(sum(p["electrical_estimate"][0] for p in recent if p.get("electrical_estimate"))),
        "recent_elec_high": round(sum(p["electrical_estimate"][1] for p in recent if p.get("electrical_estimate"))),
        "builders_named": sum(1 for p in recent if p.get("builder")),
        "public_pipeline_value": sum(x["value_num"] for x in PUBLIC_PIPELINE),
    }

    payload = {
        "generated": today.isoformat(),
        "issue": 1,
        "totals": totals,
        "summary": summary,
        "act_now": act_now,
        "pipeline": pipeline,
        "early_big": early_big,
        "sectors": {k: v for k, v in sectors.items()},
        "by_council": by_council,
        "by_stage": by_stage,
        "by_group": by_group,
        "watchlist": watchlist,
        "hot_suburbs": hot_suburbs,
        "public_pipeline": PUBLIC_PIPELINE,
        "quality": summary["quality"],
    }
    (DATA / "report_payload.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = build()
    t = p["totals"]
    print(f"window            : last {t['window_days']} days ({t['window_from']} -> {t['window_to']})")
    print(f"tracked total     : {t['tracked_total']:,}")
    print(f"new this fortnight: {t['recent_count']:,}")
    print(f"high / medium     : {t['recent_high']} / {t['recent_medium']}")
    print(f"verified value    : ${t['recent_value']:,}")
    print(f"electrical band   : ${t['recent_elec_low']:,} - ${t['recent_elec_high']:,}")
    print(f"builders named    : {t['builders_named']}")
    print(f"act now cards     : {len(p['act_now'])}")
    print(f"pipeline cards    : {len(p['pipeline'])}")
    print(f"early big cards   : {len(p['early_big'])}")
    print(f"watchlist         : {len(p['watchlist'])}")
    print(f"sectors           : { {k: len(v) for k, v in p['sectors'].items()} }")
