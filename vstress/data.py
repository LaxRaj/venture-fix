"""Evidence fixtures and the fourteen economics rows.

The economics rows are deliberately small.  Every numeric input carries its
provenance so an anchored price can never be printed as if it were invented,
and an invented price can never be printed as if it were anchored.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple

# ---------------------------------------------------------------------------
# Arithmetic constants.  These are declared, not learned.
# ---------------------------------------------------------------------------

TARGET_MRR = 10_000.0                 # monthly revenue bar for the screen
WEEKS_PER_MONTH = 4.33
USABLE_HOURS = 40.0 * WEEKS_PER_MONTH  # one person, 173.2 hours/month
DEFAULT_CONVERSION = 0.006             # contact -> customer, conservative blend
MARKET_LIMIT = 0.50                    # contact more than half the pool = burn
PHONE_MULTIPLIER = 12.0                # declared assumption, isolated on purpose
SAMPLE_CONSTANT = 0.68                 # field-test heuristic, see fieldtest.py

PRICE_ANCHORED = "anchored"
PRICE_ESTIMATE = "estimate"
HOURS_ESTIMATE = "estimate"
BUYERS_ESTIMATE = "estimate"
BUYERS_YOURS = "yours"


@dataclass(frozen=True)
class Economics:
    name: str
    price: float                       # monthly price per account
    service_hours: float               # hours per account per month
    buyers: int                        # addressable buyer pool
    price_provenance: str
    price_note: str = ""
    hours_provenance: str = HOURS_ESTIMATE
    hours_note: str = ""
    buyers_provenance: str = BUYERS_ESTIMATE
    buyers_note: str = ""
    conversion: float = DEFAULT_CONVERSION
    conversion_provenance: str = "published"
    conversion_note: str = "published meeting/opp/close ranges compounded; phone multiplier isolated"


ECONOMICS: Tuple[Economics, ...] = (
    Economics(
        "DOT compliance", 150.0, 3.0, 30_000,
        PRICE_ANCHORED, "incumbents $29-199/mo",
        buyers_note="carriers and compliance shops",
    ),
    Economics(
        "Prior-auth appeals", 1_200.0, 8.5, 8_000,
        PRICE_ANCHORED, "$25-50/denial; 13 hrs/wk/physician",
        buyers_note="physician practices and billing groups",
    ),
    Economics(
        "Veterinary claims", 600.0, 4.5, 9_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="independent clinics and groups",
    ),
    Economics(
        "Insurance subrogation", 3_500.0, 15.0, 2_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="regional carriers and TPAs",
    ),
    Economics(
        "Customs HTS classification", 750.0, 3.0, 5_200,
        PRICE_ANCHORED, "CrossCode GTM",
        buyers_provenance=BUYERS_YOURS,
        buyers_note="counted customs brokers",
        conversion=0.011,
        conversion_provenance="published",
        conversion_note="verified list 1.1% vs purchased 0.05%",
    ),
    Economics(
        "Freight audit", 800.0, 3.5, 6_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="shippers with recurring LTL spend",
    ),
    Economics(
        "Lien waiver filing", 250.0, 1.5, 20_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="subcontractors and suppliers",
    ),
    Economics(
        "RFP response drafting", 1_500.0, 6.0, 1_500,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="mid-market vendors with bid teams",
    ),
    Economics(
        "Grant compliance reporting", 900.0, 4.0, 12_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="nonprofits and public agencies",
    ),
    Economics(
        "Utility bill audit", 500.0, 2.5, 12_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="multi-site commercial properties",
    ),
    Economics(
        "Medical billing denials", 1_000.0, 5.0, 15_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="small practices and clinics",
    ),
    Economics(
        "Environmental permit monitoring", 2_000.0, 8.0, 500,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="industrial sites with permits",
    ),
    Economics(
        "Title searches", 250.0, 1.5, 20_000,
        PRICE_ANCHORED, "$150-400; flat-fee rivals $29-385",
        buyers_note="title agencies and small lenders",
    ),
    Economics(
        "Trademark watch", 300.0, 1.0, 25_000,
        PRICE_ESTIMATE, "judgment, no source",
        buyers_note="brand owners and small law firms",
    ),
)

ECONOMICS_BY_NAME: Dict[str, Economics] = {row.name: row for row in ECONOMICS}


# ---------------------------------------------------------------------------
# 43 synthetic labelled ventures (fixture).
#
# Replace this block with your own labels.  The evidence fields are the only
# fields the model is allowed to see; labels live outside the state.
#
# The fixture is generated from five latent dimensions, one per question
# family.  Each dimension has three levels, and each level sets the option
# key for the three questions in that family.  Evidence is rendered from the
# same levels, so the model sees varied, readable prose rather than a label.
# ---------------------------------------------------------------------------

STATE_FIELDS: Tuple[str, ...] = ("buyer", "pain", "supply", "workflow", "access")

_FIXTURE_SEED = 2026
_CAPACITY_FLOOR = 5      # 2 * supply + workflow + pain
_REACH_FLOOR = 2         # buyer + access
_MOAT_FLOOR = 0.15       # independent noise, not readable in the evidence


@dataclass(frozen=True)
class LabelledVenture:
    id: str
    name: str
    sector: str
    alive: bool
    kill_reason: str
    evidence: Mapping[str, str]


_NAMES: Tuple[Tuple[str, str], ...] = (
    ("Atlas Freight", "freight"),
    ("Beacon Title", "title"),
    ("Cobalt Health", "health"),
    ("Driftwood Logistics", "freight"),
    ("Elm Street Legal", "legal"),
    ("Foundry Grants", "nonprofit"),
    ("Granite Environmental", "environmental"),
    ("Harbor Claims", "insurance"),
    ("Ironclad Compliance", "compliance"),
    ("Juniper Vets", "veterinary"),
    ("Keystone Billing", "medical billing"),
    ("Lantern RFP", "procurement"),
    ("Meridian Subrogation", "insurance"),
    ("Northstar Permits", "environmental"),
    ("Orchard Trademarks", "legal"),
    ("Pinnacle Freight", "freight"),
    ("Quarry Safety", "compliance"),
    ("Redwood Lien", "construction"),
    ("Summit Utilities", "utilities"),
    ("Tidewater Customs", "customs"),
    ("Umbra Insurance", "insurance"),
    ("Verity Medical", "medical billing"),
    ("Westgate Leases", "property"),
    ("Xenon Energy", "energy"),
    ("Yardline Transport", "freight"),
    ("Zephyr Dental", "dental"),
    ("Alder Clinical", "health"),
    ("Birchwood Construction", "construction"),
    ("Cedar Legal", "legal"),
    ("Dovetail Freight", "freight"),
    ("Everest Title", "title"),
    ("Falcon Labs", "health"),
    ("Grove Pharmacy", "pharmacy"),
    ("Hearth Property", "property"),
    ("Indigo Staffing", "staffing"),
    ("Jasper Manufacturing", "manufacturing"),
    ("Kestrel Trucking", "freight"),
    ("Loom Textiles", "manufacturing"),
    ("Marlow Marine", "marine"),
    ("Nimbus Clinics", "health"),
    ("Olive Foods", "food"),
    ("Pebble Mining", "mining"),
    ("Quill Publishing", "publishing"),
)

# The sentence used to render each question's evidence at each level.  The
# wording matches the option labels so a single-hop reader can settle the
# question.  Each family holds three questions, each with three levels.
_FAMILY_PHRASES: Dict[str, Tuple[str, ...]] = {
    "buyer": (
        "A finance manager owns this problem.",
        "An operations manager owns this problem.",
        "The owner owns this problem.",
        "A list must be built from scratch.",
        "A purchased contact database provides the list.",
        "A government licence registry provides the list.",
        "Buyers cluster in a single metropolitan area.",
        "Buyers are spread across a single region.",
        "Buyers are spread nationally.",
    ),
    "pain": (
        "The problem is an isolated event.",
        "The problem is occasional.",
        "The problem is constant.",
        "An outside vendor handles this work.",
        "A shared administrator handles this work.",
        "A dedicated employee handles this work.",
        "The buyer's insurer catches a failure.",
        "The buyer's customer catches a failure.",
        "An internal reviewer catches a failure.",
    ),
    "supply": (
        "Buyers use a spreadsheet or manual process.",
        "Buyers use a point solution.",
        "Buyers use an outsourced firm.",
        "An incumbent subscription sits beside your offer.",
        "A task fee sits beside your offer.",
        "An outsourced retainer sits beside your offer.",
        "Switching requires only a small setup effort.",
        "Switching requires a training cycle.",
        "Switching requires an integration project.",
    ),
    "workflow": (
        "The work stays with the same person.",
        "The work moves to a different person.",
        "The work moves to an outside party.",
        "An industry platform holds the record.",
        "A spreadsheet holds the record.",
        "Paper files hold the record.",
        "A rejected pass is abandoned.",
        "A different reviewer reworks a rejected pass.",
        "An outside party reworks a rejected pass.",
    ),
    "access": (
        "A procurement team controls access to the buyer.",
        "A department head controls access to the buyer.",
        "An industry association controls access to the buyer.",
        "A trade event reaches these buyers.",
        "An in-person visit reaches these buyers.",
        "Phone reaches these buyers.",
        "A professional licence unlocks a buyer meeting.",
        "A peer reference unlocks a buyer meeting.",
        "A sample output unlocks a buyer meeting.",
    ),
}

_FAMILIES: Tuple[str, ...] = ("buyer", "pain", "supply", "workflow", "access")


def _evidence(levels: Mapping[str, int]) -> Dict[str, str]:
    """Render one readable paragraph per family from the latent levels."""
    evidence: Dict[str, str] = {}
    for family in _FAMILIES:
        phrases = [
            _FAMILY_PHRASES[family][3 * i + levels[family]]
            for i in range(3)
        ]
        evidence[family] = " ".join(phrases)
    return evidence


def _build_labelled() -> Tuple[LabelledVenture, ...]:
    assert len(_NAMES) == 43, len(_NAMES)
    rng = random.Random(_FIXTURE_SEED)
    rows: List[LabelledVenture] = []
    for i, (name, sector) in enumerate(_NAMES):
        levels = {family: rng.choice((0, 1, 2)) for family in _FAMILIES}
        moat = rng.random()

        capacity_ok = (
            2 * levels["supply"] + levels["workflow"] + levels["pain"]
            >= _CAPACITY_FLOOR
        )
        reach_ok = levels["buyer"] + levels["access"] >= _REACH_FLOOR
        alive = capacity_ok and reach_ok and moat > _MOAT_FLOOR

        if capacity_ok and reach_ok and not alive:
            reason = "moat too thin"
        elif not capacity_ok:
            reason = "capacity ceiling"
        elif not reach_ok:
            reason = "market reach"
        else:
            reason = ""

        rows.append(
            LabelledVenture(
                id=f"v{i + 1:02d}",
                name=name,
                sector=sector,
                alive=alive,
                kill_reason=reason,
                evidence=_evidence(levels),
            )
        )
    return tuple(rows)


LABELLED: Tuple[LabelledVenture, ...] = _build_labelled()


def build_state(venture: LabelledVenture) -> Dict[str, str]:
    """Return only the evidence a model may see.

    Leakage is blocked structurally rather than by prompt discipline.
    """
    state = {"id": venture.id, "name": venture.name, **dict(venture.evidence)}
    forbidden = {"alive", "kill_reason", "label", "verdict", "outcome"}
    overlap = forbidden.intersection(state)
    assert not overlap, f"label leakage in state: {sorted(overlap)}"
    assert set(STATE_FIELDS).issubset(state), "state is missing an evidence field"
    return state


def provenance_rows() -> List[Tuple[str, str, str, str]]:
    """(venture, price provenance, hours provenance, buyers provenance)."""
    return [
        (r.name, r.price_provenance, r.hours_provenance, r.buyers_provenance)
        for r in ECONOMICS
    ]


def provenance_counts() -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {
        "price": {},
        "service_hours": {},
        "buyers": {},
    }
    for row in ECONOMICS:
        for key, value in (
            ("price", row.price_provenance),
            ("service_hours", row.hours_provenance),
            ("buyers", row.buyers_provenance),
        ):
            out[key][value] = out[key].get(value, 0) + 1
    return out
