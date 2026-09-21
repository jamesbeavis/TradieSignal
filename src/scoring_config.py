#!/usr/bin/env python3
"""
Tradiesignal :: scoring configuration
=====================================
Every number an operator might want to tune lives here, not in the engine.
Edit this file, re-run the pipeline, and the whole product changes behaviour.

IMPORTANT — what is fact and what is assumption
-----------------------------------------------
FACT      : anything sourced from the NSW ePlanning API (address, cost of
            development, dates, status, builder name, building class, GFA).
ASSUMPTION: every number in this file. The electrical percentages are
            industry rules of thumb for order-of-magnitude sizing, NOT quotes.
            They must be presented to customers as estimates and re-calibrated
            against real won-job data as soon as any is available.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. Geography — council centroids and the region we serve
# ---------------------------------------------------------------------------

COUNCILS = {
    "Newcastle City Council": {
        "slug": "newcastle",
        "short": "Newcastle",
        "lat": -32.9283,
        "lon": 151.7817,
    },
    "Lake Macquarie City Council": {
        "slug": "lake-macquarie",
        "short": "Lake Macquarie",
        "lat": -32.9667,
        "lon": 151.6167,
    },
    "Maitland City Council": {
        "slug": "maitland",
        "short": "Maitland",
        "lat": -32.7333,
        "lon": 151.5500,
    },
    "Port Stephens Council": {
        "slug": "port-stephens",
        "short": "Port Stephens",
        "lat": -32.7500,
        "lon": 152.0667,
    },
    "Cessnock City Council": {
        "slug": "cessnock",
        "short": "Cessnock",
        "lat": -32.8333,
        "lon": 151.3500,
    },
}

# Default subscriber origin for radius filtering: Newcastle CBD.
DEFAULT_ORIGIN = (-32.9283, 151.7817)


# ---------------------------------------------------------------------------
# 2. Category classification
# ---------------------------------------------------------------------------
# Matched against the API's DevelopmentType array and building-use fields,
# in priority order. First match wins, so the most electrically significant
# categories are listed first.

# Needles are matched on WORD BOUNDARIES, not raw substrings.
# Without that, "port" matches "structural support" and half the
# residential pipeline is misfiled as infrastructure. Anything listed in
# PREFIX_NEEDLES below is allowed to match the start of a longer word.
PREFIX_NEEDLES = {
    "manufactur", "consult", "certif", "ev charg", "childcare",
    "telecommunication", "sewerage",
}

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    # (category, list of lowercase terms to match)
    ("energy", [
        "electricity generating", "electricity generating facility", "battery",
        "energy storage", "solar farm", "wind farm", "substation",
        "transmission", "electricity supply", "generating works",
    ]),
    ("healthcare", [
        "hospital", "health services facility", "medical centre", "medical",
        "health consulting", "day surgery", "residential care facility",
        "nursing home",
    ]),
    ("education", [
        "school", "educational establishment", "child care", "childcare",
        "centre-based child care", "tertiary institution", "university", "tafe",
    ]),
    ("infrastructure", [
        "road", "bridge", "water supply", "sewerage", "telecommunication",
        "waste management", "resource recovery", "port", "wharf", "rail",
        "public transport", "pipeline", "desalination",
    ]),
    ("industrial", [
        "general industry", "light industry", "heavy industry",
        "high technology industry", "industrial development", "warehouse",
        "distribution centre", "industrial training", "storage premises",
        "data centre", "freight transport facility", "manufactur",
    ]),
    ("retail", [
        "shop", "retail premise", "shopping centre", "supermarket",
        "food and drink premise", "restaurant or cafe", "take away food",
        "hotel or motel accommodation", "pub", "small bar", "service station",
        "garden centre", "hardware and building supplies", "market",
    ]),
    ("commercial", [
        "office premise", "commercial development", "business premises",
        "mixed use development", "shop top housing", "function centre",
        "recreation facility", "place of public worship", "community facility",
        "entertainment facility", "tourist and visitor accommodation",
        "seniors housing", "independent living units", "boarding house",
        "co-living", "build-to-rent",
    ]),
    ("residential_new", [
        "residential flat building", "multi-dwelling housing",
        "residential accommodation", "dual occupancy", "attached dwelling",
        "semi-detached dwelling", "manor house", "terrace",
        "dwelling house", "secondary dwelling", "rural worker's dwelling",
        "moveable dwelling", "group home",
    ]),
    ("subdivision", [
        "subdivision", "stratum / community title subdivision",
    ]),
    ("residential_reno", [
        "alterations or additions", "alterations and additions",
        "minor building alterations", "change of use",
    ]),
    ("low_value", [
        "swimming pool", "shed", "fence", "carport", "garage",
        "balcony, deck, patio", "driveway", "retaining wall", "earthworks",
        "advertising and signage", "signage", "demolition", "tree",
        "awning", "blind or canopy", "aerial", "antenna", "water tank",
        "portable swimming pool", "spa", "cabana", "pergola",
        "hours of operation", "temporary", "home business",
        "home occupation", "subdivision certificate",
    ]),
]

FALLBACK_CATEGORY = "other"

# Human-facing labels and the five dashboard filter buckets.
CATEGORY_LABELS = {
    "energy": "Energy",
    "healthcare": "Healthcare",
    "education": "Education",
    "infrastructure": "Infrastructure",
    "industrial": "Industrial",
    "retail": "Retail",
    "commercial": "Commercial",
    "residential_new": "New residential",
    "residential_reno": "Residential renovation",
    "subdivision": "Subdivision",
    "low_value": "Minor works",
    "other": "Other",
}

# Maps the 12 internal categories onto the 5 customer-facing filters.
CATEGORY_FILTER_GROUP = {
    "energy": "Infrastructure",
    "infrastructure": "Infrastructure",
    "healthcare": "Government",
    "education": "Government",
    "industrial": "Industrial",
    "retail": "Commercial",
    "commercial": "Commercial",
    "residential_new": "Residential",
    "residential_reno": "Residential",
    "subdivision": "Residential",
    "low_value": "Residential",
    "other": "Commercial",
}


# ---------------------------------------------------------------------------
# 3. Base opportunity scores by category (0-100)
# ---------------------------------------------------------------------------
# "How much does an electrician want to know about this kind of job?"

BASE_SCORES = {
    "energy": 100,
    "infrastructure": 92,
    "healthcare": 90,
    "education": 88,
    "industrial": 84,
    "retail": 82,
    "commercial": 80,
    "subdivision": 78,
    "residential_new": 70,
    "residential_reno": 48,
    "other": 40,
    "low_value": 12,
}

# Finer-grained overrides that fire when a specific development type is present,
# regardless of the category the record landed in. Highest match wins.
DEVELOPMENT_TYPE_BOOSTS = {
    "shopping centre": 95,
    "hospital": 95,
    "data centre": 98,
    "medical centre": 90,
    "health services facility": 92,
    "school": 88,
    "educational establishment": 88,
    "centre-based child care": 84,
    "seniors housing": 86,
    "residential care facility": 88,
    "service station": 84,
    "hotel or motel accommodation": 85,
    "warehouse or distribution centre": 86,
    "high technology industry": 92,
    "electricity generating facility": 100,
    "battery": 100,
    "residential flat building": 82,
    "shop top housing": 82,
    "mixed use development": 84,
    "build-to-rent": 86,
}


# ---------------------------------------------------------------------------
# 4. Electrical share of construction cost, by category
# ---------------------------------------------------------------------------
# ASSUMPTION. Bands are (low, high) as a fraction of declared cost of
# development. Used to size the electrical opportunity, presented as a range.
# Re-calibrate from real quotes as soon as customer data exists.

ELECTRICAL_SHARE = {
    "energy": (0.35, 0.60),        # BESS/generation is mostly electrical
    "infrastructure": (0.12, 0.22),
    "healthcare": (0.14, 0.22),
    "education": (0.11, 0.17),
    "industrial": (0.10, 0.18),
    "retail": (0.10, 0.16),
    "commercial": (0.09, 0.15),
    "subdivision": (0.04, 0.09),   # civil-heavy; street lighting + reticulation
    "residential_new": (0.06, 0.10),
    "residential_reno": (0.05, 0.11),
    "other": (0.06, 0.12),
    "low_value": (0.02, 0.08),
}


# ---------------------------------------------------------------------------
# 5. Stage / status weighting
# ---------------------------------------------------------------------------
# The stage tells you WHEN to call. A construction certificate means the
# builder is appointing trades now; a freshly lodged DA means 6-18 months out
# but you get first-mover advantage with the developer.

STAGE_DEFINITIONS = {
    # key: (label, multiplier, typical weeks until electrical trade engaged)
    "cc_determined":  ("Construction certificate issued", 1.00, 2),
    "cc_lodged":      ("Construction certificate lodged", 0.96, 6),
    "cdc_approved":   ("Complying development approved", 0.94, 4),
    "cdc_lodged":     ("Complying development lodged", 0.86, 10),
    "da_determined":  ("Development approved", 0.90, 20),
    "da_assessment":  ("DA under assessment", 0.74, 40),
    "da_info":        ("DA — info requested", 0.66, 48),
    "da_exhibition":  ("DA on public exhibition", 0.72, 44),
    "da_lodged":      ("DA lodged", 0.70, 44),
    "withdrawn":      ("Withdrawn / rejected", 0.00, 0),
}

DEAD_STATUSES = {"withdrawn", "rejected"}


# ---------------------------------------------------------------------------
# 6. Value weighting
# ---------------------------------------------------------------------------
# Log-scaled multiplier on declared cost of development, so a $50m job
# outranks a $500k job without a $500k job scoring zero.

VALUE_BANDS = [
    # (upper bound exclusive, multiplier, band label)
    (50_000,        0.35, "Under $50k"),
    (150_000,       0.55, "$50k - $150k"),
    (500_000,       0.75, "$150k - $500k"),
    (1_500_000,     0.90, "$500k - $1.5m"),
    (5_000_000,     1.00, "$1.5m - $5m"),
    (20_000_000,    1.10, "$5m - $20m"),
    (100_000_000,   1.20, "$20m - $100m"),
    (float("inf"),  1.28, "Over $100m"),
]


# ---------------------------------------------------------------------------
# 7. Distance decay
# ---------------------------------------------------------------------------
# Multiplier applied by straight-line km from the subscriber's base.

DISTANCE_BANDS = [
    (10,  1.00),
    (25,  0.97),
    (50,  0.90),
    (100, 0.78),
    (float("inf"), 0.60),
]


# ---------------------------------------------------------------------------
# 8. Signal bonuses — small additive nudges for high-intent markers
# ---------------------------------------------------------------------------

SIGNAL_BONUSES = {
    "builder_named": 6,        # CC names the builder — you have a direct target
    "multi_dwelling": 5,       # 5+ dwellings: repeatable, schedulable work
    "large_dwelling_count": 8, # 20+ dwellings
    "large_gfa": 4,            # 2,000m2+ proposed gross floor area
    "commercial_class": 4,     # BCA class 5/6/7/8/9 — commercial/industrial
    "subdivision_lots": 5,     # 10+ proposed lots
    "ev_or_solar_hint": 5,     # description mentions solar/EV/battery
    "vpa": 3,                  # voluntary planning agreement: big, well funded
    "state_significant": 8,    # regional panel or state determination
}

# BCA classes that indicate commercial/industrial electrical scope.
COMMERCIAL_BCA_CLASSES = {
    "Class 2", "Class 3", "Class 4", "Class 5", "Class 6",
    "Class 7", "Class 7a", "Class 7b", "Class 8", "Class 9",
    "Class 9a", "Class 9b", "Class 9c",
}


# ---------------------------------------------------------------------------
# 9. Priority tiers used in the dashboard and the weekly email
# ---------------------------------------------------------------------------

PRIORITY_TIERS = [
    (85, "high",   "High priority"),
    (70, "medium", "Medium priority"),
    (50, "watch",  "Watch list"),
    (0,  "low",    "Low priority"),
]


# ---------------------------------------------------------------------------
# 10. Data quality / plausibility validation
# ---------------------------------------------------------------------------
# The NSW feed is self-declared by applicants, so it contains typos of the
# "extra three zeros" kind. Catching these is a core part of the product's
# credibility — a report that tells an electrician about a $1.4bn duplex
# destroys trust instantly.

QUALITY_RULES = {
    # Cost per square metre of proposed GFA outside this range is suspect.
    "cost_per_sqm_min": 250,
    "cost_per_sqm_max": 35_000,
    # Cost per dwelling outside this range is suspect for residential work.
    "cost_per_dwelling_min": 60_000,
    "cost_per_dwelling_max": 4_000_000,
    # Absolute ceiling for a record with no corroborating scale field.
    "uncorroborated_cost_ceiling": 30_000_000,
    # Records at or below this cost carry no useful electrical signal.
    "minimum_useful_cost": 20_000,
}

# Words in a builder field that mean it is NOT actually a builder.
NON_BUILDER_TOKENS = [
    "certifier", "certification", "surveyor", "consult", "engineering services",
    "town planning", "planning pty", "architect",
]


# ---------------------------------------------------------------------------
# 11. Electrical scope inference
# ---------------------------------------------------------------------------
# Maps categories and signals to the specific services an electrician would
# quote. Drives the "Likely services required" block on the detail page.

SCOPE_LIBRARY = {
    "energy": [
        "HV/LV switchgear and protection", "Substation and transformer works",
        "Cable trays, containment and heavy cabling", "Earthing and lightning protection",
        "SCADA, control and comms", "Site power and temporary supply",
    ],
    "infrastructure": [
        "Street and public lighting", "Underground reticulation and pits",
        "Traffic and ITS power", "Pump and plant control", "Earthing systems",
    ],
    "healthcare": [
        "Essential services and life safety", "UPS and standby generation",
        "Medical body-protected wiring (AS/NZS 3003)", "Nurse call and duress",
        "Data cabling and Wi-Fi density", "Switchboards and metering",
        "Specialist lighting", "Access control and CCTV",
    ],
    "education": [
        "Classroom lighting and controls", "Data cabling and AV",
        "Switchboard upgrades", "Emergency and exit lighting",
        "Solar PV", "Security, CCTV and access control",
        "Air conditioning power",
    ],
    "industrial": [
        "Three-phase distribution and switchboards", "High-bay lighting",
        "Machine and plant power", "Solar PV and metering",
        "EV and forklift charging", "Data cabling and comms racks",
        "Fire and emergency systems",
    ],
    "retail": [
        "Tenancy fitout distribution", "Feature and display lighting",
        "Refrigeration and kitchen power", "POS and data cabling",
        "Signage power", "Emergency and exit lighting", "CCTV and alarms",
    ],
    "commercial": [
        "Main switchboard and distribution", "LED lighting and controls",
        "Data cabling and comms", "Base-build and tenancy metering",
        "EV charging infrastructure", "Access control, CCTV and intercom",
        "Mechanical services power", "Emergency and exit lighting",
    ],
    "subdivision": [
        "Underground reticulation", "Street lighting",
        "Pillar and pit installation", "Substation civil and connection",
        "NBN and comms conduit",
    ],
    "residential_new": [
        "Full rough-in and fit-off", "Switchboard and metering",
        "LED lighting and fans", "Data and TV cabling",
        "Solar PV and battery", "EV charger provision",
        "Smoke alarms", "Air conditioning power",
    ],
    "residential_reno": [
        "Rewire and circuit additions", "Switchboard upgrade and RCDs",
        "Kitchen and bathroom power", "Lighting replacement",
        "Smoke alarm compliance", "Air conditioning power",
    ],
    "other": [
        "General power and lighting", "Switchboard works", "Compliance testing",
    ],
    "low_value": [
        "Pool and spa bonding, RCD and isolation", "Outbuilding submain",
        "General power and lighting",
    ],
}

# Extra scope items triggered by explicit hints in the record.
SCOPE_TRIGGERS = {
    "solar": "Solar PV array and inverter",
    "battery": "Battery storage and hybrid inverter",
    "electric vehicle": "EV charging infrastructure",
    "ev charging": "EV charging infrastructure",
    "swimming pool": "Pool equipment bonding, RCD and isolation",
    "child care": "Child-safe outlets and compliance",
    "commercial kitchen": "Commercial kitchen and exhaust power",
    "restaurant or cafe": "Commercial kitchen and exhaust power",
    "cold": "Refrigeration power and controls",
    "car park": "Car park lighting and ventilation controls",
    "signage": "Illuminated signage supply and timers",
    "telecommunication": "Comms and antenna power",
}


# ---------------------------------------------------------------------------
# 12. Contact strategy timing
# ---------------------------------------------------------------------------

CONTACT_PLAYS = {
    "cc_determined": {
        "window": "Call this week",
        "target": "Site manager or contracts administrator at the named builder",
        "angle": "Construction certificate is issued. Trades are being locked in "
                 "now or have just been locked in. Ask who holds the electrical "
                 "package and whether they need a second crew for programme relief.",
    },
    "cc_lodged": {
        "window": "Call within 2 weeks",
        "target": "Estimator or contracts administrator at the named builder",
        "angle": "CC is lodged, so the builder is pricing and awarding packages. "
                 "This is the last clean window to get on the tender list.",
    },
    "cdc_approved": {
        "window": "Call within 2 weeks",
        "target": "Owner-builder, project home builder or certifier's client",
        "angle": "Complying development is approved and can start immediately. "
                 "CDC jobs move fast and often have no electrician appointed.",
    },
    "cdc_lodged": {
        "window": "Call within a month",
        "target": "Applicant or their builder",
        "angle": "CDC approval is usually weeks away. Introduce yourself before "
                 "the builder defaults to their usual sparky.",
    },
    "da_determined": {
        "window": "Call within 4-6 weeks",
        "target": "Developer or project manager named on the DA",
        "angle": "Consent is granted. The next step is a construction certificate, "
                 "which means the builder is being appointed. Get in front of the "
                 "developer before the builder is chosen and you inherit their sparky.",
    },
    "da_assessment": {
        "window": "Register interest now, follow up at approval",
        "target": "Developer, architect or planning consultant",
        "angle": "Too early to quote, perfect time to be remembered. A short "
                 "introduction now costs nothing and puts you on the list.",
    },
    "da_info": {
        "window": "Watch — follow up in 6-8 weeks",
        "target": "Developer or planning consultant",
        "angle": "Council has asked for more information, so timing is uncertain. "
                 "Keep it on the watch list rather than spending effort now.",
    },
    "da_exhibition": {
        "window": "Register interest now",
        "target": "Developer or architect",
        "angle": "Publicly exhibited, so the project is real and progressing. "
                 "Early contact is cheap and memorable.",
    },
    "da_lodged": {
        "window": "Register interest now",
        "target": "Developer or architect",
        "angle": "Earliest possible signal. One email now beats twenty calls later.",
    },
    "withdrawn": {
        "window": "No action",
        "target": "-",
        "angle": "Application withdrawn or rejected.",
    },
}
