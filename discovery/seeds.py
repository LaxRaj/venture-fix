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


# ---------------------------------------------------------------------------
# Creator seed set.
#
# The sector x pain matrix above crosses every sector with every pain, so a creator sector received pains such as
# "claims, denials or invoice disputes" and produced offers that are not creator ventures.  This set is built for
# the creator economy instead: who the buyer is, and the jobs creators actually pay editors and agencies for.
# ---------------------------------------------------------------------------

CREATOR_BUYERS = (
    "YouTubers with 10K+ subscribers", "podcast hosts", "newsletter writers and Substack authors",
    "Twitch and live-stream creators", "course creators and coaches",
    "short-form creators on TikTok, Reels and Shorts", "membership and community creators",
)

CREATOR_JOBS = (
    "cutting long videos into short clips", "editing long-form video", "designing thumbnails and titles",
    "repurposing one video into posts for other platforms", "producing and editing podcast episodes",
    "finding and closing sponsorship and brand deals", "managing the community and membership",
    "reporting on channel growth and analytics", "writing scripts, research and show notes",
    "captioning, translating and dubbing", "finding clients and leads for the creator's own services",
)

# Creator work is mostly sold per video or per clip, so that model appears alongside retainers and tools.
CREATOR_MODELS = ("monthly retainer", "per-video or per-clip fee", "monthly retainer", "small software tool")


def build_creator_queries(limit: int | None = None) -> List[Dict[str, str]]:
    """Deterministic creator queries: every buyer type x every job.  sector holds the buyer, pain holds the job."""
    out: List[Dict[str, str]] = []
    n = 0
    for b in CREATOR_BUYERS:
        for j in CREATOR_JOBS:
            model = CREATOR_MODELS[n % len(CREATOR_MODELS)]
            n += 1
            text = (
                f"{b}: creators who pay a freelancer, editor or small agency for {j}. "
                f"Find concrete offers a solo operator could sell as a {model}. "
                f"Include what editors and agencies charge today."
            )
            out.append({"id": query_id(text), "sector": b, "pain": j, "model": model, "text": text})
    return out[:limit] if limit else out


def all_queries() -> List[Dict[str, str]]:
    """The core sector matrix followed by the creator set; the core queries keep their order and ids."""
    return build_queries() + build_creator_queries()
