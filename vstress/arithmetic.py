"""The arithmetic layer.  Every reported number lives here.

Three tests, all of which can fail:

    accounts needed   target / price
    capacity          usable hours / hours per account
    reach             contacts needed <= share of the buyer pool

No model touches this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .data import (
    DEFAULT_CONVERSION,
    ECONOMICS,
    MARKET_LIMIT,
    TARGET_MRR,
    USABLE_HOURS,
    Economics,
)

REACHABLE = "REACHABLE"
BURNS = "BURNS THE MARKET"
DEAD = "DEAD ON ARITHMETIC"

SEVERITY = {REACHABLE: 0, BURNS: 1, DEAD: 2}


def combine(hard: str, model: str) -> str:
    """Hard checks set a floor; a model may raise severity, never revive.

    Unknown model output fails open.  Unknown hard output is a programming
    error and raises immediately.
    """
    if hard not in SEVERITY:
        raise ValueError(f"unknown hard verdict: {hard!r}")
    if model not in SEVERITY:
        return hard
    return hard if SEVERITY[hard] >= SEVERITY[model] else model


def accounts_needed(target_mrr: float, price: float) -> float:
    if price <= 0:
        raise ValueError("price must be positive")
    return target_mrr / price


def capacity(service_hours: float, usable_hours: float = USABLE_HOURS) -> float:
    if service_hours <= 0:
        raise ValueError("service_hours must be positive")
    return usable_hours / service_hours


def contacts_needed(accounts: float, conversion: float) -> float:
    if conversion <= 0:
        raise ValueError("conversion must be positive")
    return accounts / conversion


@dataclass(frozen=True)
class Verdict:
    name: str
    accounts_needed: float
    capacity: float
    contacts_needed: float
    buyers: int
    market_share: float
    hard: str
    cause: str
    flips: Mapping[str, float]
    margins: Mapping[str, float]

    @property
    def alive(self) -> bool:
        return self.hard == REACHABLE

    @property
    def closest(self) -> Tuple[str, float]:
        """The input whose flip is nearest, and its relative distance."""
        order = ("service_hours", "price", "buyers", "conversion")
        key = min(order, key=lambda k: self.margins[k])
        return key, self.margins[key]


def verdict(row: Economics, target_mrr: float = TARGET_MRR,
            usable_hours: float = USABLE_HOURS,
            market_limit: float = MARKET_LIMIT) -> Verdict:
    need = accounts_needed(target_mrr, row.price)
    cap = capacity(row.service_hours, usable_hours)
    contacts = contacts_needed(need, row.conversion)
    share = contacts / row.buyers if row.buyers else float("inf")

    if need > cap:
        hard = DEAD
        cause = (
            f"{need:,.1f} accounts needed > {cap:,.1f} one-person capacity "
            f"at {row.service_hours:g} hrs/account"
        )
    elif share > market_limit:
        hard = BURNS
        cause = (
            f"{contacts:,.0f} contacts needed = {share:.0%} of the "
            f"{row.buyers:,} buyer pool (limit {market_limit:.0%})"
        )
    else:
        hard = REACHABLE
        cause = (
            f"{need:,.1f} accounts <= {cap:,.1f} capacity; "
            f"{contacts:,.0f} contacts = {share:.0%} of pool"
        )

    hours_flip = usable_hours * row.price / target_mrr
    price_flip = row.service_hours * target_mrr / usable_hours
    buyers_flip = contacts / market_limit
    conversion_flip = need / (row.buyers * market_limit)

    flips = {
        "service_hours": hours_flip,
        "price": price_flip,
        "buyers": buyers_flip,
        "conversion": conversion_flip,
    }
    current = {
        "service_hours": row.service_hours,
        "price": row.price,
        "buyers": float(row.buyers),
        "conversion": row.conversion,
    }
    margins = {
        key: _relative_distance(current[key], flips[key]) for key in current
    }
    return Verdict(
        name=row.name,
        accounts_needed=need,
        capacity=cap,
        contacts_needed=contacts,
        buyers=row.buyers,
        market_share=share,
        hard=hard,
        cause=cause,
        flips=flips,
        margins=margins,
    )


def _relative_distance(current: float, flip: float) -> float:
    denom = max(abs(current), abs(flip), 1e-12)
    return abs(current - flip) / denom


def board(rows: Iterable[Economics] = ECONOMICS) -> List[Verdict]:
    return [verdict(row) for row in rows]


def fmt_hours(value: float) -> str:
    return f"{value:.2f}"


def fmt_price(value: float) -> str:
    # A price break-even is the largest whole-dollar price that still works.
    return f"${math.floor(value):,}"


def fmt_int(value: float) -> str:
    return f"{value:,.0f}"


def break_even_table(rows: Iterable[Economics] = ECONOMICS) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for row in rows:
        v = verdict(row)
        out.append(
            (
                row.name,
                f"{row.service_hours:g} -> {fmt_hours(v.flips['service_hours'])}",
                f"{fmt_price(row.price)} -> {fmt_price(v.flips['price'])}",
            )
        )
    return out


def sensitivity(row: Economics) -> Dict[str, float]:
    """How far each input must move, as a multiple of its current value."""
    v = verdict(row)
    current = {
        "service_hours": row.service_hours,
        "price": row.price,
        "buyers": float(row.buyers),
        "conversion": row.conversion,
    }
    return {
        key: v.flips[key] / current[key] if current[key] else float("inf")
        for key in current
    }


def model_verdict(row: Economics, bands: Mapping[str, float]) -> str:
    """Recompute a verdict from model-moved input bands.

    The caller must still pass this through ``combine`` with the hard verdict.
    """
    moved = Economics(
        name=row.name,
        price=float(bands.get("price", row.price)),
        service_hours=float(bands.get("service_hours", row.service_hours)),
        buyers=int(round(bands.get("buyers", row.buyers))),
        price_provenance="model band",
        hours_provenance="model band",
        buyers_provenance="model band",
        conversion=float(bands.get("conversion", row.conversion)),
    )
    return verdict(moved).hard
