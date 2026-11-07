"""Grade the evidence behind a survivor.

A  page fetched and the claimed number appears on it
B  a URL is cited and the page loaded, but the number was not found
C  no URL, or the page could not be fetched (reason recorded; check by hand)

Grade C cannot enter the shortlist.  Fetching is read-only.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional, Tuple

Fetcher = Callable[[str], Tuple[Optional[int], str]]


def fetch(url: str, timeout: int = 20) -> Tuple[Optional[int], str]:
    req = urllib.request.Request(url, headers={"User-Agent": "venture-fix-verifier/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(400_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None, ""


def stub_fetch(url: str) -> Tuple[Optional[int], str]:
    return 200, "STUB PAGE"


def number_forms(value: float) -> Tuple[str, ...]:
    whole = int(round(value))
    return tuple({str(whole), f"{whole:,}", f"${whole:,}", f"${whole}"})


def _found(value: Optional[float], text: str) -> bool:
    if value is None:
        return False
    return any(re.search(r"(?<![\d,.])" + re.escape(f) + r"(?![\d,])", text) for f in number_forms(value))


def grade(c: dict, fetcher: Fetcher = fetch, census_check=None) -> Dict[str, object]:
    """A needs the PRICE confirmed on its cited page; a confirmed pool alone is at most B."""
    price_value = c.get("price_quoted") if c.get("price_quoted") is not None else c.get("price_usd")
    checks = [("price", c.get("price_url"), price_value), ("pool", c.get("pool_url"), c.get("pool_count"))]
    checks = [x for x in checks if x[1]]
    if not checks:
        return {"grade": "C", "reason": "no cited URL"}
    loaded, price_hit, any_hit = False, False, False
    reasons = []
    for what, url, value in checks:
        if url.startswith("https://api.census.gov/") and census_check is not None:
            ok = census_check(url, value)  # re-query the API with the key from the environment
            if ok is None:
                reasons.append(f"census API unreachable {url}")
                continue
            loaded, any_hit = True, any_hit or ok
            continue
        status, text = fetcher(url)
        if status is None or status >= 400:
            reasons.append(f"unreachable ({status}) {url}")
            continue
        loaded = True
        if _found(value, text):
            any_hit = True
            price_hit = price_hit or what == "price"
    if price_hit:
        return {"grade": "A", "reason": "cited price page fetched and the figure appears on it"}
    if any_hit:
        return {"grade": "B", "reason": "pool figure confirmed; the price is still a guess or unconfirmed"}
    if loaded:
        return {"grade": "B", "reason": "page loaded, figure not found; check by hand"}
    return {"grade": "C", "reason": "; ".join(reasons) or "unreachable"}
