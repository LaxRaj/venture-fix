"""Rank survivors and write the report.  Numbers come from screen.py, never from model prose."""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List

from .screen import CONV_BASE, OUT_PER_WEEK

GRADE_ORDER = {"A": 0, "B": 1, "C": 2}


def shortlist(rows: List[dict], top: int = 15) -> List[dict]:
    ok = [r for r in rows if r["screen"].get("verdict") == "SURVIVES"
          and r.get("verify", {}).get("grade") in ("A", "B")]
    ok.sort(key=lambda r: (GRADE_ORDER[r["verify"]["grade"]], r["screen"]["weeks_base"], -r["screen"]["per_hr"]))
    return ok[:top]


def cheap_test(r: dict, weeks: int = 3) -> str:
    contacts = int(OUT_PER_WEEK * weeks)
    expected = contacts * CONV_BASE
    return (f"Contact {contacts} {r['buyer']} over {weeks} weeks via: {r['channel'] or 'a free channel you pick'}. "
            f"Offer: {r['offer']} at ${r['price_usd']:,.0f}/mo. Expected paid at {CONV_BASE:.1%}: about {expected:.1f}. "
            f"Pass: at least 1 paid, or 3 booked calls from a warm reply.")


def report(rows: List[dict], n_queries: int, n_raw: int, sat: List[dict], stub: bool) -> str:
    verdicts = Counter(r["screen"]["verdict"] for r in rows)
    grades = Counter(r.get("verify", {}).get("grade", "-") for r in rows if r["screen"].get("verdict") == "SURVIVES")
    top = shortlist(rows)
    lines = ["# Venture universe", ""]
    if stub:
        lines += ["**STUB RUN: every number below is synthetic. This checks plumbing only.**", ""]
    lines += [f"Queries run: {n_queries}. Raw candidates: {n_raw}. Unique after clustering: {len(rows)}.", "",
              "## Screen verdicts", "", "| Verdict | Count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(verdicts.items(), key=lambda kv: -kv[1])]
    n_ground = sum(1 for r in rows if r.get("grounded"))
    lines += ["", f"Candidates whose price or pool was replaced by a cited, search-grounded figure: {n_ground}. "
              "Every other number is a model guess, so its verdict is provisional. Hours per account are always a guess.",
              "", "INSUFFICIENT, UNIT and CONTINGENCY rows were not screened; they need a monthly price, hours and "
              "a pool figure before the test can score them.", "",
              f"Survivors by evidence grade: {dict(grades)}. Grade C survivors need a manual price/pool check before they can be shortlisted.",
              "", "## Saturation (new unique candidates per 25 queries)", "", "| Queries | New unique | Per query |", "|---|---|---|"]
    lines += [f"| {s['queries']} | {s['new_unique']} | {s['per_query']} |" for s in sat]
    lines += ["", "A falling per-query rate means the seed matrix is covering the space; a flat rate means more queries would still find new ventures.",
              "", f"## Shortlist ({len(top)})", ""]
    if not top:
        lines.append("No candidate is both a screen survivor and grade A/B. Look at the grade C survivors below.")
    for i, r in enumerate(top, 1):
        s, tags = r["screen"], r.get("tags", {})
        lines += [f"### {i}. {r['offer']}", f"- Buyer: {r['buyer']}",
                  f"- ${r['price_usd']:,.0f}/mo, {r['hours_per_account_month']:g} h/account, ${s['per_hr']}/hr, "
                  f"{s['accounts']} accounts for $3k, {s['weeks_base']} weeks at base conversion "
                  f"({s['weeks_stress']} at stress); survives stress reach test: {s['survives_stress']}",
                  f"- Evidence grade {r['verify']['grade']}: {r['verify']['reason']}; grounded fields: {', '.join(r.get('grounded_fields', [])) or 'none'}",
                  f"- Blockers: {r['blockers'] or 'none stated'}"]
        if tags.get("status") == "ok":
            lines.append(f"- Jev escape rate {tags['escape_rate']:.0%} (higher means thinner evidence; diagnostic only)")
        lines += [f"- Test: {cheap_test(r)}", ""]
    c_surv = [r for r in rows if r["screen"].get("verdict") == "SURVIVES" and r.get("verify", {}).get("grade") == "C"]
    if c_surv:
        lines += ["## Survivors needing a manual evidence check (grade C)", ""]
        lines += [f"- {r['offer']} ({r['buyer']}): {r['verify']['reason']}" for r in c_surv[:40]]
        lines.append("")
    lines += ["## All candidates", "", "| ID | Offer | Verdict | $/hr | Weeks to $3k |", "|---|---|---|---|---|"]
    for r in rows:
        s = r["screen"]
        lines.append(f"| {r['id']} | {r['offer'][:60]} | {s['verdict']} | {s.get('per_hr', '')} | {s.get('weeks_base', '')} |")
    return "\n".join(lines) + "\n"
