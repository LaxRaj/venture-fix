"""Harvest: one query -> validated candidates, cached by query id, resumable."""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

EVIDENCE_KEYS = ("buyer", "pain", "supply", "workflow", "access")
UNITS = ("month", "project", "per_unit", "contingency")
MIN_POOL = 100  # a buyer pool under this is a unit error, not a market


def _num(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(str(value).replace(",", "").replace("$", ""))
    except ValueError:
        return None
    return v if v > 0 else None


def _url(value) -> Optional[str]:
    return value if isinstance(value, str) and re.match(r"^https?://", value.strip()) else None


def validate(raw: dict, query: Dict[str, str]) -> Optional[dict]:
    """Return a normalized candidate, or None if offer/buyer are missing."""
    offer = str(raw.get("offer") or "").strip()
    buyer = str(raw.get("buyer") or "").strip()
    if not offer or not buyer:
        return None
    ev = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    unit = raw.get("price_unit")
    pool = _num(raw.get("pool_count"))
    if pool is not None and pool < MIN_POOL:
        pool = None  # implausible (usually thousands written as plain numbers); treat as unknown
    return {
        "offer": offer, "buyer": buyer, "task": str(raw.get("task") or "").strip(),
        "price_usd": _num(raw.get("price_usd")), "price_unit": unit if unit in UNITS else None,
        "price_url": _url(raw.get("price_url")),
        "hours_per_account_month": _num(raw.get("hours_per_account_month")),
        "pool_count": pool, "pool_url": _url(raw.get("pool_url")),
        "channel": str(raw.get("channel") or "").strip(), "blockers": str(raw.get("blockers") or "").strip(),
        "evidence": {k: str(ev.get(k) or "").strip() for k in EVIDENCE_KEYS},
        "source_query": query["id"], "sector": query["sector"], "pain": query["pain"], "model": query["model"],
    }


def harvest(groq, queries: List[Dict[str, str]], cache_dir: str, limit: Optional[int] = None,
            max_tokens: Optional[int] = None, log=print) -> Dict[str, int]:
    """Run uncached queries.  Stops cleanly on a hard failure or token budget; rerun resumes."""
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "called": 0, "candidates": 0, "failed": 0}
    for q in queries:
        path = os.path.join(cache_dir, f"{q['id']}.json")
        if os.path.exists(path):
            stats["cached"] += 1
            continue
        if limit is not None and stats["called"] >= limit:
            break
        if max_tokens is not None and getattr(groq, "tokens_used", 0) >= max_tokens:
            log(f"token budget {max_tokens:,} reached; stopping (rerun to continue)")
            break
        try:
            items = groq.ask(q["text"])
        except RuntimeError as exc:
            stats["failed"] += 1
            log(f"stopped at query {q['id']}: {exc}")
            break
        good = [c for c in (validate(i, q) for i in items) if c]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"query": q, "candidates": good, "raw_count": len(items)}, fh)
        stats["called"] += 1
        stats["candidates"] += len(good)
    stats["tokens"] = getattr(groq, "tokens_used", 0)
    return stats


def load_cached(cache_dir: str, queries: List[Dict[str, str]]) -> List[dict]:
    """All cached candidates in query order, tagged with their batch number."""
    out: List[dict] = []
    for idx, q in enumerate(queries):
        path = os.path.join(cache_dir, f"{q['id']}.json")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for c in json.load(fh)["candidates"]:
                c = dict(c)
                c["query_index"] = idx
                out.append(c)
    return out
