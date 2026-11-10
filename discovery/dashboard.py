"""Build a self-contained HTML dashboard from whatever pipeline stages exist.

Works on a partial run: if the cache has queries but dedupe has not been run, candidates are
clustered in memory and marked as a preview.  The page needs no server and no network.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from . import dedupe as D, harvest as H, rank as R, screen as S, seeds, tagcheck as TC
from vstress.questions import ADMITTED

from . import questions_v2 as Q2

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "dashboard_template.html")
STAGE_FILES = ("verified.json", "grounded.json", "screened.json")
KEEP = ("id", "offer", "buyer", "task", "sector", "pain", "model", "price_usd", "price_unit", "price_url",
        "hours_per_account_month", "pool_count", "pool_url", "channel", "blockers", "evidence", "cluster_size",
        "grounded", "grounded_fields", "guess", "screen", "verify", "price_quoted", "evidence_quote", "price_basis",
        "pool_basis", "pool_note", "grounded_via", "price_kind", "price_rejected", "jev_removed", "tags2",
        "units_per_account_month", "volume_basis", "unit_name")


def _read(path: str):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _jev_summary(rows: List[dict], tags2: dict, quality, trusted: set) -> Dict[str, object]:
    """Per-question answer counts over everything tagged, the quality-check table, and the shortlist removals."""
    dist: Dict[str, Dict[str, int]] = {q.id: {} for q in Q2.ADMITTED_V2}
    for t in tags2.values():
        if t.get("status") != "ok":
            continue
        for q, a in t["final"].items():
            dist[q][a] = dist[q].get(a, 0) + 1
    return {
        "tagged": sum(1 for t in tags2.values() if t.get("status") == "ok"),
        "questions": [{"id": q.id, "text": q.text, "source": q.source, "answers": dist[q.id],
                       "labels": {o.key: o.label for o in q.options}} for q in Q2.ADMITTED_V2],
        "quality": quality, "trusted": sorted(trusted),
        # only survivors can be "removed from the shortlist"; a candidate that already failed the screen was never on it
        "removed": [{"id": r["id"], "offer": r["offer"], "reason": r["jev_removed"]}
                    for r in rows if r.get("jev_removed") and r["screen"].get("verdict") == "SURVIVES"],
    }


def collect(out_dir: str, stub: bool) -> Dict[str, object]:
    queries = seeds.all_queries()
    cache = os.path.join(out_dir, "cache")
    done = sum(1 for q in queries if os.path.exists(os.path.join(cache, q["id"] + ".json")))
    raw_meta = _read(os.path.join(out_dir, "raw.json"))
    unique_meta = _read(os.path.join(out_dir, "unique.json"))
    tags = _read(os.path.join(out_dir, "tags.json")) or {}

    rows: Optional[List[dict]] = None
    source = "none"
    for name in STAGE_FILES:
        rows = _read(os.path.join(out_dir, name))
        if rows is not None:
            source = name
            break
    preview = False
    if rows is None and unique_meta:
        rows, source = unique_meta["unique"], "unique.json"
    if rows is None and done:
        rows, source, preview = D.dedupe(H.load_cached(cache, queries)), "cache (in-memory clustering)", True
    rows = rows or []
    for r in rows:
        if "screen" not in r:
            r["screen"] = S.screen(r)
    tags2 = _read(os.path.join(out_dir, "tags_v2.json")) or {}
    quality = _read(os.path.join(out_dir, "tagcheck.json"))
    trusted = TC.trusted(quality)
    rows = R.apply_jev_gate(rows, tags2, trusted)
    jev = _jev_summary(rows, tags2, quality, trusted)

    n_raw = unique_meta["n_raw"] if unique_meta else (len(H.load_cached(cache, queries)) if done else 0)
    saturation = unique_meta["saturation"] if unique_meta else D.saturation(rows, len(queries)) if rows else []
    # Batches of queries that have not run yet are not "0 new": drop them and count them as pending.
    ran = [b for b in saturation if int(str(b["queries"]).split("-")[0]) - 1 < done]
    pending_batches = len(saturation) - len(ran)
    saturation = ran
    tag_ok = sum(1 for t in tags.values() if t.get("status") == "ok")
    stages = [
        {"name": "Seed matrix", "state": "done", "detail": f"{len(seeds.SECTORS)} sectors x {len(seeds.PAINS)} pains + {len(seeds.CREATOR_BUYERS)} creator buyers x {len(seeds.CREATOR_JOBS)} jobs = {len(queries)} queries"},
        {"name": "Generate", "state": "done" if done == len(queries) else ("partial" if done else "todo"),
         "detail": f"{done} of {len(queries)} queries cached"},
        {"name": "Dedupe", "state": "done" if unique_meta else ("preview" if preview else "todo"),
         "detail": f"{n_raw} raw -> {len(rows)} unique" if rows else "not run"},
        {"name": "Tag (Jev)", "state": "done" if tags2 else ("partial" if tags else "todo"),
         "detail": (f"{sum(1 for t in tags2.values() if t.get('status') == 'ok')} tagged, 2 shuffled runs; "
                    + (f"{len(trusted)} of {len(Q2.ADMITTED_V2)} questions validated" if quality else "no quality check yet"))
         if tags2 else ("legacy bank only" if tags else "not run")},
        {"name": "Screen", "state": "done" if source in STAGE_FILES else "todo",
         "detail": f"{len(rows)} screened" if source in STAGE_FILES else "computed live in this page"},
        {"name": "Ground", "state": "done" if source in ("grounded.json", "verified.json") else "todo",
         "detail": f"{sum(1 for r in rows if r.get('grounded'))} with cited figures"},
        {"name": "Verify", "state": "done" if source == "verified.json" else "todo",
         "detail": f"{sum(1 for r in rows if r.get('verify'))} graded"},
    ]
    slim = []
    for r in rows:
        d = {k: r[k] for k in KEEP if k in r}
        d["tags"] = tags.get(r["id"], {})
        slim.append(d)
    return {
        "generated": time.strftime("%Y-%m-%d %H:%M"), "stub": stub, "preview": preview, "source": source,
        "queries_total": len(queries), "queries_done": done, "n_raw": n_raw,
        "rows": slim, "saturation": saturation, "pending_batches": pending_batches, "stages": stages,
        "params": {"target": S.TARGET, "deliv": S.DELIV_HOURS, "out": S.OUT_PER_WEEK, "base": S.CONV_BASE,
                   "stress": S.CONV_STRESS, "bar": S.BAR_HR, "reach": S.REACH_LIMIT, "flag": S.PRICE_FLAG},
        "questions": {q.id: {"text": q.text, "family": q.family} for q in ADMITTED},
        "jev": jev,
        "top": _read(os.path.join(out_dir, "top.json")),
    }


def render(data: Dict[str, object]) -> str:
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        html = fh.read()
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
    return html.replace("/*__DATA__*/null", blob)


def build(out_dir: str, stub: bool) -> str:
    path = os.path.join(out_dir, "dashboard.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(collect(out_dir, stub)))
    return path
