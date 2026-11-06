"""The typed question bank and its import-time admission tests.

A question is rejected while the module is imported, not by review.  The four
tests come from the published weakness list for jev-1.13:

    T1 single hop          no inference chain, no negation
    T2 no arithmetic       no counting, comparing or units
    T3 no dates            no before/after, durations or deadlines
    T4 enumerable          named options plus exactly one escape hatch
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from .data import STATE_FIELDS

FAMILIES: Tuple[str, ...] = ("buyer", "pain", "supply", "workflow", "access")
ALLOWED_MAPS: Tuple[str, ...] = ("", "price", "service_hours", "buyer_count", "conversion")

ESCAPE_KEY = "escape"
ESCAPE_LABEL = "Evidence does not settle this"


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    score: float
    escape: bool = False


@dataclass(frozen=True)
class Question:
    id: str
    family: str
    text: str
    source: str
    maps_to: str
    options: Tuple[Option, ...]

    @property
    def escape_option(self) -> Option:
        found = [o for o in self.options if o.escape]
        assert len(found) == 1, f"{self.id}: expected one escape option"
        return found[0]

    @property
    def substantive(self) -> Tuple[Option, ...]:
        return tuple(o for o in self.options if not o.escape)

    def score_for(self, key: str) -> float:
        for option in self.options:
            if option.key == key:
                return option.score
        raise KeyError(f"{self.id}: unknown answer key {key!r}")


def _opt(key: str, label: str, score: float) -> Option:
    return Option(key, label, score)


def _escape() -> Option:
    return Option(ESCAPE_KEY, ESCAPE_LABEL, 0.5, escape=True)


QUESTIONS: Tuple[Question, ...] = (
    # ---- buyer -----------------------------------------------------------
    Question(
        "buyer_role", "buyer",
        "Which role in the buying organization owns this problem?",
        "buyer", "",
        (
            _opt("owner", "Owner or founder", 0.8),
            _opt("ops", "Operations manager", 0.65),
            _opt("finance", "Finance manager", 0.5),
            _opt("compliance", "Compliance manager", 0.4),
            _escape(),
        ),
    ),
    Question(
        "buyer_list_source", "buyer",
        "Where does a ready list of these buyers already exist?",
        "buyer", "buyer_count",
        (
            _opt("association", "Trade association roster", 1.3),
            _opt("registry", "Government licence registry", 1.4),
            _opt("purchased", "Purchased contact database", 1.0),
            _opt("scratch", "A list must be built from scratch", 0.7),
            _escape(),
        ),
    ),
    Question(
        "buyer_geography", "buyer",
        "Which description fits the locations of these buyers?",
        "buyer", "",
        (
            _opt("metro", "A single metropolitan area", 0.55),
            _opt("region", "A single region", 0.7),
            _opt("national", "National spread", 0.8),
            _opt("international", "International spread", 0.6),
            _escape(),
        ),
    ),
    # ---- pain ------------------------------------------------------------
    Question(
        "pain_recurrence", "pain",
        "Which description fits the return of this problem for a buyer?",
        "pain", "service_hours",
        (
            _opt("constant", "Constant", 1.1),
            _opt("cyclical", "Cyclical", 1.0),
            _opt("occasional", "Occasional", 0.9),
            _opt("isolated", "Isolated event", 0.8),
            _escape(),
        ),
    ),
    Question(
        "pain_handler", "pain",
        "Who handles this work for the buyer?",
        "pain", "service_hours",
        (
            _opt("dedicated", "A dedicated employee", 1.15),
            _opt("shared", "A shared administrator", 1.0),
            _opt("vendor", "An outside vendor", 0.85),
            _opt("owner", "The owner personally", 1.1),
            _escape(),
        ),
    ),
    Question(
        "pain_error_caught", "pain",
        "Which party catches a failure in this work?",
        "pain", "service_hours",
        (
            _opt("reviewer", "An internal reviewer", 1.2),
            _opt("customer", "The buyer's customer", 1.1),
            _opt("auditor", "An auditor or regulator", 1.0),
            _opt("insurer", "The buyer's insurer", 0.9),
            _escape(),
        ),
    ),
    # ---- supply ----------------------------------------------------------
    Question(
        "supply_current", "supply",
        "What do buyers use for this work?",
        "supply", "price",
        (
            _opt("manual", "A spreadsheet or manual process", 0.8),
            _opt("point", "A point solution", 1.0),
            _opt("outsourced", "An outsourced firm", 1.3),
            _opt("internal", "An internal team", 1.1),
            _escape(),
        ),
    ),
    Question(
        "supply_alternative", "supply",
        "Which alternative sits beside your offer for a buyer?",
        "supply", "price",
        (
            _opt("subscription", "An incumbent subscription", 0.9),
            _opt("task_fee", "A task fee", 1.0),
            _opt("retainer", "An outsourced retainer", 1.25),
            _opt("labour", "Internal labour", 1.15),
            _escape(),
        ),
    ),
    Question(
        "supply_switching", "supply",
        "What must a buyer give up to switch?",
        "supply", "price",
        (
            _opt("setup", "A small setup effort", 0.95),
            _opt("training", "A training cycle", 1.0),
            _opt("migration", "A data migration", 1.1),
            _opt("integration", "An integration project", 1.2),
            _escape(),
        ),
    ),
    # ---- workflow --------------------------------------------------------
    Question(
        "workflow_handoff", "workflow",
        "Which description fits the handoff in this work?",
        "workflow", "service_hours",
        (
            _opt("same", "It stays with the same person", 0.8),
            _opt("second", "It moves to a different person", 1.0),
            _opt("queue", "It moves to a shared queue", 1.1),
            _opt("outside", "It moves to an outside party", 1.25),
            _escape(),
        ),
    ),
    Question(
        "workflow_system", "workflow",
        "Which system holds the record for this work?",
        "workflow", "service_hours",
        (
            _opt("spreadsheet", "A spreadsheet", 1.2),
            _opt("email", "Email threads", 1.25),
            _opt("platform", "An industry platform", 0.9),
            _opt("paper", "Paper files", 1.3),
            _escape(),
        ),
    ),
    Question(
        "workflow_rework", "workflow",
        "Which description fits a rejected pass?",
        "workflow", "service_hours",
        (
            _opt("same", "The same person reworks it", 1.0),
            _opt("another", "A different reviewer reworks it", 1.15),
            _opt("outside", "An outside party reworks it", 1.25),
            _opt("abandoned", "The case is abandoned", 0.8),
            _escape(),
        ),
    ),
    # ---- access ----------------------------------------------------------
    Question(
        "access_gatekeeper", "access",
        "Who controls access to the buyer?",
        "access", "buyer_count",
        (
            _opt("owner", "The owner directly", 1.1),
            _opt("department", "A department head", 0.9),
            _opt("procurement", "A procurement team", 0.8),
            _opt("association", "An industry association", 1.2),
            _escape(),
        ),
    ),
    Question(
        "access_channel", "access",
        "Which channel reaches these buyers?",
        "access", "conversion",
        (
            _opt("email", "Email", 1.0),
            _opt("phone", "Phone", 1.2),
            _opt("visit", "An in-person visit", 1.1),
            _opt("event", "A trade event", 0.95),
            _escape(),
        ),
    ),
    Question(
        "access_proof", "access",
        "Which proof unlocks a buyer meeting?",
        "access", "",
        (
            _opt("reference", "A peer reference", 0.9),
            _opt("sample", "A sample output", 1.15),
            _opt("security", "A security review", 0.85),
            _opt("licence", "A professional licence", 0.8),
            _escape(),
        ),
    ),
)

QUESTIONS_BY_ID: Dict[str, Question] = {q.id: q for q in QUESTIONS}


# ---------------------------------------------------------------------------
# Admission tests
# ---------------------------------------------------------------------------

_NEGATION = re.compile(
    r"\b(not|no|never|none|nobody|nothing|without|cannot|can't|isn't|aren't|"
    r"don't|doesn't|didn't|unable|fails?|failed|avoid|except)\b",
    re.IGNORECASE,
)
_INFERENCE = re.compile(
    r"\b(because|therefore|thus|hence|implies?|suggests?|indicates?|means|"
    r"likely|probably|if|then)\b",
    re.IGNORECASE,
)
_ARITHMETIC = re.compile(
    r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|many|much|"
    r"more|less|fewer|most|least|count|number|rate|percent|percentage|"
    r"average|total|sum|unit|units|per|each|half|double|twice)\b",
    re.IGNORECASE,
)
_DATES = re.compile(
    r"\b(day|days|week|weeks|month|months|year|years|hour|hours|minute|"
    r"minutes|before|after|during|deadline|quarter|date|duration|daily|"
    r"weekly|monthly|yearly|annual|annually|now|currently|recently|soon|"
    r"start|end|today|tomorrow|yesterday|last|next)\b",
    re.IGNORECASE,
)
_UNBOUNDED = re.compile(r"\b(etc|other|others|more|another|additional)\b|\.\.\.", re.IGNORECASE)


def admission_failures(q: Question) -> List[str]:
    """Return the admission tests this question fails (empty means admitted)."""
    failures: List[str] = []
    text = q.text
    labels = [o.label for o in q.substantive]

    if _NEGATION.search(text) or _INFERENCE.search(text) or any(
        _NEGATION.search(label) or _INFERENCE.search(label) for label in labels
    ):
        failures.append("T1")
    if _ARITHMETIC.search(text) or any(_ARITHMETIC.search(label) for label in labels):
        failures.append("T2")
    if _DATES.search(text) or any(_DATES.search(label) for label in labels):
        failures.append("T3")

    t4 = True
    if q.family not in FAMILIES:
        t4 = False
    if q.source not in STATE_FIELDS:
        t4 = False
    if q.maps_to not in ALLOWED_MAPS:
        t4 = False
    escapes = [o for o in q.options if o.escape]
    if len(escapes) != 1:
        t4 = False
    if len(q.substantive) < 2:
        t4 = False
    keys = [o.key for o in q.options]
    labels_all = [o.label for o in q.options]
    if len(keys) != len(set(keys)) or len(labels_all) != len(set(labels_all)):
        t4 = False
    if any(not o.key or " " in o.key for o in q.options):
        t4 = False
    if any(_UNBOUNDED.search(o.label) for o in q.substantive):
        t4 = False
    if not t4:
        failures.append("T4")
    return failures


def _admit_bank() -> Tuple[Question, ...]:
    seen: set[str] = set()
    admitted: List[Question] = []
    problems: List[str] = []
    for q in QUESTIONS:
        if q.id in seen:
            problems.append(f"{q.id}: duplicate question id")
        seen.add(q.id)
        failures = admission_failures(q)
        if failures:
            problems.append(f"{q.id}: failed {', '.join(failures)}")
        else:
            admitted.append(q)
    if problems:
        raise ImportError("question bank failed admission:\n  " + "\n  ".join(problems))
    if len(admitted) != 15:
        raise ImportError(f"question bank must contain 15 admitted questions, got {len(admitted)}")
    counts = {family: sum(1 for q in admitted if q.family == family) for family in FAMILIES}
    if any(count != 3 for count in counts.values()):
        raise ImportError(f"question families must have three questions each: {counts}")
    return tuple(admitted)


ADMITTED: Tuple[Question, ...] = _admit_bank()


# Six counterexamples, kept so the admission tests are themselves exercised.
# They are not part of the bank.
REJECTED_EXAMPLES: Tuple[Tuple[str, Question], ...] = (
    (
        "T1",
        Question(
            "bad_inference", "buyer",
            "Which role owns this problem, and therefore feels it first?",
            "buyer", "",
            (_opt("a", "Owner", 1.0), _opt("b", "Operator", 0.5), _escape()),
        ),
    ),
    (
        "T1",
        Question(
            "bad_negation", "buyer",
            "Which role does not own this problem?",
            "buyer", "",
            (_opt("a", "Owner", 1.0), _opt("b", "Operator", 0.5), _escape()),
        ),
    ),
    (
        "T2",
        Question(
            "bad_count", "buyer",
            "How many buyers are there?",
            "buyer", "",
            (_opt("a", "Owner", 1.0), _opt("b", "Operator", 0.5), _escape()),
        ),
    ),
    (
        "T2",
        Question(
            "bad_units", "supply",
            "What do buyers pay per seat?",
            "supply", "price",
            (_opt("a", "Owner", 1.0), _opt("b", "Operator", 0.5), _escape()),
        ),
    ),
    (
        "T3",
        Question(
            "bad_date", "pain",
            "Which buyer renewed before the audit?",
            "pain", "",
            (_opt("a", "Owner", 1.0), _opt("b", "Operator", 0.5), _escape()),
        ),
    ),
    (
        "T4",
        Question(
            "bad_options", "access",
            "Which channel reaches these buyers?",
            "access", "",
            (_opt("a", "Email", 1.0), _opt("b", "Other", 0.5), _opt("c", "Etc", 0.4)),
        ),
    ),
)


def _check_rejections() -> None:
    for expected, q in REJECTED_EXAMPLES:
        failures = admission_failures(q)
        if expected not in failures:
            raise ImportError(
                f"admission counterexample {q.id!r} did not fail {expected}: {failures}"
            )


_check_rejections()


def payload(q: Question, state: Mapping[str, str], rng) -> Dict[str, object]:
    """One question, one evidence field, options shuffled on every call."""
    options = list(q.options)
    rng.shuffle(options)
    return {
        "id": q.id,
        "question": q.text,
        "evidence": state[q.source],
        "options": [{"key": o.key, "label": o.label} for o in options],
    }


def bank_report() -> Dict[str, object]:
    counts = {family: sum(1 for q in ADMITTED if q.family == family) for family in FAMILIES}
    maps = {
        "price": sum(1 for q in ADMITTED if q.maps_to == "price"),
        "service_hours": sum(1 for q in ADMITTED if q.maps_to == "service_hours"),
        "buyer_count": sum(1 for q in ADMITTED if q.maps_to == "buyer_count"),
        "conversion": sum(1 for q in ADMITTED if q.maps_to == "conversion"),
        "diagnostic": sum(1 for q in ADMITTED if q.maps_to == ""),
    }
    return {
        "admitted": len(ADMITTED),
        "rejected_examples": len(REJECTED_EXAMPLES),
        "families": counts,
        "maps_to": maps,
    }
