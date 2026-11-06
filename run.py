#!/usr/bin/env python3
"""Venture stress test CLI."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from vstress import arithmetic, calibrate, fieldtest
from vstress.data import ECONOMICS, provenance_counts


def _load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE lines without overriding the real environment."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def _screen() -> None:
    rows = arithmetic.board(ECONOMICS)
    print("VENTURE STRESS TEST - $10k MRR bar, one person, 173.2 usable hours/month")
    print("No revenue forecast. Three arithmetic tests and their break-evens.")
    print()
    print(f"{'venture':30} {'price':>7} {'prov':>5} {'hrs':>5} {'need':>6} {'cap':>6} "
          f"{'contacts':>9} {'pool':>7} {'verdict':20} {'hrs flip':>8} {'price flip':>10}")
    print("-" * 134)
    for row, v in zip(ECONOMICS, rows):
        print(
            f"{row.name[:30]:30} {arithmetic.fmt_price(row.price):>7} "
            f"{_prov(row):>5} {row.service_hours:>5.1f} "
            f"{v.accounts_needed:>6.1f} {v.capacity:>6.1f} "
            f"{v.contacts_needed:>9,.0f} {row.buyers:>7,} {v.hard:20} "
            f"{arithmetic.fmt_hours(v.flips['service_hours']):>8} "
            f"{arithmetic.fmt_price(v.flips['price']):>10}"
        )
    print()
    counts = {}
    for v in rows:
        counts[v.hard] = counts.get(v.hard, 0) + 1
    print("verdicts: " + ", ".join(f"{k}: {counts[k]}" for k in (arithmetic.DEAD, arithmetic.BURNS, arithmetic.REACHABLE)))
    print()
    print("break-evens (the actual output):")
    print(f"{'venture':30} {'service hrs now -> flips at':30} {'price now -> flips at':24}")
    print("-" * 90)
    for name, hours, price in arithmetic.break_even_table():
        print(f"{name[:30]:30} {hours:30} {price:24}")
    print()
    print("hours are hrs/account/month. price flips are floored to whole dollars.")
    print("prov: A=anchored price, E=estimate, Y=your buyer count.")
    print("provenance:")
    prov = provenance_counts()
    for key, label in (("price", "price"), ("service_hours", "hours"), ("buyers", "buyers")):
        bits = ", ".join(f"{value}: {count}" for value, count in sorted(prov[key].items()))
        print(f"  {label:8} {bits}")
    print("  anchored and estimate are never printed as the same kind of number.")


def _prov(row) -> str:
    return (
        f"{row.price_provenance[0].upper()}/"
        f"{row.hours_provenance[0].upper()}/"
        f"{row.buyers_provenance[0].upper()}"
    )


def _brief() -> None:
    print("BRIEF - per-venture verdict and what flips it")
    print()
    for row in ECONOMICS:
        v = arithmetic.verdict(row)
        key, margin = v.closest
        print(f"{row.name} - {v.hard}")
        print(f"  {v.cause}")
        print(
            f"  flips: hours {arithmetic.fmt_hours(v.flips['service_hours'])} "
            f"(now {row.service_hours:g}), price {arithmetic.fmt_price(v.flips['price'])} "
            f"(now {arithmetic.fmt_price(row.price)}), "
            f"pool {v.flips['buyers']:,.0f} (now {row.buyers:,})"
        )
        print(
            f"  nearest: {fieldtest.INPUT_LABEL[key]} is {margin:.1%} from its flip; "
            f"field calls: {fieldtest.sample_size(margin)}"
        )
        print(
            f"  provenance: price {row.price_provenance}, hours {row.hours_provenance}, "
            f"buyers {row.buyers_provenance}"
        )
        print()


def _field(name: str | None) -> None:
    if name:
        print(fieldtest.field_report(name))
    else:
        print(fieldtest.shopping_report())


def _calibrate(provider: str, seed: int, permutations: int) -> None:
    print(calibrate.report(provider, seed=seed, permutations=permutations))


def _ingest(path: str) -> None:
    print(fieldtest.ingest(path))


def main(argv: Sequence[str] | None = None) -> int:
    _load_dotenv()
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Screen pre-revenue ventures without forecasting revenue.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("screen", help="the board, with break-evens")

    sub.add_parser("brief", help="per-venture verdict and what flips it")

    field_parser = sub.add_parser("field", help="what to measure, and the call script")
    field_parser.add_argument("--venture", default=None, help="venture name (fuzzy match)")

    cal = sub.add_parser("calibrate", help="score the question bank against labels")
    cal.add_argument("--provider", choices=("stub", "generative", "jev"), default="stub")
    cal.add_argument("--seed", type=int, default=91, help="stub seed (default 91)")
    cal.add_argument("--permutations", type=int, default=calibrate.PERMUTATIONS)

    ing = sub.add_parser("ingest", help="replace invented inputs with measured values")
    ing.add_argument("--file", required=True, help="JSON or CSV measurements")

    args = parser.parse_args(argv)
    if args.command == "screen":
        _screen()
    elif args.command == "brief":
        _brief()
    elif args.command == "field":
        _field(args.venture)
    elif args.command == "calibrate":
        _calibrate(args.provider, args.seed, args.permutations)
    elif args.command == "ingest":
        _ingest(args.file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
