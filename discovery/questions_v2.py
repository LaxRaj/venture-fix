"""Question bank v2: five typed questions that each feed a decision.

The original 15 questions read 6-8 word evidence sentences that rarely contain the answer.  These read
the richer text we already hold (the cited price quote, the offer, the task, the blockers, the channel),
and every answer maps to something we act on: price kind and audience check the grounded price,
regulated work feeds compliance, delivery model shows retainer fit, channel groups outreach motions.

They pass the same admission rules as the original bank (single hop, no arithmetic, no dates,
enumerable with exactly one escape option).  vstress/ is not edited, so the source check uses this
module's own list of state fields.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from vstress.questions import (
    ALLOWED_MAPS, ESCAPE_KEY, Option, Question, _ARITHMETIC, _DATES, _INFERENCE, _NEGATION, _UNBOUNDED, _escape, _opt,
)

SOURCES: Tuple[str, ...] = ("quote", "regulated_text", "offer_text", "channel")
FAMILIES_V2: Tuple[str, ...] = ("price", "audience", "compliance", "model", "access")

QUESTIONS_V2: Tuple[Question, ...] = (
    Question(
        "price_kind", "price", "What kind of amount does the quote state?", "quote", "",
        (
            _opt("vendor", "A fee a business pays an outside vendor for this service", 1.0),
            _opt("internal", "What the buyer spends doing this work in-house", 0.0),
            _opt("ads", "An advertising or media budget", 0.0),
            _opt("savings", "A saving or benefit the buyer gains", 0.0),
            _escape(),
        ),
    ),
    Question(
        "audience", "audience", "Which kind of buyer does the quote describe?", "quote", "",
        (
            _opt("small", "A small local business or practice", 1.0),
            _opt("large", "A large company or enterprise", 0.0),
            _escape(),
        ),
    ),
    Question(
        "regulated_work", "compliance", "What rules govern this work?", "regulated_text", "",
        (
            _opt("licence", "A professional licence is required", 0.0),
            _opt("health", "Patient health records are handled", 0.0),
            _opt("finance", "Financial or tax filings are handled", 0.0),
            _opt("plain", "Ordinary business with only general rules", 1.0),
            _escape(),
        ),
    ),
    Question(
        "delivery_model", "model", "How is this offer delivered?", "offer_text", "",
        (
            _opt("service", "A person does the work for the buyer", 1.0),
            _opt("tool", "Software the buyer runs themselves", 0.5),
            _opt("advice", "Coaching or advice", 0.5),
            _opt("leads", "Sold leads or introductions", 0.5),
            _escape(),
        ),
    ),
    Question(
        "access_channel", "access", "Which channel suits reaching these buyers?", "channel", "",
        (
            _opt("direct", "Direct outreach by email or phone", 1.0),
            _opt("community", "An association or community group", 1.0),
            _opt("platform", "A marketplace or platform", 1.0),
            _opt("partner", "A partner who already serves them", 1.0),
            _escape(),
        ),
    ),
)


def admission_failures_v2(q: Question) -> List[str]:
    """Same T1-T4 as vstress/questions.py, with this module's source list for T4."""
    failures: List[str] = []
    labels = [o.label for o in q.substantive]
    if _NEGATION.search(q.text) or _INFERENCE.search(q.text) or any(_NEGATION.search(l) or _INFERENCE.search(l) for l in labels):
        failures.append("T1")
    if _ARITHMETIC.search(q.text) or any(_ARITHMETIC.search(l) for l in labels):
        failures.append("T2")
    if _DATES.search(q.text) or any(_DATES.search(l) for l in labels):
        failures.append("T3")
    keys = [o.key for o in q.options]
    t4 = (q.family in FAMILIES_V2 and q.source in SOURCES and q.maps_to in ALLOWED_MAPS
          and sum(1 for o in q.options if o.escape) == 1 and len(q.substantive) >= 2
          and len(keys) == len(set(keys)) and len({o.label for o in q.options}) == len(q.options)
          and all(o.key and " " not in o.key for o in q.options)
          and not any(_UNBOUNDED.search(o.label) for o in q.substantive))
    if not t4:
        failures.append("T4")
    return failures


def _admit() -> Tuple[Question, ...]:
    problems = []
    seen = set()
    for q in QUESTIONS_V2:
        if q.id in seen:
            problems.append(f"{q.id}: duplicate id")
        seen.add(q.id)
        f = admission_failures_v2(q)
        if f:
            problems.append(f"{q.id}: failed {', '.join(f)}")
    if problems:
        raise ImportError("question bank v2 failed admission:\n  " + "\n  ".join(problems))
    return QUESTIONS_V2


ADMITTED_V2: Tuple[Question, ...] = _admit()
BY_ID: Dict[str, Question] = {q.id: q for q in ADMITTED_V2}

# Groq's price_kind labels (discovery/extract.py) -> this bank's option keys, for the cross-check.
GROQ_PRICE_KIND = {"vendor_fee": "vendor", "buyer_internal_cost": "internal", "ad_spend": "ads", "buyer_savings": "savings"}


def build_state_v2(c: dict) -> Dict[str, str]:
    """State for one candidate.  Empty fields are left out so questions reading them are skipped."""
    parts = {
        "quote": (c.get("evidence_quote") or "").strip(),
        "regulated_text": " | ".join(x for x in ((c.get("task") or "").strip(), (c.get("blockers") or "").strip()) if x),
        "offer_text": " | ".join(x for x in ((c.get("offer") or "").strip(), (c.get("task") or "").strip()) if x),
        "channel": (c.get("channel") or "").strip(),
    }
    state = {k: v for k, v in parts.items() if v}
    state["id"] = c["id"]
    state["name"] = c["offer"]
    return state


def applicable(state: Dict[str, str]) -> List[Question]:
    return [q for q in ADMITTED_V2 if state.get(q.source)]
