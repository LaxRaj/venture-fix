"""Hard arithmetic screen.  Same math as analysis/ideas_screen.py.

Only flat monthly-price rows with price, hours and pool can be screened.  Everything
else is routed to a named bucket instead of being guessed.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

DELIV_HOURS = 190.0      # delivery hrs/month at 60-80 hrs/week
OUT_PER_WEEK = 100.0     # outbound contacts per week
CONV_BASE = 0.003        # contact -> paid, base (analysis/phase2_channels.md)
CONV_STRESS = 0.001
BAR_HR = 57.74           # $10k MRR / 173.2 h, the repo's revenue-per-hour bar
REACH_LIMIT = 0.5        # contacting more than half the pool burns the market
TARGET = 3000.0          # first milestone, MRR
PRICE_FLAG = 2500.0      # monthly prices above this are flagged as unlikely for small-business buyers


def screen(c: dict, target: float = TARGET, flag: float = PRICE_FLAG) -> Dict[str, object]:
    unit, price, hrs, pool = c.get("price_unit"), c.get("price_usd"), c.get("hours_per_account_month"), c.get("pool_count")
    if unit == "contingency":
        return {"verdict": "CONTINGENCY", "why": "paid as a share of recovery; flat-price test cannot score it"}
    if unit in ("project", "per_unit"):
        return {"verdict": "UNIT", "why": f"priced per {unit}; needs monthly accounts-per-month to convert"}
    if unit != "month" or price is None or hrs is None or pool is None:
        missing = [n for n, v in (("price", price), ("hours", hrs), ("pool", pool)) if v is None]
        return {"verdict": "INSUFFICIENT", "why": "missing " + ", ".join(missing or ["monthly price unit"])}

    per_hr = price / hrs
    accounts = math.ceil(target / price)   # whole customers: half a customer does not exist
    cap = DELIV_HOURS / hrs
    row: Dict[str, object] = {"per_hr": round(per_hr, 1), "accounts": accounts, "cap": round(cap, 1),
                              "price_flag": price > flag}
    for tag, conv in (("base", CONV_BASE), ("stress", CONV_STRESS)):
        contacts = accounts / conv
        row[f"contacts_{tag}"] = round(contacts)
        row[f"weeks_{tag}"] = round(contacts / OUT_PER_WEEK, 1)
        row[f"pool_ok_{tag}"] = contacts <= pool * REACH_LIMIT
    if per_hr < BAR_HR:
        row.update(verdict="FAILS_HR", why=f"${per_hr:.0f}/hr is below the ${BAR_HR}/hr bar")
    elif accounts > cap:
        row.update(verdict="FAILS_CAP", why=f"needs {accounts:.1f} accounts, capacity is {cap:.1f}")
    elif not row["pool_ok_base"]:
        row.update(verdict="FAILS_POOL", why="reaching enough contacts burns over half the pool")
    else:
        row.update(verdict="SURVIVES", why="passes capacity and reach at base conversion")
    row["survives_stress"] = bool(row["pool_ok_stress"]) and row["verdict"] == "SURVIVES"
    return row
