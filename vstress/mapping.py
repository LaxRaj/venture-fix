"""Answers -> input bands, with floors and a confidence gate.

A model may move an input band.  It may not produce an arithmetic output.
Low-confidence answers, diagnostic-only answers and unknown answer keys are
queued for a human and change no input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .data import PHONE_MULTIPLIER, Economics
from .questions import QUESTIONS_BY_ID

CONFIDENCE_GATE = 0.55
BAND_WIDTH = 0.12

FLOORS: Mapping[str, float] = {
    "price": 29.0,
    "service_hours": 0.10,
    "buyers": 1.0,
    "conversion": 1e-5,
}
CEILINGS: Mapping[str, float] = {
    "price": 25_000.0,
    "service_hours": 200.0,
    "buyers": 1_000_000.0,
    "conversion": 0.10,
}

# One declared multiplier per answer key.  These are not predictions; they are
# bounded moves inside a band that arithmetic will test.
MULTIPLIERS: Mapping[str, Mapping[str, float]] = {
    "buyer_list_source": {
        "association": 1.30, "registry": 1.40, "purchased": 1.00, "scratch": 0.70,
    },
    "buyer_geography": {
        "metro": 0.90, "region": 1.00, "national": 1.15, "international": 1.05,
    },
    "pain_recurrence": {
        "constant": 1.15, "cyclical": 1.05, "occasional": 0.95, "isolated": 0.85,
    },
    "pain_handler": {
        "dedicated": 1.10, "shared": 1.00, "vendor": 0.85, "owner": 1.10,
    },
    "pain_error_caught": {
        "reviewer": 1.15, "customer": 1.10, "auditor": 1.00, "insurer": 0.90,
    },
    "supply_current": {
        "manual": 0.80, "point": 1.00, "outsourced": 1.30, "internal": 1.10,
    },
    "supply_alternative": {
        "subscription": 0.90, "task_fee": 1.00, "retainer": 1.25, "labour": 1.15,
    },
    "supply_switching": {
        "setup": 0.95, "training": 1.00, "migration": 1.10, "integration": 1.20,
    },
    "workflow_handoff": {
        "same": 0.80, "second": 1.00, "queue": 1.10, "outside": 1.25,
    },
    "workflow_system": {
        "spreadsheet": 1.20, "email": 1.25, "platform": 0.90, "paper": 1.30,
    },
    "workflow_rework": {
        "same": 1.00, "another": 1.15, "outside": 1.25, "abandoned": 0.80,
    },
    "access_gatekeeper": {
        "owner": 1.10, "department": 0.90, "procurement": 0.80, "association": 1.20,
    },
    "access_channel": {
        "email": 1.00, "phone": PHONE_MULTIPLIER, "visit": 4.00, "event": 2.00,
    },
}


@dataclass(frozen=True)
class Answer:
    key: str
    confidence: float
    raw: str = ""


@dataclass(frozen=True)
class Band:
    value: float
    low: float
    high: float
    provenance: str
    confidence: float


@dataclass
class MappingResult:
    bands: Dict[str, Band]
    applied: List[str] = field(default_factory=list)
    queued: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)

    def values(self) -> Dict[str, float]:
        return {key: band.value for key, band in self.bands.items()}


def _clamp(name: str, value: float) -> float:
    return max(FLOORS[name], min(CEILINGS[name], value))


def _band(name: str, value: float, provenance: str, confidence: float) -> Band:
    value = _clamp(name, value)
    low = _clamp(name, value * (1.0 - BAND_WIDTH))
    high = _clamp(name, value * (1.0 + BAND_WIDTH))
    return Band(value=value, low=low, high=high,
                provenance=provenance, confidence=confidence)


def base_bands(row: Economics) -> Dict[str, Band]:
    return {
        "price": _band("price", row.price, row.price_provenance, 1.0),
        "service_hours": _band("service_hours", row.service_hours, row.hours_provenance, 1.0),
        "buyers": _band("buyers", float(row.buyers), row.buyers_provenance, 1.0),
        "conversion": _band("conversion", row.conversion, row.conversion_provenance, 1.0),
    }


def apply_answers(row: Economics, answers: Mapping[str, Answer]) -> MappingResult:
    """Move input bands from high-confidence answers only."""
    bands = base_bands(row)
    applied: List[str] = []
    queued: List[str] = []
    diagnostics: List[str] = []

    per_input: Dict[str, List[Tuple[float, float, str]]] = {
        "price": [], "service_hours": [], "buyers": [], "conversion": [],
    }

    for qid, answer in answers.items():
        question = QUESTIONS_BY_ID.get(qid)
        if question is None:
            queued.append(qid)
            continue
        target = question.maps_to
        if target == "":
            diagnostics.append(qid)
            continue
        target = {"buyer_count": "buyers"}.get(target, target)
        if target not in per_input:
            queued.append(qid)
            continue
        if answer.confidence < CONFIDENCE_GATE:
            queued.append(qid)
            continue
        multipliers = MULTIPLIERS.get(qid, {})
        if answer.key not in multipliers:
            queued.append(qid)
            continue
        per_input[target].append(
            (multipliers[answer.key], answer.confidence, qid)
        )

    if per_input["price"]:
        base = row.price
        weighted = _weighted_multiplier(per_input["price"])
        bands["price"] = _band("price", base * weighted, "model band",
                               _mean_conf(per_input["price"]))
        applied.extend(q for _, _, q in per_input["price"])

    if per_input["service_hours"]:
        base = row.service_hours
        weighted = _weighted_multiplier(per_input["service_hours"])
        bands["service_hours"] = _band(
            "service_hours", base * weighted, "model band",
            _mean_conf(per_input["service_hours"]),
        )
        applied.extend(q for _, _, q in per_input["service_hours"])

    if per_input["buyers"]:
        base = float(row.buyers)
        weighted = _weighted_multiplier(per_input["buyers"])
        bands["buyers"] = _band("buyers", base * weighted, "model band",
                                _mean_conf(per_input["buyers"]))
        applied.extend(q for _, _, q in per_input["buyers"])

    if per_input["conversion"]:
        base = row.conversion
        weighted = _weighted_multiplier(per_input["conversion"])
        bands["conversion"] = _band(
            "conversion", base * weighted, "model band",
            _mean_conf(per_input["conversion"]),
        )
        applied.extend(q for _, _, q in per_input["conversion"])

    return MappingResult(bands=bands, applied=applied, queued=queued,
                         diagnostics=diagnostics)


def _weighted_multiplier(items: Iterable[Tuple[float, float, str]]) -> float:
    items = list(items)
    total = sum(conf for _, conf, _ in items)
    if total <= 0:
        return 1.0
    return sum(mult * conf for mult, conf, _ in items) / total


def _mean_conf(items: Iterable[Tuple[float, float, str]]) -> float:
    items = list(items)
    return sum(conf for _, conf, _ in items) / len(items) if items else 1.0


def gated_verdict(row: Economics, answers: Mapping[str, Answer]):
    """Move bands, recompute, then apply the hard floor.

    Returns ``(verdict, mapping_result)``.  A model-raised band can make a
    venture look worse; it can never revive one that fails division.
    """
    from .arithmetic import combine, model_verdict, verdict

    hard = verdict(row).hard
    result = apply_answers(row, answers)
    soft = model_verdict(row, result.values())
    return combine(hard, soft), result
