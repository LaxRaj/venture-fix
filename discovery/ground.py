"""Stage 2: replace a survivor's guessed price/pool with search-grounded figures.

Only candidates that survive the screen on their *guesses* are grounded, because search is
the expensive step.  A grounded figure needs a cited http(s) URL; otherwise the guess stays and
the candidate remains ungrounded (verify.py then grades it C).  Hours per account always stay a
guess: no web page states them.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional

from .harvest import UNITS, _num, _url
from .screen import screen


def key(c: dict) -> str:
    return hashlib.sha256((c["offer"].lower() + "|" + c["buyer"].lower()).encode()).hexdigest()[:16]


def pick(rows: List[dict], n: int) -> List[dict]:
    """Top-n survivors on their guesses, fastest to $3k first."""
    surv = [r for r in rows if r["screen"].get("verdict") == "SURVIVES" and not r.get("grounded")]
    surv.sort(key=lambda r: (r["screen"]["weeks_base"], -r["screen"]["per_hr"]))
    return surv[:n]


def apply(c: dict, found: Optional[dict]) -> dict:
    """Return a copy of c with any properly cited figures swapped in."""
    out = dict(c)
    out["guess"] = {k: c.get(k) for k in ("price_usd", "price_unit", "price_url", "pool_count", "pool_url")}
    swapped = []
    if found:
        p, purl = _num(found.get("price_usd")), _url(found.get("price_url"))
        if p is not None and purl:
            out["price_usd"], out["price_url"] = p, purl
            unit = found.get("price_unit")
            out["price_unit"] = unit if unit in UNITS else out.get("price_unit")
            swapped.append("price")
        n, nurl = _num(found.get("pool_count")), _url(found.get("pool_url"))
        if n is not None and nurl:
            out["pool_count"], out["pool_url"] = n, nurl
            swapped.append("pool")
    out["grounded"] = bool(swapped)
    out["grounded_fields"] = swapped
    return out


def ground_all(groq, rows: List[dict], cache_dir: str, n: int, max_tokens: Optional[int] = None,
               log=print) -> Dict[str, int]:
    """Ground up to n survivors, cached per candidate; returns stats.  Rerun resumes."""
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "called": 0, "failed": 0}
    for r in pick(rows, n):
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path):
            stats["cached"] += 1
            continue
        if max_tokens is not None and getattr(groq, "tokens_used", 0) >= max_tokens:
            log(f"token budget {max_tokens:,} reached; stopping (rerun to continue)")
            break
        try:
            found = groq.ground(r["offer"], r["buyer"])
        except RuntimeError as exc:
            stats["failed"] += 1
            log(f"stopped on {r['offer'][:50]!r}: {exc}")
            break
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"offer": r["offer"], "found": found}, fh)
        stats["called"] += 1
    stats["tokens"] = getattr(groq, "tokens_used", 0)
    return stats


def merge_cached(rows: List[dict], cache_dir: str) -> List[dict]:
    """Apply every cached grounding result and re-screen the changed rows."""
    out = []
    for r in rows:
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                g = apply(r, json.load(fh)["found"])
            g.pop("verify", None)
            g["screen"] = screen(g)
            out.append(g)
        else:
            out.append(r)
    return out
