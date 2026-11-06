"""Seed matrix: sector x recurring pain x delivery model -> query cells.

Coverage is systematic: every cell is a query, so saturation can be measured
against the matrix instead of against whatever a model volunteers.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List

# NAICS-style sectors of small and mid-size buyers (free public taxonomy).
SECTORS = (
    "trucking and freight carriers", "freight brokers and 3PLs", "customs brokers and importers",
    "construction contractors", "roofing and HVAC contractors", "real estate brokerages",
    "property managers", "medical and dental practices", "veterinary clinics",
    "physical therapy and chiropractic clinics", "independent pharmacies", "law firms",
    "accounting and bookkeeping firms", "insurance agencies", "mortgage brokers",
    "restaurants", "ecommerce and Shopify stores", "Amazon sellers", "manufacturers",
    "wholesale distributors", "nonprofits and charities", "schools and tutoring centers",
    "marketing and creative agencies", "YouTube and video creators", "podcasters and newsletter writers",
    "SaaS startups", "staffing and recruiting firms", "auto repair and dealerships",
    "salons, gyms and wellness studios", "farms and agricultural suppliers",
    "energy and utilities consumers", "hotels and short-term rental hosts",
)

PAINS = (
    "recurring compliance paperwork and filings", "claims, denials or invoice disputes",
    "audit and recovery of overpaid or lost money", "lead generation and appointment setting",
    "content production and repurposing", "bookkeeping, reconciliation and reporting",
    "scheduling, dispatch and follow-up", "document drafting and proposal writing",
    "data entry and cleanup between systems", "review, reputation and listing management",
)

MODELS = ("monthly retainer", "per-unit fee", "contingency on recovered money", "small software tool")


def query_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_queries(limit: int | None = None) -> List[Dict[str, str]]:
    """Deterministic list of query cells.  Each sector x pain cell gets one model,
    rotated, so the matrix stays about 320 cells instead of 1,280."""
    out: List[Dict[str, str]] = []
    n = 0
    for s in SECTORS:
        for p in PAINS:
            model = MODELS[n % len(MODELS)]
            n += 1
            text = (
                f"Small businesses in '{s}' that pay someone for '{p}'. "
                f"Find concrete offers a solo operator could sell as a {model}."
            )
            out.append({"id": query_id(text), "sector": s, "pain": p, "model": model, "text": text})
    return out[:limit] if limit else out
