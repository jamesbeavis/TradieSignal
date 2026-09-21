#!/usr/bin/env python3
"""
Tradiesignal :: normalisation, deduplication, quality control and scoring
=========================================================================
Reads the raw NSW ePlanning snapshots, produces one clean scored project
record per real-world project, and writes:

    data/projects.json   full scored dataset
    data/projects.csv    same, flat, for spreadsheets
    data/summary.json    aggregate stats for the report and dashboard

Pipeline
--------
1. NORMALISE  every DA / CDC / CC record into one common schema.
2. LINK       records that describe the same physical project (address +
              lot/plan) into a single project with a stage history, so the
              customer sees one project, not three rows.
3. VALIDATE   flag implausible declared costs (the "extra three zeros"
              problem) instead of publishing them as fact.
4. CLASSIFY   assign category, filter group, electrical scope.
5. SCORE      opportunity score from category, stage, value, distance,
              and high-intent signals.
6. ESTIMATE   electrical opportunity range from the category's share band.

Usage:
    python3 src/normalise_and_score.py
    python3 src/normalise_and_score.py --origin -32.9283,151.7817
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import scoring_config as cfg

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data")


# ===========================================================================
# helpers
# ===========================================================================

def _f(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    v = _f(value)
    return int(v) if v is not None else None


def _date(value: Any) -> str | None:
    """Normalise the API's mixed date formats to ISO yyyy-mm-dd."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[: len(fmt) + 6] if "%f" in fmt else text[: len(fmt)], fmt).date().isoformat()
        except ValueError:
            continue
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else None


def _days_ago(iso: str | None, today: date) -> int | None:
    if not iso:
        return None
    try:
        return (today - date.fromisoformat(iso)).days
    except ValueError:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def title_case_address(addr: str) -> str:
    """The feed shouts addresses in caps. Make them readable."""
    if not addr:
        return "Address not supplied"
    small = {"of", "the", "and"}
    parts = []
    for word in addr.title().split():
        low = word.lower()
        if low in small and parts:
            parts.append(low)
        elif re.fullmatch(r"(?i)nsw|dp\d+|sp\d+", word):
            parts.append(word.upper())
        else:
            parts.append(word)
    out = " ".join(parts)
    return re.sub(r"\bNsw\b", "NSW", out)


# ===========================================================================
# 1. NORMALISE
# ===========================================================================

def development_types(record: dict) -> list[str]:
    return [
        d.get("DevelopmentType", "").strip()
        for d in (record.get("DevelopmentType") or [])
        if d.get("DevelopmentType")
    ]


def building_classes(record: dict) -> list[str]:
    return [
        b.get("BuildingCodeClass", "").strip()
        for b in (record.get("BuildingCodeClass") or [])
        if b.get("BuildingCodeClass")
    ]


def primary_location(record: dict) -> dict:
    locations = record.get("Location") or []
    return locations[0] if locations else {}


def stage_key(record: dict) -> str:
    """Map (service, status) onto our stage vocabulary."""
    service = record.get("_service")
    status = (record.get("ApplicationStatus") or "").strip().lower()

    if status in cfg.DEAD_STATUSES:
        return "withdrawn"

    if service == "OnlineCC":
        return "cc_determined" if status == "determined" else "cc_lodged"

    if service == "OnlineCDC":
        return "cdc_approved" if status == "approved" else "cdc_lodged"

    # OnlineDA
    if status == "determined":
        return "da_determined"
    if status == "additional information requested":
        return "da_info"
    if status == "on exhibition":
        return "da_exhibition"
    if status == "under assessment":
        # exhibition dates present and current => publicly exhibited
        if record.get("AssessmentExhibitionStartDate"):
            return "da_exhibition"
        return "da_assessment"
    return "da_lodged"


def normalise(record: dict, today: date) -> dict:
    loc = primary_location(record)
    lots = loc.get("Lot") or []
    lot_ref = ""
    if lots:
        first = lots[0]
        lot_ref = f"{first.get('Lot','')}/{first.get('PlanLabel','')}".strip("/")

    council = (record.get("Council") or {}).get("CouncilName") or record.get("_council_query") or ""
    dtypes = development_types(record)

    lodged = _date(record.get("LodgementDate"))
    determined = _date(record.get("DeterminationDate"))
    submitted = _date(record.get("SubmissionDate") or record.get("DateSubmitted"))

    builder = (record.get("BuilderTradingName") or record.get("BuilderLegalName") or "").strip()
    builder_is_real = bool(builder) and not any(
        token in builder.lower() for token in cfg.NON_BUILDER_TOKENS
    )

    return {
        "source_ref": record.get("PlanningPortalApplicationNumber") or "",
        "council_ref": record.get("CouncilApplicationNumber")
        or record.get("CertifierApplicationNumber")
        or "",
        "service": record.get("_service"),
        "council": council,
        "council_short": cfg.COUNCILS.get(council, {}).get("short", council),
        "status_raw": record.get("ApplicationStatus"),
        "application_type": record.get("ApplicationType"),
        "stage_key": stage_key(record),
        "development_types": dtypes,
        "building_classes": building_classes(record),
        "cost_declared": _f(record.get("CostOfDevelopment")),
        "dwellings_new": _i(record.get("NumberOfNewDwellings")) or _i(record.get("UnitsProposed")),
        "storeys": _i(record.get("NumberOfStoreys")) or _i(record.get("StoreysProposed")),
        "lots_proposed": _i(record.get("NumberOfProposedLots")) or _i(record.get("ProposedLots")),
        "gfa_proposed": _f(record.get("ProposedGrossFloorArea")),
        "gfa_existing": _f(record.get("ExistingGrossFloorArea")),
        "land_area": _f(record.get("LandArea")),
        "use_current": (record.get("CurrentBuildingUse") or "").strip() or None,
        "use_proposed": (record.get("ProposedBuildingUse") or "").strip() or None,
        "builder": builder if builder_is_real else None,
        "builder_field_raw": builder or None,
        "date_submitted": submitted,
        "date_lodged": lodged,
        "date_determined": determined,
        "date_last_updated": _date(record.get("DateLastUpdated")),
        "exhibition_start": _date(record.get("AssessmentExhibitionStartDate")),
        "exhibition_end": _date(record.get("AssessmentExhibitionEndDate")),
        "determination_authority": record.get("DeterminationAuthority"),
        "vpa": record.get("AccompaniedByVPAFlag") == "Y",
        "sic": record.get("DevelopmentSubjectToSICFlag") == "Y",
        "subdivision": record.get("SubdivisionProposedFlag") == "Y",
        "address": title_case_address(loc.get("FullAddress") or ""),
        "address_raw": (loc.get("FullAddress") or "").strip(),
        "suburb": title_case_address(loc.get("Suburb") or "") or None,
        "postcode": (loc.get("Postcode") or "").strip() or None,
        "lat": _f(loc.get("Y")),
        "lon": _f(loc.get("X")),
        "lot_ref": lot_ref or None,
        "days_since_activity": _days_ago(
            determined or lodged or submitted, today
        ),
    }


# ===========================================================================
# 2. LINK — collapse DA -> CDC -> CC for the same site into one project
# ===========================================================================

def link_key(row: dict) -> str:
    """
    Identity for a physical project. Address is the strongest available key;
    the feed gives no cross-service project id. Fall back to lot/plan, then
    to the record's own reference so nothing is silently merged.
    """
    addr = re.sub(r"[^A-Z0-9]+", "", (row["address_raw"] or "").upper())
    if addr and len(addr) > 8:
        return f"A:{addr}"
    if row["lot_ref"]:
        return f"L:{row['council']}:{row['lot_ref']}"
    return f"R:{row['source_ref']}"


STAGE_RANK = {
    "withdrawn": -1,
    "da_lodged": 0,
    "da_info": 1,
    "da_assessment": 2,
    "da_exhibition": 3,
    "da_determined": 4,
    "cdc_lodged": 5,
    "cdc_approved": 6,
    "cc_lodged": 7,
    "cc_determined": 8,
}


def merge_group(rows: list[dict]) -> dict:
    """
    Fold every record for one site into a single project, keeping the most
    advanced stage as the headline and everything else as stage history.
    """
    rows = sorted(rows, key=lambda r: (STAGE_RANK.get(r["stage_key"], 0), r["date_last_updated"] or ""))
    lead = dict(rows[-1])

    # Backfill any field the lead record is missing from its siblings.
    fill_fields = [
        "cost_declared", "dwellings_new", "storeys", "lots_proposed",
        "gfa_proposed", "gfa_existing", "land_area", "use_current",
        "use_proposed", "builder", "lat", "lon", "suburb", "postcode",
        "lot_ref", "vpa", "sic", "subdivision", "determination_authority",
    ]
    for field in fill_fields:
        if not lead.get(field):
            for other in reversed(rows[:-1]):
                if other.get(field):
                    lead[field] = other[field]
                    break

    # Union of development types and building classes across the whole history.
    all_types, all_classes = [], []
    for row in rows:
        for t in row["development_types"]:
            if t not in all_types:
                all_types.append(t)
        for c in row["building_classes"]:
            if c not in all_classes:
                all_classes.append(c)
    lead["development_types"] = all_types
    lead["building_classes"] = all_classes

    # Headline cost = the largest plausible declared cost seen for the site.
    costs = [r["cost_declared"] for r in rows if r["cost_declared"]]
    lead["cost_all_declared"] = sorted(costs, reverse=True)

    lead["stage_history"] = [
        {
            "service": r["service"],
            "stage_key": r["stage_key"],
            "stage_label": cfg.STAGE_DEFINITIONS[r["stage_key"]][0],
            "status": r["status_raw"],
            "ref": r["source_ref"],
            "council_ref": r["council_ref"],
            "date": r["date_determined"] or r["date_lodged"],
            "cost": r["cost_declared"],
        }
        for r in rows
    ]
    lead["record_count"] = len(rows)
    lead["source_refs"] = [r["source_ref"] for r in rows]
    lead["has_da"] = any(r["service"] == "OnlineDA" for r in rows)
    lead["has_cdc"] = any(r["service"] == "OnlineCDC" for r in rows)
    lead["has_cc"] = any(r["service"] == "OnlineCC" for r in rows)
    return lead


# ===========================================================================
# 3. VALIDATE — plausibility of the declared cost
# ===========================================================================

# Categories where floor area is a meaningless denominator: a battery farm or
# a substation is nearly all equipment and almost no building.
EQUIPMENT_HEAVY = {"energy", "infrastructure"}


def validate_cost(project: dict, category: str) -> tuple[float | None, str, list[str]]:
    """
    Returns (cost_used, confidence, flags).

    The declared cost is applicant-entered and unaudited, so the feed contains
    "extra three zeros" typos. We corroborate it against physical scale where
    a meaningful denominator exists. Cross-checks are deliberately narrow: a
    false "suspect" flag suppresses a real opportunity, which is just as
    damaging to the customer as publishing a fake $1.4bn duplex.
    """
    flags: list[str] = []
    declared = project.get("cost_declared")
    q = cfg.QUALITY_RULES

    if declared is None or declared <= 0:
        return None, "unknown", ["no_cost_declared"]

    if declared < q["minimum_useful_cost"]:
        return declared, "low", ["cost_below_useful_threshold"]

    checks_run = 0
    checks_passed = 0

    types_text = " ".join(project["development_types"]).lower()
    is_new_build = (
        "erection of a new structure" in types_text
        or (project.get("dwellings_new") or 0) > 0
    )
    # Only the NEW floor area is attributable to the declared cost. On an
    # alteration, gfa_proposed describes the whole building while the cost
    # covers a small fitout, which produced a wave of false outliers.
    gfa_new = (project.get("gfa_proposed") or 0) - (project.get("gfa_existing") or 0)

    if (
        category not in EQUIPMENT_HEAVY
        and is_new_build
        and gfa_new > 30
    ):
        checks_run += 1
        per_sqm = declared / gfa_new
        if q["cost_per_sqm_min"] <= per_sqm <= q["cost_per_sqm_max"]:
            checks_passed += 1
        else:
            flags.append(f"cost_per_sqm_outlier:{per_sqm:,.0f}")

    # Dwelling count is a valid denominator for ANY project that contains
    # dwellings, including commercial mixed use. Restricting this check to
    # purely residential categories left genuine 280-apartment towers sitting
    # in the "unverified" bucket, which is worse than the typo it prevents.
    dwellings = project.get("dwellings_new") or 0
    if dwellings:
        checks_run += 1
        per_dwelling = declared / dwellings
        lo, hi = q["cost_per_dwelling_min"], q["cost_per_dwelling_max"]
        if category not in ("residential_new", "residential_reno"):
            # Mixed use carries retail/commercial cost the dwellings don't.
            lo, hi = lo * 0.5, hi * 2.5
        if lo <= per_dwelling <= hi:
            checks_passed += 1
        else:
            flags.append(f"cost_per_dwelling_outlier:{per_dwelling:,.0f}")

    lots = project.get("lots_proposed") or 0
    if lots >= 2 and category == "subdivision":
        checks_run += 1
        per_lot = declared / lots
        if 5_000 <= per_lot <= 2_000_000:
            checks_passed += 1
        else:
            flags.append(f"cost_per_lot_outlier:{per_lot:,.0f}")

    # A very large figure with nothing at all to corroborate it is the classic
    # data-entry typo. Equipment-heavy categories are exempt: a $208m battery
    # legitimately has no floor area and no dwellings.
    if (
        checks_run == 0
        and declared > q["uncorroborated_cost_ceiling"]
        and category not in EQUIPMENT_HEAVY
    ):
        flags.append("large_cost_uncorroborated")
        return declared, "unverified", flags

    if checks_run and checks_passed == 0:
        return declared, "suspect", flags

    if checks_run and checks_passed < checks_run:
        return declared, "medium", flags

    if checks_run:
        return declared, "high", flags

    # Nothing to check against, but the figure is within a sane range.
    return declared, "medium", flags


# ===========================================================================
# 4. CLASSIFY
# ===========================================================================

_NEEDLE_CACHE: dict[str, re.Pattern] = {}


def needle_pattern(needle: str) -> re.Pattern:
    """
    Word-boundary matcher. Raw substring matching is a trap here: "port"
    matches "structural support", "rail" matches "guardrail", "spa" matches
    "spaces". Needles in cfg.PREFIX_NEEDLES may match the start of a longer
    word (so "manufactur" still catches "manufacturing").
    """
    if needle not in _NEEDLE_CACHE:
        tail = "" if needle in cfg.PREFIX_NEEDLES else r"\b"
        _NEEDLE_CACHE[needle] = re.compile(r"\b" + re.escape(needle) + tail)
    return _NEEDLE_CACHE[needle]


def matches(haystack: str, needle: str) -> bool:
    return bool(needle_pattern(needle).search(haystack))


def _haystack(project: dict) -> str:
    return " | ".join(
        project["development_types"]
        + [project.get("use_proposed") or "", project.get("use_current") or ""]
    ).lower()


RESI_SCALE_MARKERS = (
    "residential flat building", "shop top housing", "multi-dwelling housing",
    "mixed use development", "build-to-rent", "co-living", "boarding house",
)


def classify(project: dict) -> str:
    haystack = _haystack(project)

    # Mixed-use first. A 280-dwelling tower with a shop at street level is a
    # commercial mixed-use project, not "retail" — and the rule order alone
    # would file it under whichever use happens to be listed earliest.
    dwellings = project.get("dwellings_new") or 0
    has_resi_scale = any(matches(haystack, m) for m in RESI_SCALE_MARKERS)
    has_nonresi = any(
        matches(haystack, n)
        for n in ("shop", "retail premise", "office premise", "commercial development",
                  "food and drink premise", "restaurant or cafe", "business premises")
    )
    if has_resi_scale and (has_nonresi or dwellings >= 20):
        # Genuinely large single-use residential stays residential; anything
        # with a non-residential component becomes commercial mixed use.
        if has_nonresi:
            return "commercial"

    for category, needles in cfg.CATEGORY_RULES:
        if any(matches(haystack, needle) for needle in needles):
            return category
    return cfg.FALLBACK_CATEGORY


def infer_scope(project: dict, category: str) -> list[str]:
    scope = list(cfg.SCOPE_LIBRARY.get(category, cfg.SCOPE_LIBRARY["other"]))
    haystack = _haystack(project)
    for needle, item in cfg.SCOPE_TRIGGERS.items():
        if matches(haystack, needle) and item not in scope:
            scope.append(item)
    if (project.get("dwellings_new") or 0) >= 5 and "Common-area lighting and metering" not in scope:
        scope.append("Common-area lighting and house metering")
    if (project.get("storeys") or 0) >= 4:
        scope.append("Riser cabling and lift/plant power")
    return scope


# ===========================================================================
# 5. SCORE
# ===========================================================================

def value_band(cost: float | None) -> tuple[float, str]:
    if not cost:
        return 0.45, "Value not stated"
    for upper, mult, label in cfg.VALUE_BANDS:
        if cost < upper:
            return mult, label
    return 1.28, "Over $100m"


def distance_multiplier(km: float | None) -> float:
    if km is None:
        return 0.9
    for upper, mult in cfg.DISTANCE_BANDS:
        if km <= upper:
            return mult
    return 0.6


def score_project(project: dict, origin: tuple[float, float]) -> dict:
    category = classify(project)
    project["category"] = category
    project["category_label"] = cfg.CATEGORY_LABELS[category]
    project["filter_group"] = cfg.CATEGORY_FILTER_GROUP[category]

    cost_used, cost_confidence, quality_flags = validate_cost(project, category)
    project["cost"] = cost_used
    project["cost_confidence"] = cost_confidence
    project["quality_flags"] = quality_flags

    # --- base -------------------------------------------------------------
    base = cfg.BASE_SCORES[category]
    haystack = _haystack(project)
    for needle, boost in cfg.DEVELOPMENT_TYPE_BOOSTS.items():
        if matches(haystack, needle):
            base = max(base, boost)

    # --- stage ------------------------------------------------------------
    stage = project["stage_key"]
    stage_label, stage_mult, stage_weeks = cfg.STAGE_DEFINITIONS[stage]
    project["stage_label"] = stage_label
    project["weeks_to_trade_engagement"] = stage_weeks

    # --- value ------------------------------------------------------------
    # A suspect cost must not be allowed to inflate the score.
    scoring_cost = cost_used if cost_confidence not in ("suspect", "unverified") else None
    value_mult, value_label = value_band(scoring_cost)
    project["value_band"] = value_label

    # --- distance ---------------------------------------------------------
    km = None
    if project.get("lat") and project.get("lon"):
        km = haversine_km(origin[0], origin[1], project["lat"], project["lon"])
    project["distance_km"] = round(km, 1) if km is not None else None
    dist_mult = distance_multiplier(km)

    # --- signals ----------------------------------------------------------
    signals: list[str] = []
    bonus = 0
    b = cfg.SIGNAL_BONUSES

    if project.get("builder"):
        bonus += b["builder_named"]
        signals.append("Builder named in the certificate")
    dwellings = project.get("dwellings_new") or 0
    if dwellings >= 20:
        bonus += b["large_dwelling_count"]
        signals.append(f"{dwellings} dwellings")
    elif dwellings >= 5:
        bonus += b["multi_dwelling"]
        signals.append(f"{dwellings} dwellings")
    if (project.get("gfa_proposed") or 0) >= 2000:
        bonus += b["large_gfa"]
        signals.append(f"{project['gfa_proposed']:,.0f} m2 proposed floor area")
    if any(c in cfg.COMMERCIAL_BCA_CLASSES for c in project["building_classes"]):
        bonus += b["commercial_class"]
        signals.append("Commercial/industrial BCA class")
    if (project.get("lots_proposed") or 0) >= 10:
        bonus += b["subdivision_lots"]
        signals.append(f"{project['lots_proposed']} lots")
    if re.search(r"solar|battery|electric vehicle|ev charg", haystack):
        bonus += b["ev_or_solar_hint"]
        signals.append("Solar / battery / EV scope indicated")
    if project.get("vpa"):
        bonus += b["vpa"]
        signals.append("Voluntary planning agreement")
    auth = (project.get("determination_authority") or "").lower()
    if "panel" in auth or "committee" in auth:
        bonus += b["state_significant"]
        signals.append(f"Determined by {project['determination_authority']}")

    project["signals"] = signals

    # --- combine ----------------------------------------------------------
    raw = (base * stage_mult * value_mult * dist_mult) + bonus
    if stage == "withdrawn":
        raw = 0
    score = int(max(0, min(100, round(raw))))
    project["opportunity_score"] = score

    project["score_breakdown"] = {
        "category_base": base,
        "stage_multiplier": stage_mult,
        "value_multiplier": value_mult,
        "distance_multiplier": dist_mult,
        "signal_bonus": bonus,
        "formula": "(base x stage x value x distance) + signal bonus, capped 0-100",
    }

    # --- priority tier ----------------------------------------------------
    for threshold, key, label in cfg.PRIORITY_TIERS:
        if score >= threshold:
            project["priority"] = key
            project["priority_label"] = label
            break

    # --- electrical opportunity ------------------------------------------
    low_pct, high_pct = cfg.ELECTRICAL_SHARE[category]
    project["electrical_share_pct"] = [round(low_pct * 100, 1), round(high_pct * 100, 1)]
    if cost_used and cost_confidence not in ("suspect", "unverified"):
        project["electrical_estimate"] = [round(cost_used * low_pct), round(cost_used * high_pct)]
    else:
        project["electrical_estimate"] = None

    project["scope"] = infer_scope(project, category)

    play = cfg.CONTACT_PLAYS[stage]
    project["contact_window"] = play["window"]
    project["contact_target"] = (
        f"{project['builder']} — site manager or contracts administrator"
        if project.get("builder") and stage.startswith("cc")
        else play["target"]
    )
    project["contact_angle"] = play["angle"]

    project["project_name"] = build_name(project)
    project["id"] = f"TS-{_slug(project['council_short'])[:4].upper()}-{project['source_ref'].replace('PAN-','').replace('CDC-','').replace('CFT-','')}"
    project["slug"] = _slug(f"{project['suburb'] or project['council_short']}-{project['project_name']}")[:80]
    return project


NAME_PRIORITY = [
    "Electricity generating facility", "Hospital", "Medical centre",
    "School", "Educational establishment", "Centre-based child care",
    "Shopping centre", "Warehouse or distribution centre",
    "High technology industry", "General industry", "Light industry",
    "Industrial development", "Mixed use development", "Shop top housing",
    "Residential flat building", "Multi-dwelling housing", "Seniors housing",
    "Independent living units", "Tourist and visitor accommodation",
    "Hotel or motel accommodation", "Office Premise", "Commercial development",
    "Retail Premise", "Restaurant or cafe", "Service station", "Shop",
    "Subdivision", "Dual occupancy", "Secondary dwelling", "Dwelling house",
    "Alterations or additions to an existing building or structure",
]


def build_name(project: dict) -> str:
    """The feed has no project name. Construct a useful one."""
    types = project["development_types"]
    chosen = None
    for candidate in NAME_PRIORITY:
        for t in types:
            if candidate.lower() in t.lower():
                chosen = t
                break
        if chosen:
            break
    if not chosen:
        chosen = types[0] if types else "Development"

    chosen = chosen[0].upper() + chosen[1:]
    dwellings = project.get("dwellings_new") or 0
    lots = project.get("lots_proposed") or 0

    # A tower with shops underneath was classified commercial; name it that way
    # too, so the heading and the sector chip agree with each other.
    if (
        project.get("category") == "commercial"
        and dwellings >= 5
        and any(k in chosen.lower() for k in ("residential flat", "shop top", "multi-dwelling"))
    ):
        chosen = "Mixed use development"

    if lots >= 2 and "subdivision" in chosen.lower():
        chosen = f"{lots}-lot subdivision"
    elif dwellings >= 2:
        chosen = f"{chosen} ({dwellings} dwellings)"

    suburb = project.get("suburb") or ""
    if not suburb or suburb.lower().startswith("address not"):
        suburb = f"{project.get('council_short') or ''} LGA".strip()
    return f"{chosen}, {suburb}".strip().strip(",")


# ===========================================================================
# main
# ===========================================================================

def load_raw() -> list[dict]:
    records: list[dict] = []
    for path in sorted(RAW_DIR.glob("Online*_*.json")):
        records.extend(json.loads(path.read_text(encoding="utf-8")))
    if not records:
        raise SystemExit(f"No raw records found in {RAW_DIR}. Run collect_eplanning.py first.")
    return records


def summarise(projects: list[dict]) -> dict:
    live = [p for p in projects if p["stage_key"] != "withdrawn"]
    scored_cost = [p for p in live if p.get("cost") and p["cost_confidence"] in ("high", "medium", "low")]
    by_priority: dict[str, int] = defaultdict(int)
    by_category: dict[str, int] = defaultdict(int)
    by_council: dict[str, dict] = defaultdict(lambda: {"count": 0, "value": 0.0})
    by_group: dict[str, int] = defaultdict(int)
    elec_low = elec_high = 0.0

    for p in live:
        by_priority[p["priority"]] += 1
        by_category[p["category_label"]] += 1
        by_group[p["filter_group"]] += 1
        c = by_council[p["council_short"]]
        c["count"] += 1
        if p.get("cost") and p["cost_confidence"] in ("high", "medium", "low"):
            c["value"] += p["cost"]
        if p.get("electrical_estimate"):
            elec_low += p["electrical_estimate"][0]
            elec_high += p["electrical_estimate"][1]

    builders: dict[str, dict] = defaultdict(lambda: {"jobs": 0, "value": 0.0, "councils": set()})
    for p in live:
        if p.get("builder"):
            b = builders[p["builder"]]
            b["jobs"] += 1
            b["councils"].add(p["council_short"])
            if p.get("cost") and p["cost_confidence"] in ("high", "medium", "low"):
                b["value"] += p["cost"]

    top_builders = sorted(
        (
            {"builder": k, "jobs": v["jobs"], "value": round(v["value"]), "councils": sorted(v["councils"])}
            for k, v in builders.items()
        ),
        key=lambda x: (-x["value"], -x["jobs"]),
    )[:20]

    suburbs: dict[str, dict] = defaultdict(lambda: {"count": 0, "value": 0.0})
    for p in live:
        if p.get("suburb"):
            s = suburbs[p["suburb"]]
            s["count"] += 1
            if p.get("cost") and p["cost_confidence"] in ("high", "medium", "low"):
                s["value"] += p["cost"]
    top_suburbs = sorted(
        ({"suburb": k, "count": v["count"], "value": round(v["value"])} for k, v in suburbs.items()),
        key=lambda x: -x["value"],
    )[:15]

    return {
        "generated": date.today().isoformat(),
        "projects_total": len(projects),
        "projects_live": len(live),
        "withdrawn": len(projects) - len(live),
        "construction_value_verified": round(sum(p["cost"] for p in scored_cost)),
        "electrical_opportunity_low": round(elec_low),
        "electrical_opportunity_high": round(elec_high),
        "by_priority": dict(by_priority),
        "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
        "by_filter_group": dict(sorted(by_group.items(), key=lambda x: -x[1])),
        "by_council": {k: {"count": v["count"], "value": round(v["value"])} for k, v in by_council.items()},
        "top_builders": top_builders,
        "top_suburbs": top_suburbs,
        "quality": {
            "cost_confidence": {
                level: sum(1 for p in projects if p["cost_confidence"] == level)
                for level in ("high", "medium", "low", "suspect", "unverified", "unknown")
            },
            "suspect_records": [
                {
                    "id": p["id"], "address": p["address"], "declared": p["cost"],
                    "flags": p["quality_flags"],
                }
                for p in projects if p["cost_confidence"] in ("suspect", "unverified")
            ][:40],
        },
    }


CSV_FIELDS = [
    "id", "project_name", "address", "suburb", "postcode", "council_short",
    "category_label", "filter_group", "stage_label", "status_raw",
    "cost", "cost_confidence", "electrical_estimate_low", "electrical_estimate_high",
    "opportunity_score", "priority_label", "builder", "dwellings_new",
    "lots_proposed", "gfa_proposed", "storeys", "distance_km",
    "date_lodged", "date_determined", "contact_window", "contact_target",
    "source_ref", "council_ref", "lat", "lon",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default=None, help="lat,lon of the subscriber base")
    args = parser.parse_args()

    origin = cfg.DEFAULT_ORIGIN
    if args.origin:
        lat, lon = args.origin.split(",")
        origin = (float(lat), float(lon))

    today = date.today()
    raw = load_raw()
    print(f"loaded {len(raw)} raw records")

    normalised = [normalise(r, today) for r in raw]

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in normalised:
        groups[link_key(row)].append(row)
    print(f"linked into {len(groups)} distinct sites")

    projects = [score_project(merge_group(rows), origin) for rows in groups.values()]
    projects.sort(key=lambda p: (-p["opportunity_score"], -(p.get("cost") or 0)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "projects.json").write_text(json.dumps(projects, indent=1), encoding="utf-8")

    with (OUT_DIR / "projects.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for p in projects:
            row = dict(p)
            est = p.get("electrical_estimate") or [None, None]
            row["electrical_estimate_low"], row["electrical_estimate_high"] = est
            writer.writerow(row)

    summary = summarise(projects)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps({k: v for k, v in summary.items() if k not in ("top_builders", "top_suburbs", "quality")}, indent=2))
    print("\ntop builders:")
    for b in summary["top_builders"][:10]:
        print(f"  ${b['value']:>13,.0f}  {b['jobs']:>3} jobs  {b['builder']}")


if __name__ == "__main__":
    main()
