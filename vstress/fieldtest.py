"""The only layer that creates new information: the field test.

It does not forecast.  It names the input nearest its flip, the number of calls
that input deserves, and six measurement questions.
"""

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import replace
from typing import Dict, Iterable, List, Mapping, Tuple

from .arithmetic import fmt_price, verdict
from .data import ECONOMICS, ECONOMICS_BY_NAME, SAMPLE_CONSTANT, Economics

MIN_CALLS = 8
MAX_CALLS = 200
INPUT_LABEL = {
    "service_hours": "service hours per account",
    "price": "monthly price",
    "buyers": "addressable buyer pool",
    "conversion": "contact-to-customer conversion",
}

CALL_SCRIPT: Mapping[str, Tuple[Tuple[str, str], ...]] = {
    "service_hours": (
        ("Who touches this work before it is finished?", "count the handoffs, not the tool"),
        ("Where does the record live while the work is open?", "spreadsheet, email, platform, paper"),
        ("What happens when a reviewer rejects a pass?", "who reworks it, and how far back"),
        ("Which step needs a specialist or a licensed sign-off?", "the step that sets the labour cost"),
        ("How much of the work is copied between systems?", "manual re-entry is the hidden hour"),
        ("If this ran perfectly, what would still take the same time?", "separate fixed from removable work"),
    ),
    "price": (
        ("What do you use for this today?", "the incumbent, not your product"),
        ("What do you pay for that today?", "monthly, annual or per task; write the unit down"),
        ("Which budget line pays for it?", "department, compliance, IT or owner"),
        ("What else competes for that budget line?", "the real alternative"),
        ("What would make switching worth the disruption?", "the threshold, in their words"),
        ("Who signs off on a change of this size?", "the path from interest to purchase"),
    ),
    "buyers": (
        ("How do you find peers with the same problem?", "association, registry, list, none"),
        ("Where is that list kept?", "roster, licence file, CRM, no list"),
        ("Who controls access to that list?", "owner, department head, procurement, association"),
        ("How many of those peers share the same workflow?", "the honest slice, not the whole market"),
        ("Who else would need to approve a change?", "the gatekeeper"),
        ("What proof would make an introduction easy?", "reference, sample, security review, licence"),
    ),
    "conversion": (
        ("Which channel gets a reply from these buyers?", "email, phone, visit, event"),
        ("Who answers that channel?", "the role, not the company"),
        ("What does the first reply usually ask for?", "the real objection"),
        ("Which proof unlocks a meeting?", "reference, sample, review, licence"),
        ("What makes a buyer take a second meeting?", "the trigger, not the pitch"),
        ("Who else joins the second meeting?", "the buying group"),
    ),
}


def sample_size(margin: float) -> int:
    """Declared heuristic: calls ~ constant / margin^2, floored and capped.

    This is not a power calculation.  It is a shopping-list heuristic that
    spends calls where the input is close to its flip and almost nothing where
    the margin is an order of magnitude.
    """
    if margin <= 0:
        return MAX_CALLS
    return max(MIN_CALLS, min(MAX_CALLS, math.ceil(SAMPLE_CONSTANT / (margin * margin))))


def nearest_input(row: Economics) -> Tuple[str, float, float, float]:
    """(input, current, flip, relative margin) for the nearest flip."""
    v = verdict(row)
    current = {
        "service_hours": row.service_hours,
        "price": row.price,
        "buyers": float(row.buyers),
        "conversion": row.conversion,
    }
    order = ("service_hours", "price", "buyers", "conversion")
    key = min(order, key=lambda k: v.margins[k])
    return key, current[key], v.flips[key], v.margins[key]


def shopping_list(rows: Iterable[Economics] = ECONOMICS) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for row in rows:
        key, current, flip, margin = nearest_input(row)
        out.append({
            "name": row.name,
            "verdict": verdict(row).hard,
            "input": key,
            "current": current,
            "flip": flip,
            "margin": margin,
            "calls": sample_size(margin),
        })
    return sorted(out, key=lambda item: (item["margin"], item["name"]))


def _fmt_value(name: str, value: float) -> str:
    if name == "price":
        return f"${value:,.0f}/mo"
    if name == "buyers":
        return f"{value:,.0f} buyers"
    if name == "conversion":
        return f"{value:.3%}"
    return f"{value:.2f} hrs/account/mo"


def field_report(name: str) -> str:
    row = _resolve(name)
    key, current, flip, margin = nearest_input(row)
    calls = sample_size(margin)
    v = verdict(row)
    lines: List[str] = []
    lines.append(f"FIELD TEST - {row.name}")
    lines.append(f"verdict: {v.hard}")
    lines.append(f"why: {v.cause}")
    lines.append("")
    lines.append(f"measure: {INPUT_LABEL[key]}")
    lines.append(f"  now:    {_fmt_value(key, current)}")
    lines.append(f"  flips:  {_fmt_value(key, flip)}")
    lines.append(f"  margin: {margin:.1%} away from the flip")
    lines.append(f"  calls:  {calls} (declared heuristic: {SAMPLE_CONSTANT}/margin^2, floor {MIN_CALLS})")
    lines.append(
        f"  provenance: price {row.price_provenance}, hours {row.hours_provenance}, "
        f"buyers {row.buyers_provenance}"
    )
    lines.append("")
    lines.append("six questions, none of them a pitch:")
    for i, (question, note) in enumerate(CALL_SCRIPT[key], 1):
        lines.append(f"  {i}. {question}")
        lines.append(f"     -> {note}")
    lines.append("")
    lines.append("Do not describe the product. Write down the answer, the unit, and who said it.")
    lines.append("Bring the values back with: python3 run.py ingest --file measurements.json")
    return "\n".join(lines)


def shopping_report() -> str:
    items = shopping_list()
    lines = ["SHOPPING LIST - rank the numbers worth a call", ""]
    lines.append(f"{'venture':32} {'verdict':20} {'measure':18} {'margin':>7} {'calls':>5}")
    lines.append("-" * 88)
    for item in items:
        lines.append(
            f"{str(item['name'])[:32]:32} {str(item['verdict'])[:20]:20} "
            f"{INPUT_LABEL[str(item['input'])][:18]:18} "
            f"{float(item['margin']):>6.1%} {int(item['calls']):>5}"
        )
    lines.append("")
    lines.append("Start at the top. The top row is the most fragile number in the system.")
    return "\n".join(lines)


def _resolve(name: str) -> Economics:
    if name in ECONOMICS_BY_NAME:
        return ECONOMICS_BY_NAME[name]
    needle = name.strip().lower()
    matches = [row for row in ECONOMICS if needle in row.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"no venture matched {name!r}")
    choices = ", ".join(row.name for row in matches)
    raise SystemExit(f"{name!r} is ambiguous: {choices}")


def _read_measurements(path: str) -> List[Dict[str, object]]:
    if not os.path.exists(path):
        raise SystemExit(f"measurement file not found: {path}")
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data = data.get("measurements", data.get("rows", []))
        if not isinstance(data, list):
            raise SystemExit("JSON measurements must be a list or have a measurements list")
        return [dict(item) for item in data]
    if path.lower().endswith(".csv"):
        with open(path, "r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    raise SystemExit("measurements must be .json or .csv")


def ingest(path: str) -> str:
    rows = _read_measurements(path)
    by_name = dict(ECONOMICS_BY_NAME)
    before = {row.name: verdict(row).hard for row in ECONOMICS}
    updated: Dict[str, Economics] = {}
    notes: List[str] = []

    field_map = {
        "service_hours": "service_hours",
        "hours": "service_hours",
        "price": "price",
        "buyers": "buyers",
        "buyer_count": "buyers",
        "pool": "buyers",
        "conversion": "conversion",
    }

    for item in rows:
        name = str(item.get("venture", item.get("name", ""))).strip()
        field = str(item.get("field", item.get("input", ""))).strip().lower()
        if not name or field not in field_map:
            notes.append(f"skipped row (need venture + field): {item}")
            continue
        try:
            row = _resolve(name)
        except SystemExit as exc:
            notes.append(str(exc))
            continue
        try:
            value = float(item.get("value", ""))
        except (TypeError, ValueError):
            notes.append(f"skipped row (bad value): {item}")
            continue
        target = field_map[field]
        if target == "buyers":
            value = int(round(value))
        if value <= 0:
            notes.append(f"skipped row (non-positive value): {item}")
            continue
        replacements = {target: value}
        if target == "price":
            replacements["price_provenance"] = "measured"
            replacements["price_note"] = f"ingested from {path}"
        elif target == "service_hours":
            replacements["hours_provenance"] = "measured"
            replacements["hours_note"] = f"ingested from {path}"
        elif target == "buyers":
            replacements["buyers_provenance"] = "measured"
            replacements["buyers_note"] = f"ingested from {path}"
        else:
            replacements["conversion_provenance"] = "measured"
            replacements["conversion_note"] = f"ingested from {path}"
        updated[row.name] = replace(updated.get(row.name, row), **replacements)

    lines = [f"INGEST - {path}", ""]
    if not updated:
        lines.append("No rows were applied.")
        for note in notes:
            lines.append(f"  {note}")
        return "\n".join(lines)

    lines.append(f"{'venture':32} {'before':20} {'after':20} moved")
    lines.append("-" * 82)
    for name, row in updated.items():
        after = verdict(row).hard
        moved = "YES" if after != before[name] else ""
        lines.append(f"{name[:32]:32} {before[name][:20]:20} {after[:20]:20} {moved}")
    lines.append("")
    lines.append("Measured values replace invented values; provenance now reads measured.")
    lines.append(
        "Calls settle price, hours and pain. They cannot test a close rate: "
        "20 calls at the 0.6% base predict 0.12 customers."
    )
    for note in notes:
        lines.append(f"  {note}")
    return "\n".join(lines)
