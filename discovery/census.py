"""Buyer-pool counts from Census County Business Patterns (free key: CENSUS_API_KEY).

Pool = establishments with fewer than 20 employees in the sector's NAICS industries, summed over
the size classes the API labels.  This is an INDUSTRY-LEVEL UPPER BOUND, not one candidate's exact
buyers, so it makes the reach test lenient; the report and dashboard say so.  Sectors with no clean
NAICS code keep the model's guess.  The cited URL is the API query itself (key never included).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

YEAR = 2023
BASE = f"https://api.census.gov/data/{YEAR}/cbp"
UA = "venture-fix-discovery/1.0"
SMALL = (re.compile(r"less than 5", re.I), re.compile(r"\b5 to 9\b", re.I), re.compile(r"\b10 to 19\b", re.I))

# Seed sector -> NAICS 2017 codes (the field the API exposes).  None = no clean code; keep the guess.
SECTOR_NAICS: Dict[str, Optional[List[str]]] = {
    "trucking and freight carriers": ["484"],
    "freight brokers and 3PLs": ["488510"],
    "customs brokers and importers": ["488510"],
    "construction contractors": ["236", "238"],
    "roofing and HVAC contractors": ["238160", "238220"],
    "real estate brokerages": ["531210"],
    "property managers": ["5313"],
    "medical and dental practices": ["6211", "6212"],
    "veterinary clinics": ["541940"],
    "physical therapy and chiropractic clinics": ["621310", "621340"],
    "independent pharmacies": ["446110"],
    "law firms": ["541110"],
    "accounting and bookkeeping firms": ["5412"],
    "insurance agencies": ["524210"],
    "mortgage brokers": ["522310"],
    "restaurants": ["7225"],
    "ecommerce and Shopify stores": ["454110"],      # approximate: electronic shopping and mail-order
    "Amazon sellers": None,
    "manufacturers": None,                          # too broad to be a useful buyer pool
    "wholesale distributors": ["423", "424"],
    "nonprofits and charities": None,
    "schools and tutoring centers": ["611691"],
    "marketing and creative agencies": ["541810", "541430"],
    "YouTube and video creators": None,
    "podcasters and newsletter writers": None,
    "SaaS startups": ["5112"],                      # approximate: software publishers
    "staffing and recruiting firms": ["5613"],
    "auto repair and dealerships": ["8111", "4411"],
    "salons, gyms and wellness studios": ["812112", "713940"],
    "farms and agricultural suppliers": None,       # CBP excludes crop and animal production
    "energy and utilities consumers": None,
    "hotels and short-term rental hosts": ["7211"],
}


def url_for(naics: str, codes: Optional[List[str]] = None) -> str:
    """Query URL for one industry code.  When a sector sums several codes, they are all listed in the URL
    fragment (ignored by the server) so the citation records exactly what was summed."""
    base = f"{BASE}?get=ESTAB,EMPSZES,EMPSZES_LABEL&for=us:*&NAICS2017={naics}&LFO=001"
    return base + ("#naics=" + ",".join(codes) if codes and len(codes) > 1 else "")


def check_pool(url: str, claimed: float, key: str, get: Callable[[str], object] = None, memo: Optional[dict] = None):
    """Re-query every cited industry code with the key and compare the summed count.  None if unreachable."""
    get = get or _get_json
    memo = memo if memo is not None else {}
    base, _, frag = url.partition("#")
    codes = frag[len("naics="):].split(",") if frag.startswith("naics=") else [re.search(r"NAICS2017=([^&]+)", base).group(1)]
    total = 0
    for code in codes:
        if code not in memo:
            try:
                memo[code] = fetch_small(code, key, get)
            except RuntimeError:
                memo[code] = None
        if memo[code] is None:
            return None
        total += memo[code]
    return abs(total - claimed) < 0.5


def parse_small(rows: List[List[str]]) -> Optional[int]:
    """Sum establishments in the three small size classes from an API response.  None if any class is missing."""
    if not rows or len(rows) < 2:
        return None
    head = rows[0]
    try:
        i_est, i_lab = head.index("ESTAB"), head.index("EMPSZES_LABEL")
    except ValueError:
        return None
    total, seen = 0, set()
    for r in rows[1:]:
        for n, pat in enumerate(SMALL):
            if pat.search(r[i_lab] or ""):
                try:
                    total += int(r[i_est])
                except ValueError:
                    return None
                seen.add(n)
    return total if len(seen) == len(SMALL) else None


def _get_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Census request failed: {exc}") from exc
    if "Invalid Key" in body[:2000]:
        raise RuntimeError("Census rejected the API key (Invalid Key). A new key must be activated from the link in "
                           "Census's confirmation email before it works; otherwise re-copy it.")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise RuntimeError("Census returned a non-JSON response (bad query or service problem)") from exc


def fetch_small(naics: str, key: str, get: Callable[[str], object] = _get_json) -> Optional[int]:
    return parse_small(get(url_for(naics) + f"&key={key}"))  # type: ignore[arg-type]


class Census:
    """sector -> pool dict, cached on disk.  Returns None for sectors without a clean code."""

    name = "census"

    def __init__(self, cache_dir: str, get: Callable[[str], object] = _get_json) -> None:
        self.key = os.environ.get("CENSUS_API_KEY", "")
        if not self.key:
            raise RuntimeError("CENSUS_API_KEY is not set")
        self.dir, self.get = cache_dir, get
        os.makedirs(cache_dir, exist_ok=True)

    def sector_pool(self, sector: str) -> Optional[Dict[str, object]]:
        codes = SECTOR_NAICS.get(sector)
        if not codes:
            return None
        path = os.path.join(self.dir, re.sub(r"\W+", "_", sector) + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        total = 0
        for code in codes:
            n = fetch_small(code, self.key, self.get)
            if n is None:
                return None
            total += n
        out = {"pool_count": float(total), "pool_url": url_for(codes[0], codes), "pool_basis": "census",
               "pool_note": f"establishments with under 20 employees, NAICS {', '.join(codes)} ({YEAR}); industry-level upper bound"}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh)
        return out


class StubCensus:
    name = "census-stub"

    def sector_pool(self, sector: str) -> Optional[Dict[str, object]]:
        if not SECTOR_NAICS.get(sector):
            return None
        n = 5000 + (sum(map(ord, sector)) * 37) % 90000
        return {"pool_count": float(n), "pool_url": url_for("000000"), "pool_basis": "census",
                "pool_note": "STUB census count"}


def make_census(provider: str, cache_dir: str):
    if provider == "stub":
        return StubCensus()
    try:
        return Census(cache_dir)
    except RuntimeError:
        return None  # no key: pools stay guesses and the run says so
