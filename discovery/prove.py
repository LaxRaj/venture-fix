"""Stage: proof that real vendors already charge for this service.

For each survivor, search for OTHER vendors selling the same service to the same kind of buyer and keep a
vendor only if its price quote is literally in a returned search result (the same rule as extract.validate).
A separate two-run check (option order shuffled) asks whether the candidate's own cited quote describes the
same service and buyer; if the runs disagree the answer is "unclear".  The model is never trusted on its word.
"""

from __future__ import annotations

import json
import os
import random
import statistics
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from . import dedupe as D
from .extract import _norm, validate as validate_price
from .groq_client import extract_json_object
from .ground import key
from .search import SearchBudget

VERSION = 2
MATCH = ("yes", "no", "unclear")
MAX_RESULTS = 12

VENDOR_PROMPT = (
    "VENDORS. You read web search results. Service: {offer}, sold to {buyer}.\n"
    "Results:\n{results}\n"
    "List every DIFFERENT vendor, agency or freelancer in these results that publicly states a price for this same "
    "service to this kind of buyer. Reply with one JSON object only: "
    '{{"vendors": [{{"vendor": "name", "source_index": integer, "quote": "text copied exactly from that result containing the price", '
    '"price_usd": number, "price_unit": "month" | "year" | "project" | "per_unit" | "contingency", '
    '"price_kind": "vendor_fee" | "buyer_internal_cost" | "ad_spend" | "buyer_savings" | "other", '
    '"audience": "small_business" | "enterprise" | "unclear", "same_service": true or false}}]}}. '
    "Rules: use only the results above; copy each quote exactly; one entry per vendor; skip results with no price; "
    "same_service is true only if the vendor sells this service to this kind of buyer, not a neighbouring service. "
    "Do not estimate. You have no tools: do not try to open or browse anything."
)

MATCH_PROMPT = (
    "MATCH CHECK. Service: {offer}. Buyer: {buyer}.\n"
    "Evidence quote: \"{quote}\"\nSource: {url}\n"
    "Does this evidence describe a price for the same service sold to the same kind of buyer? "
    "Options, in this order: {options}. "
    'Reply with one JSON object only: {{"answer": "yes" | "no" | "unclear"}}. '
    "Answer unclear when the text does not say."
)


def host(url: str) -> str:
    h = (urlparse(url or "").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def queries_for(r: dict) -> List[str]:
    from .extract import query_for
    return [query_for(r["offer"], r["buyer"]), f"{r['offer']} for {r['buyer']} agency rates"]


GENERIC = {"service", "services", "pack", "package", "standard", "assistant", "support", "tool", "kit", "review", "per", "monthly"}


def names_the_service(offer: str, *texts: str) -> bool:
    """Deterministic same-service floor the model cannot talk its way past: at least half of the offer's distinctive
    words (5-letter prefix match, generic words ignored) must appear in the text.  An offer with none passes."""
    words = {t[:5] for t in D.tokens(offer) if t not in GENERIC}
    if not words:
        return True
    hay = _norm(" ".join(texts))
    return sum(1 for w in words if w in hay) * 2 >= len(words)


def parse_vendors(found: Optional[dict], results: List[Dict[str, str]], offer: str = "") -> List[dict]:
    """Keep a vendor only if validate_price accepts its quote, the model says it is the same service, and the
    result's own title or snippet names the service.  One vendor per host: two pages of one company are not
    independent proof."""
    out, seen = [], set()
    for v in (found or {}).get("vendors") or []:
        if not isinstance(v, dict) or v.get("same_service") is not True:
            continue
        ok = validate_price(v, results)
        if not ok or "rejected" in ok:
            continue
        hit = results[int(v["source_index"])]
        if not names_the_service(offer, hit["title"], hit["snippet"]):
            continue
        h = host(ok["price_url"])
        if not h or h in seen:
            continue
        seen.add(h)
        out.append({"vendor": str(v.get("vendor") or h)[:80], "host": h, "url": ok["price_url"], "quote": ok["evidence_quote"],
                    "price": ok["price_usd"], "unit": ok["price_unit"], "basis": ok["price_basis"]})
    return out


def judge_match(complete: Callable[[str], str], r: dict, runs: int = 2, seed: int = 7) -> str:
    """yes / no / unclear.  Two runs with shuffled option order; any disagreement is 'unclear'."""
    quote = r.get("evidence_quote")
    if not quote or not r.get("price_url") or not names_the_service(r["offer"], quote, r["price_url"]):
        return "unclear"
    answers = []
    for i in range(runs):
        opts = list(MATCH)
        random.Random(seed + i * 17).shuffle(opts)
        prompt = MATCH_PROMPT.format(offer=r["offer"], buyer=r["buyer"], quote=quote, url=r["price_url"], options=", ".join(opts))
        got = extract_json_object(complete(prompt)) or {}
        a = got.get("answer")
        answers.append(a if a in MATCH else "unclear")
    return answers[0] if len(set(answers)) == 1 else "unclear"


def summarize(r: dict, vendors: List[dict], match: str) -> dict:
    """Price range uses the proven vendors in the row's own price unit plus the row's own cited price.  Only the
    vendors found here count toward n_vendors, so the row's own quote is never counted as independent proof."""
    unit = r.get("price_unit")
    same_unit = [v["price"] for v in vendors if v["unit"] == unit]
    if r.get("price_usd") is not None and "price" in (r.get("grounded_fields") or []):
        same_unit.append(float(r["price_usd"]))
    return {"match": match, "vendors": vendors, "n_vendors": len(vendors), "unit": unit,
            "price_low": min(same_unit) if same_unit else None,
            "price_median": round(statistics.median(same_unit), 2) if same_unit else None}


def eligible(rows: List[dict]) -> List[dict]:
    """Survivors that pass the stress reach test, were not removed by Jev, and carry a cited price."""
    return [r for r in rows if r["screen"].get("verdict") == "SURVIVES" and r["screen"].get("survives_stress")
            and not r["screen"].get("price_flag") and not r.get("jev_removed")
            and "price" in (r.get("grounded_fields") or [])]


def _stale(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh).get("v") != VERSION
    except (OSError, ValueError):
        return True


def prove_all(groq, search, rows: List[dict], cache_dir: str, log=print) -> Dict[str, int]:
    os.makedirs(cache_dir, exist_ok=True)
    stats = {"cached": 0, "called": 0, "failed": 0, "vendors": 0}
    for r in eligible(rows):
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path) and not _stale(path):
            stats["cached"] += 1
            continue
        try:
            results: List[Dict[str, str]] = []
            for q in queries_for(r):
                results += search.search(q)
            results = results[:MAX_RESULTS]
            rendered = "\n".join(f"[{i}] {x['title']} | {x['snippet']} ({x['url']})" for i, x in enumerate(results))
            vendors = parse_vendors(extract_json_object(groq.complete(VENDOR_PROMPT.format(
                offer=r["offer"], buyer=r["buyer"], results=rendered), max_out=1200)), results, r["offer"]) if results else []
            match = judge_match(groq.complete, r)
        except SearchBudget as exc:
            log(str(exc))
            break
        except RuntimeError as exc:
            stats["failed"] += 1
            log(f"stopped on {r['offer'][:50]!r}: {exc}")
            break
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"v": VERSION, "offer": r["offer"], "proof": summarize(r, vendors, match)}, fh)
        stats["called"] += 1
        stats["vendors"] += len(vendors)
    stats["tokens"] = getattr(groq, "tokens_used", 0)
    stats["searches_paid"] = getattr(search, "fresh", 0)
    stats["searches_cached"] = getattr(search, "hits", 0)
    return stats


def apply_cached(rows: List[dict], cache_dir: str) -> List[dict]:
    out = []
    for r in rows:
        path = os.path.join(cache_dir, key(r) + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("v") == VERSION:
                r = dict(r, proof=data["proof"])
        out.append(r)
    return out
