#!/usr/bin/env python3
"""Corrected screen for a solo founder: capacity sweep, target sweep, time to first dollar.

Imports vstress; edits nothing in it.  Run: python3 analysis/corrected_screen.py

Declared assumptions (not measured):
  work month 260-345 hrs (60-80 hrs/wk); delivery share 60-75% -> 150/190/230 delivery hrs.
  (260*0.60=156 ~150 ; 300*0.63=190 ; 345*0.67=230.)  Remainder is sales, admin, support.
  Time-to-first-customer ignores sales-cycle lag and churn.  Geometric model, independent contacts.
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, __file__.rsplit("/analysis/", 1)[0])

from vstress.arithmetic import verdict, DEAD, BURNS, REACHABLE
from vstress.data import ECONOMICS, USABLE_HOURS, WEEKS_PER_MONTH

CAPS = (150.0, 190.0, 230.0)
TARGETS = (3_000.0, 5_000.0, 10_000.0)
CONVS = (0.011, 0.006, 0.001, 0.0005)
CONTACTS_WK = (20, 60, 100)
SHORT = {DEAD: "DEAD", BURNS: "BURN", REACHABLE: "ok"}


def sweep() -> None:
    print("1. VERDICT BY (delivery hrs/month, target MRR).  ok / BURN (reach) / DEAD (capacity)")
    print(f"{'venture':30s}" + "".join(f"{int(c)}h:${int(t/1000)}k ".rjust(11) for c in CAPS for t in TARGETS))
    base_flips = []
    for r in ECONOMICS:
        cells = []
        for c in CAPS:
            for t in TARGETS:
                cells.append(SHORT[verdict(r, t, c).hard].rjust(11))
        print(f"{r.name[:29]:30s}" + "".join(cells))
    print("\n   Baseline check (173.2h, $10k):")
    for r in ECONOMICS:
        v = verdict(r, 10_000.0, USABLE_HOURS)
        print(f"   {r.name:32s} {v.hard}")
    print("\n   Rows whose verdict differs from baseline (173.2h/$10k):")
    for r in ECONOMICS:
        b = verdict(r, 10_000.0, USABLE_HOURS).hard
        diffs = [f"{int(c)}h/${int(t/1000)}k->{SHORT[verdict(r,t,c).hard]}"
                 for c in CAPS for t in TARGETS if verdict(r, t, c).hard != b]
        if diffs:
            print(f"   {r.name:32s} base {SHORT[b]}: " + ", ".join(diffs))
    print("\n   Bars: $/delivery-hr >= target/cap ; price*buyers*conv >= 2*target")
    for c in CAPS:
        print(f"   {int(c)}h: " + ", ".join(f"${t/1000:.0f}k needs ${t/c:,.2f}/hr" for t in TARGETS))


def weeks_first(c_wk: float, p: float, q: float = 0.5) -> float:
    """Weeks until P(>=1 customer) = q, at c_wk contacts/week."""
    return math.log(1 - q) / math.log(1 - p) / c_wk


def first_dollar() -> None:
    print("\n2. TIME TO FIRST CUSTOMER (contacts/week x conversion), price-independent")
    print(f"{'conv':>7s}" + "".join(f"  {c}/wk: exp / p50 / p90 wks".rjust(30) for c in CONTACTS_WK))
    for p in CONVS:
        row = f"{p:7.2%}"
        for c in CONTACTS_WK:
            row += f"{1/(p*c):9.1f} /{weeks_first(c,p,.5):6.1f} /{weeks_first(c,p,.9):6.1f}".rjust(30)
        print(row)
    print("\n   Weeks to reach target MRR = ceil(target/price) accounts / (contacts_wk*conv).  Expected value.")
    print("   Shown at 60 contacts/wk.  'n' = accounts needed.  Dash = pool burned (contacts > 50% of buyers).")
    for t in (3_000.0, 5_000.0):
        print(f"\n   Target ${t:,.0f}")
        print(f"   {'venture':30s}{'n':>4s}" + "".join(f"{p:>10.2%}" for p in CONVS) + "   (weeks)")
        for r in ECONOMICS:
            n = math.ceil(t / r.price)
            cells = ""
            for p in CONVS:
                contacts = n / p
                if contacts > 0.5 * r.buyers:
                    cells += "-".rjust(10)
                else:
                    cells += f"{contacts/60:10.0f}"
            print(f"   {r.name[:29]:30s}{n:4d}{cells}")
    print("\n   Note the first dollar needs only ONE account; the price/hours/pool tests do not gate it at all.")
    print("   Pool check for first dollar: 1/conv contacts <= 50% of buyers -> trivially true for every row.")


if __name__ == "__main__":
    sweep()
    first_dollar()
