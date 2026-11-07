"""Read search snippets with a no-tool model and keep a price only if the text proves it.

The model is untrusted.  A price is accepted only when (1) the quote it returns is an exact
substring of the cited result's own title or snippet, (2) the price figure appears inside that
quote, and (3) the cited URL is one of the returned results.  Anything else leaves the guess alone.
Costs about 1-2k tokens per candidate, against 17-62k for model-driven browsing.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

from .groq_client import extract_json_object
from .verify import _found

VERSION = 3  # bump when the prompt or acceptance rules change; older cached extractions are redone (searches are cached, so no new credits)
KINDS = ("vendor_fee", "buyer_internal_cost", "ad_spend", "buyer_savings", "other")

PROMPT = (
    "You read web search results and extract ONE price. Service: {offer}, sold to {buyer}.\n"
    "Results:\n{results}\n"
    "Find a price that buyers or competing vendors charge for this kind of service. Reply with one JSON object only: "
    '{{"price_usd": number or null, "price_unit": "month" | "year" | "project" | "per_unit" | "contingency" | null, '
    '"source_index": integer or null, "quote": "text copied exactly from that result containing the price" or null, '
    '"price_kind": "vendor_fee" | "buyer_internal_cost" | "ad_spend" | "buyer_savings" | "other", '
    '"audience": "small_business" | "enterprise" | "unclear"}}. '
    "price_kind: vendor_fee = what a business pays an outside vendor, agency or freelancer for this service; "
    "buyer_internal_cost = what the work costs the buyer to do in-house (salaries, software they run, their own costs); "
    "ad_spend = an advertising or media budget, not a service fee; "
    "buyer_savings = money the buyer saves, recovers or earns, or any benefit claim such as 'save $2,000 a month', which is not what they pay; "
    "other = anything else. "
    "audience: enterprise if the price is for large companies or says enterprise, small_business if for small firms. "
    "Rules: use only the results above; copy the quote exactly; if no result states a price for this kind of "
    "service, answer with nulls. Do not estimate. You have no tools: do not try to open or browse anything."
)


def query_for(offer: str, buyer: str) -> str:
    return f"{offer} pricing per month for {buyer}"


RANGE = re.compile(r"\$\s?[\d,]+(?:\.\d+)?\s*(?:to|-|\u2013|\u2014|and)\s*\$?\s?[\d,]+", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def render(results: List[Dict[str, str]]) -> str:
    return "\n".join(f"[{i}] {r['title']} | {r['snippet']} ({r['url']})" for i, r in enumerate(results))


def validate(found: Optional[dict], results: List[Dict[str, str]]) -> Optional[dict]:
    """Return normalized price evidence, {"rejected": reason}, or None.  Never trusts the model's word."""
    if not found:
        return None
    try:
        price = float(str(found.get("price_usd")).replace(",", "").replace("$", ""))
        idx = int(found.get("source_index"))
    except (TypeError, ValueError):
        return None
    quote = found.get("quote")
    if price <= 0 or not isinstance(quote, str) or not quote.strip() or not (0 <= idx < len(results)):
        return None
    hit = results[idx]
    if _norm(quote) not in _norm(hit["title"] + " " + hit["snippet"]):
        return None                                  # quote not actually in the result
    if not _found(price, quote):
        return None                                  # figure not inside the quote
    unit = found.get("price_unit")
    if unit not in ("month", "year", "project", "per_unit", "contingency"):
        return None
    kind = found.get("price_kind")
    if kind not in KINDS:
        return {"rejected": "price kind not stated"}
    if kind != "vendor_fee":
        return {"rejected": f"quoted figure is {kind.replace('_', ' ')}, not a vendor's fee"}
    if found.get("audience") == "enterprise":
        return {"rejected": "quoted figure is an enterprise price"}
    basis = "as quoted"
    if RANGE.search(quote):                          # a quoted range: keep the figure the model chose and say so
        basis = "one end of a quoted range (check which)"
    out = {"price_usd": price, "price_quoted": price, "price_unit": unit, "price_url": hit["url"],
           "evidence_quote": quote.strip(), "price_basis": basis, "price_kind": kind}
    if unit == "year":                               # convert annual list prices to a monthly figure
        out.update(price_usd=round(price / 12, 2), price_unit="month", price_basis=basis + "; annual price / 12")
    return out


def extract_price(complete: Callable[[str], str], offer: str, buyer: str,
                  results: List[Dict[str, str]]) -> Optional[dict]:
    if not results:
        return None
    prompt = PROMPT.format(offer=offer, buyer=buyer, results=render(results))
    return validate(extract_json_object(complete(prompt)), results)
