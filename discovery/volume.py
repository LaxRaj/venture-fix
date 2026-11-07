"""Typical purchase volume for per-unit and per-project offers, so they can be put on a monthly footing.

Creator work is usually sold per video, per clip or per project, which the flat monthly test cannot score.  The model
is asked how many units one typical small buyer would buy in a month.  That figure is a GUESS (like hours per
account) and is labelled that way everywhere: a derived monthly price never ranks beside a cited, monthly one.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .extract_json import first_object
from .ground import key
from .screen import screen

VERSION = 1
MAX_UNITS = 500.0

PROMPT = (
    "A business sells '{offer}' to {buyer}, priced per {unit}. The work: {task}\n"
    "How many {unit}s would ONE typical small buyer purchase in a single month? "
    'Reply with one JSON object only: {{"units_per_month": number, "unit_name": "short noun", "basis": "one short sentence"}}. '
    "Give a conservative typical figure for a small buyer, not a maximum. You have no tools: do not try to browse."
)


def validate(found: Optional[dict]) -> Optional[dict]:
    if not found:
        return None
    try:
        units = float(str(found.get("units_per_month")).replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not (0 < units <= MAX_UNITS):
        return None
    return {"units_per_account_month": units, "unit_name": str(found.get("unit_name") or "").strip()[:30],
            "volume_basis": str(found.get("basis") or "").strip()[:160]}


def wanted(rows: List[dict]) -> List[dict]:
    return [r for r in rows if r.get("price_unit") in ("per_unit", "project") and r.get("price_usd")]


def volume_for(complete, r: dict) -> Optional[dict]:
    unit = "project" if r.get("price_unit") == "project" else "unit"
    prompt = PROMPT.format(offer=r["offer"], buyer=r["buyer"], unit=unit, task=(r.get("task") or "")[:160])
    return validate(first_object(complete(prompt)))


def fill(groq, rows: List[dict], cache_dir: str, max_tokens: Optional[int] = None, log=print) -> Dict[str, int]:
    """One cheap no-tool call per per-unit/project candidate.  Cached; a rerun resumes.  A limit stops the run cleanly."""
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "called": 0, "answered": 0, "failed": 0}
    for r in wanted(rows):
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path):
            stats["cached"] += 1
            continue
        if max_tokens is not None and getattr(groq, "tokens_used", 0) >= max_tokens:
            log(f"token budget {max_tokens:,} reached; stopping (rerun to continue)")
            break
        try:
            got = volume_for(groq.complete, r)
        except RuntimeError as exc:
            stats["failed"] += 1
            log(f"stopped on {r['offer'][:50]!r}: {exc}")
            break
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"offer": r["offer"], "found": got, "v": VERSION}, fh)
        stats["called"] += 1
        stats["answered"] += 1 if got else 0
    stats["tokens"] = getattr(groq, "tokens_used", 0)
    return stats


def apply_cached(rows: List[dict], cache_dir: str) -> List[dict]:
    """Attach cached volumes and re-screen the rows they change."""
    out = []
    for r in rows:
        path = os.path.join(cache_dir, key(r) + ".json")
        if r.get("price_unit") in ("per_unit", "project") and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                found = json.load(fh).get("found")
            if found:
                r = dict(r, **found)
                r.pop("verify", None)
                r["screen"] = screen(r)
        out.append(r)
    return out
