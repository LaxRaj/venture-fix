"""Cluster near-duplicate candidates and measure saturation."""

from __future__ import annotations

import difflib
import re
from typing import Dict, List

_STOP = {"for", "and", "the", "a", "an", "of", "to", "in", "on", "service", "services", "management",
         "managed", "small", "business", "businesses", "solo", "automated", "ai", "assisted", "based"}
_FILLED = ("price_usd", "price_unit", "price_url", "hours_per_account_month", "pool_count", "pool_url")


def tokens(text: str) -> List[str]:
    return sorted({t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP})


def similar(a: dict, b: dict, ratio: float = 0.82, jaccard: float = 0.7) -> bool:
    ta, tb = set(tokens(a["offer"])), set(tokens(b["offer"]))
    if not ta or not tb:
        return False
    if len(ta & tb) / len(ta | tb) >= jaccard:
        return True
    return difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio() >= ratio


def _richness(c: dict) -> int:
    return sum(1 for k in _FILLED if c.get(k) is not None) + sum(1 for v in c["evidence"].values() if v)


def dedupe(candidates: List[dict]) -> List[dict]:
    """Keep the richest record per cluster; remember all source queries."""
    clusters: List[List[dict]] = []
    for c in candidates:
        for group in clusters:
            if similar(c, group[0]):
                group.append(c)
                break
        else:
            clusters.append([c])
    out = []
    for i, group in enumerate(clusters):
        best = dict(max(group, key=_richness))
        best["id"] = f"v{i:04d}"
        best["cluster_size"] = len(group)
        best["source_queries"] = sorted({g["source_query"] for g in group})
        best["first_query_index"] = min(g["query_index"] for g in group)
        out.append(best)
    return out


def saturation(unique: List[dict], n_queries: int, batch: int = 25) -> List[Dict[str, float]]:
    """New unique candidates per batch of queries.  A falling rate means coverage is saturating."""
    rows = []
    for start in range(0, n_queries, batch):
        end = min(start + batch, n_queries)
        new = sum(1 for u in unique if start <= u["first_query_index"] < end)
        rows.append({"queries": f"{start + 1}-{end}", "new_unique": new,
                     "per_query": round(new / (end - start), 2)})
    return rows
