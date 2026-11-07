"""Stage 2: replace a candidate's guessed price/pool with cited figures.

Two engines:
  search   (default) one search-API query + a no-tool model reading the snippets for the price,
           and Census County Business Patterns for the pool.  ~1-2k Groq tokens per candidate.
  browser  the model drives Groq's browser_search tool itself.  17-62k tokens per candidate.

A grounded figure needs a cited http(s) URL; otherwise the guess stays and the candidate remains
ungrounded (verify.py then grades it C).  Hours per account always stay a guess: no page states them.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional

from .extract import VERSION as EXTRACT_VERSION, extract_price, query_for
from .harvest import UNITS, _num, _url
from .screen import screen
from .search import SearchBudget

ORDER = {"SURVIVES": 0, "FAILS_HR": 1, "FAILS_CAP": 1, "FAILS_POOL": 1, "UNIT": 2, "CONTINGENCY": 2, "INSUFFICIENT": 3}


def key(c: dict) -> str:
    return hashlib.sha256((c["offer"].lower() + "|" + c["buyer"].lower()).encode()).hexdigest()[:16]


def pick(rows: List[dict], n: int, scope: str = "survivors") -> List[dict]:
    """Candidates to ground.  survivors: top-n screen survivors.  all: everything, survivors and near-misses first."""
    todo = [r for r in rows if not r.get("grounded")]
    if scope == "survivors":
        todo = [r for r in todo if r["screen"].get("verdict") == "SURVIVES"]
        todo.sort(key=lambda r: (r["screen"]["weeks_base"], -r["screen"]["per_hr"]))
    else:
        todo.sort(key=lambda r: (ORDER.get(r["screen"].get("verdict"), 3), r["screen"].get("weeks_base") or 1e9))
    return todo[:n]


def apply(c: dict, found: Optional[dict]) -> dict:
    """Return a copy of c with any properly cited figures swapped in."""
    out = dict(c)
    out["guess"] = c.get("guess") or {k: c.get(k) for k in ("price_usd", "price_unit", "price_url", "pool_count", "pool_url")}
    swapped = list(c.get("grounded_fields") or [])
    if found:
        p, purl = _num(found.get("price_usd")), _url(found.get("price_url"))
        if p is not None and purl:
            out["price_usd"], out["price_url"] = p, purl
            unit = found.get("price_unit")
            out["price_unit"] = unit if unit in UNITS else out.get("price_unit")
            for extra in ("price_quoted", "evidence_quote", "price_basis"):
                if found.get(extra) is not None:
                    out[extra] = found[extra]
            if "price" not in swapped:
                swapped.append("price")
        n, nurl = _num(found.get("pool_count")), _url(found.get("pool_url"))
        if n is not None and nurl:
            out["pool_count"], out["pool_url"] = n, nurl
            out["pool_basis"] = found.get("pool_basis") or "page"
            if found.get("pool_note"):
                out["pool_note"] = found["pool_note"]
            if "pool" not in swapped:
                swapped.append("pool")
        if found.get("grounded_via"):
            out["grounded_via"] = found["grounded_via"]
        if found.get("price_rejected"):
            out["price_rejected"] = found["price_rejected"]
        if found.get("price_kind"):
            out["price_kind"] = found["price_kind"]
    out["grounded"] = bool(swapped)
    out["grounded_fields"] = swapped
    return out


def _write(path: str, offer: str, found: Optional[dict], v: int = 1) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"offer": offer, "found": found, "v": v}, fh)


def _stale(path: str) -> bool:
    """A cached search-engine grounding is stale if it carries a price made under an older extraction prompt.
    Entries that found no price stay valid: a stricter prompt cannot find a price they missed."""
    with open(path, "r", encoding="utf-8") as fh:
        entry = json.load(fh)
    return entry.get("v", 1) < EXTRACT_VERSION and bool((entry.get("found") or {}).get("price_url"))


def ground_all(groq, rows: List[dict], cache_dir: str, n: int, max_tokens: Optional[int] = None,
               scope: str = "survivors", log=print) -> Dict[str, int]:
    """Browser engine.  Cached per candidate; rerun resumes."""
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "called": 0, "failed": 0}
    for r in pick(rows, n, scope):
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
        _write(path, r["offer"], found)
        stats["called"] += 1
    stats["tokens"] = getattr(groq, "tokens_used", 0)
    return stats


def ground_all_search(groq, search, census, rows: List[dict], cache_dir: str, n: int,
                      max_tokens: Optional[int] = None, scope: str = "all", log=print) -> Dict[str, int]:
    """Search engine.  One query + one snippet read per candidate; Census supplies the pool by sector.

    Stops cleanly on the search cap, a Groq limit or the token budget; rerun resumes from cache.
    """
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "called": 0, "priced": 0, "rejected": 0, "pooled": 0, "failed": 0, "redone": 0}
    for r in pick(rows, n, scope):
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path):
            if not _stale(path):
                stats["cached"] += 1
                continue
            stats["redone"] += 1
        if max_tokens is not None and getattr(groq, "tokens_used", 0) >= max_tokens:
            log(f"token budget {max_tokens:,} reached; stopping (rerun to continue)")
            break
        found: Dict[str, object] = {"grounded_via": getattr(search, "name", "search")}
        try:
            results = search.search(query_for(r["offer"], r["buyer"]))
            price = extract_price(groq.complete, r["offer"], r["buyer"], results)
        except SearchBudget as exc:
            log(str(exc))
            break
        except RuntimeError as exc:
            stats["failed"] += 1
            log(f"stopped on {r['offer'][:50]!r}: {exc}")
            break
        if price and "rejected" in price:
            found["price_rejected"] = price["rejected"]
            stats["rejected"] += 1
        elif price:
            found.update(price)
            stats["priced"] += 1
        pool = census.sector_pool(r.get("sector", "")) if census else None
        if pool:
            found.update(pool)
            stats["pooled"] += 1
        _write(path, r["offer"], found, v=EXTRACT_VERSION)
        stats["called"] += 1
    stats["tokens"] = getattr(groq, "tokens_used", 0)
    stats["searches_paid"] = getattr(search, "fresh", 0)
    stats["searches_cached"] = getattr(search, "hits", 0)
    return stats


def ground_pools(census, rows: List[dict], cache_dir: str, log=print) -> Dict[str, int]:
    """Census pools only: no search credits, no Groq tokens.  Cached apart from price grounding so it never blocks it."""
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "pooled": 0, "no_naics": 0, "failed": 0}
    for r in rows:
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path):
            stats["cached"] += 1
            continue
        try:
            pool = census.sector_pool(r.get("sector", ""))
        except RuntimeError as exc:
            stats["failed"] += 1
            log(f"stopped: {exc}")
            break
        if not pool:
            stats["no_naics"] += 1
            continue
        _write(path, r["offer"], dict(pool, grounded_via="census"))
        stats["pooled"] += 1
    return stats


def merge_cached(rows: List[dict], *cache_dirs: str) -> List[dict]:
    """Apply every cached grounding result (later dirs win) and re-screen the changed rows."""
    out = []
    for r in rows:
        g, changed = r, False
        for d in cache_dirs:
            path = os.path.join(d, key(r) + ".json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    g = apply(g, json.load(fh)["found"])
                changed = True
        if changed:
            g = dict(g)
            g.pop("verify", None)
            g["screen"] = screen(g)
        out.append(g)
    return out
