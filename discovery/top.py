"""Score proven survivors, take the top 20, pick 7.  Pure functions of their inputs: no network.

Every number is arithmetic on fields that already exist.  The score is a transparent sum of four parts, and
the re-screen is deliberately pessimistic (lowest proven price, double the hours, half the volume).
A candidate is "Proven" only when the same-service check said yes AND two or more independent vendors
were found AND it still survives the pessimistic screen.  The list is never padded to look better.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from . import rank as R
from .dedupe import similar
from .screen import BAR_HR, CONV_STRESS, OUT_PER_WEEK, screen

TOP_N, PICK_N, PER_SECTOR = 20, 7, 2
POINTS = {"proof": 40, "money": 35, "reach": 15, "fit": 10}
TEST_CONTACTS = 300
LOADS = (100, 300, 700)   # contacts per week to show


def conservative(r: dict) -> Optional[dict]:
    """Re-screen with the lowest proven price, twice the hours and half the volume.  None if it no longer survives."""
    proof = r.get("proof") or {}
    c = dict(r)
    if proof.get("price_low") is not None:
        c["price_usd"] = proof["price_low"]
    if c.get("hours_per_account_month") is not None:
        c["hours_per_account_month"] = c["hours_per_account_month"] * 2
    if c.get("units_per_account_month") is not None:
        c["units_per_account_month"] = c["units_per_account_month"] / 2
    s = screen(c)
    if s.get("verdict") != "SURVIVES" or not s.get("survives_stress") or s.get("price_flag"):
        return None
    return s


def _tag(r: dict, q: str, trusted: set) -> Optional[str]:
    t = r.get("tags2") or {}
    if t.get("status") != "ok" or q not in trusted:
        return None
    a = (t.get("final") or {}).get(q)
    return None if a in (None, "unstable", "escape") else a


def score(r: dict, s: dict, trusted: set) -> Dict[str, float]:
    """The four parts, each 0..POINTS[part].  An untrusted or missing tag earns half of its share: no penalty, no credit."""
    proof = r.get("proof") or {}
    n = min(proof.get("n_vendors", 0), 5)
    p = POINTS["proof"] * n / 5 * {"yes": 1.0, "unclear": 0.5}.get(proof.get("match"), 0.0)
    money = 20 * min(s["per_hr"] / (3 * BAR_HR), 1.0) + 15 * max(0.0, 1 - s["weeks_stress"] / 100)
    reach = (8 if r.get("pool_basis") == "census" else 0) + (4 if s.get("pool_ok_stress") else 0)
    ch = _tag(r, "access_channel", trusted)
    reach += 3 if ch else 1.5
    dm, rw = _tag(r, "delivery_model", trusted), _tag(r, "regulated_work", trusted)
    fit = (4 if dm == "service" else 1 if dm else 2) + (3 if rw == "plain" else 0 if rw else 1.5) + (3 if not (r.get("blockers") or "").strip() else 0)
    return {k: round(v, 1) for k, v in (("proof", p), ("money", money), ("reach", reach), ("fit", fit))}


def label(r: dict) -> str:
    proof = r.get("proof") or {}
    return "Proven" if proof.get("match") == "yes" and proof.get("n_vendors", 0) >= 2 else "Partial"


def kill_rule(weeks: int = 3) -> str:
    return f"No paid account and fewer than 3 booked calls after {weeks} weeks: drop it and move to the next candidate."


def entry(r: dict, s: dict, parts: Dict[str, float]) -> dict:
    proof = r["proof"]
    return {"id": r["id"], "offer": r["offer"], "buyer": r["buyer"], "sector": r.get("sector", ""),
            "label": label(r), "score": round(sum(parts.values()), 1), "parts": parts,
            "match": proof["match"], "n_vendors": proof["n_vendors"], "vendors": proof["vendors"],
            "price_low": proof["price_low"], "price_median": proof["price_median"], "price_unit": proof["unit"],
            "own_quote": r.get("evidence_quote"), "own_url": r.get("price_url"),
            "cons": {"per_hr": s["per_hr"], "accounts": s["accounts"], "weeks_stress": s["weeks_stress"],
                     "monthly_price": s.get("monthly_price", proof["price_low"] or r.get("price_usd")),
                     "hours": r["hours_per_account_month"] * 2, "derived": bool(s.get("derived"))},
            "pool_count": r.get("pool_count"), "pool_basis": r.get("pool_basis"),
            "measured": [k for k, ok in (("price quote found in search result", True), ("buyer pool from Census", r.get("pool_basis") == "census")) if ok],
            "guessed": ["hours per account"] + (["monthly volume"] if r.get("units_per_account_month") is not None else []),
            "channel": r.get("channel"), "blockers": r.get("blockers"),
            "test": R.cheap_test(r, weeks=3), "kill": kill_rule()}


def pick_seven(top: List[dict], rows_by_id: Dict[str, dict]) -> List[str]:
    """Greedy over Proven entries in rank order: at most PER_SECTOR per sector, skip near-duplicate offers."""
    picks: List[str] = []
    per: Dict[str, int] = {}
    for e in top:
        if e["label"] != "Proven" or len(picks) >= PICK_N:
            continue
        if per.get(e["sector"], 0) >= PER_SECTOR:
            continue
        if any(similar(rows_by_id[e["id"]], rows_by_id[p]) for p in picks):
            continue
        picks.append(e["id"])
        per[e["sector"]] = per.get(e["sector"], 0) + 1
    return picks


def load_table(n_tests: int) -> List[dict]:
    contacts = n_tests * TEST_CONTACTS
    return [{"per_week": w, "weeks": math.ceil(contacts / w), "contacts": contacts} for w in LOADS]


def build(rows: List[dict], trusted: set) -> dict:
    """rows: verified rows with `proof` attached (prove.apply_cached) and the Jev gate applied."""
    scored = []
    for r in rows:
        if not r.get("proof"):
            continue
        s = conservative(r)
        if s is None:
            continue
        scored.append((r, entry(r, s, score(r, s, trusted))))
    # Proven first, then by score: a Partial never outranks a Proven.
    scored.sort(key=lambda t: (t[1]["label"] != "Proven", -t[1]["score"], t[0]["id"]))
    top = [e for _, e in scored[:TOP_N]]
    by_id = {r["id"]: r for r, _ in scored}
    picks = pick_seven(top, by_id)
    proven = sum(1 for _, e in scored if e["label"] == "Proven")
    return {"top": top, "picks": picks, "load": load_table(len(picks)),
            "counts": {"eligible_proved": len(scored), "proven": proven, "in_top": len(top),
                       "proven_in_top": sum(1 for e in top if e["label"] == "Proven"), "picked": len(picks)},
            "params": {"points": POINTS, "stress_conv": CONV_STRESS, "out_per_week": OUT_PER_WEEK, "bar_hr": BAR_HR,
                       "test_contacts": TEST_CONTACTS, "trusted_tags": sorted(trusted)}}


def markdown(t: dict, stub: bool) -> str:
    c = t["counts"]
    lines = ["# Top 20 and the 7 to start", ""]
    if stub:
        lines += ["**STUB RUN: every number below is synthetic. This checks plumbing only.**", ""]
    lines += [f"Proved candidates that still survive the pessimistic screen: {c['eligible_proved']}. Proven: {c['proven']}. "
              f"In the top {len(t['top'])}: {c['proven_in_top']} Proven, {len(t['top']) - c['proven_in_top']} Partial. Picked: {c['picked']} of {PICK_N}.", "",
              "Proven = same-service check said yes in both runs, two or more independent vendors with a price quote found in the "
              "search result text, and it survives the screen with the lowest proven price, double the hours and half the volume. "
              "Hours and volume are still guesses. Nothing here is a forecast of revenue.", ""]
    if c["picked"] < PICK_N:
        lines += [f"**Only {c['picked']} Proven candidates passed the pick rules (max {PER_SECTOR} per sector, no near-duplicates). The list is not padded.**", ""]
    lines += ["## The picks", ""]
    by_id = {e["id"]: e for e in t["top"]}
    for i, pid in enumerate(t["picks"], 1):
        e = by_id[pid]
        lines += [f"### {i}. {e['offer']}", f"- Buyer: {e['buyer']}",
                  f"- Score {e['score']} (proof {e['parts']['proof']}, money {e['parts']['money']}, reach {e['parts']['reach']}, fit {e['parts']['fit']})",
                  f"- Lowest proven price ${e['price_low']:,.0f}/{e['price_unit']}; {e['cons']['accounts']} accounts for $3k; "
                  f"${e['cons']['per_hr']}/hr and {e['cons']['weeks_stress']} weeks at pessimistic settings",
                  "- Already charging: " + "; ".join(f"[{v['vendor']}]({v['url']}) \"{v['quote']}\"" for v in e["vendors"]),
                  f"- Test: {e['test']}", f"- Kill rule: {e['kill']}", ""]
    lines += ["## Outreach load for the picks", "", "| Contacts per week | Weeks to finish all tests |", "|---|---|"]
    lines += [f"| {x['per_week']} | {x['weeks']} |" for x in t["load"]]
    lines += ["", f"## Top {len(t['top'])}", "", "| # | Offer | Label | Score | Vendors | Low price | $/hr | Weeks |", "|---|---|---|---|---|---|---|---|"]
    for i, e in enumerate(t["top"], 1):
        star = " *" if e["id"] in t["picks"] else ""
        lines.append(f"| {i} | {e['offer'][:60]}{star} | {e['label']} | {e['score']} | {e['n_vendors']} | "
                     f"${e['price_low']:,.0f}/{e['price_unit']} | {e['cons']['per_hr']} | {e['cons']['weeks_stress']} |")
    lines += ["", "\\* = picked."]
    return "\n".join(lines) + "\n"
