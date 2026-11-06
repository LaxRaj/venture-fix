#!/usr/bin/env python3
"""Reverse-engineering harness for the venture stress test.

This does not forecast revenue either.  It derives what the screen is actually
a function of, proves the derivation against every row, and then asks the
question the screen never prints: at full capacity, how many dollars a month is
one person allowed to earn, and which input is the one that decides it.

Run:  python3 analysis/reverse.py
      python3 analysis/reverse.py --check   (assertions only, exit code)
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import replace
from typing import Dict, List, Tuple

sys.path.insert(0, __file__.rsplit("/analysis/", 1)[0])

from vstress import arithmetic as A
from vstress import mapping as M
from vstress.data import (
    DEFAULT_CONVERSION,
    ECONOMICS,
    MARKET_LIMIT,
    TARGET_MRR,
    USABLE_HOURS,
    Economics,
)
from vstress.fieldtest import sample_size

# The two constants the whole board reduces to.
BAR = TARGET_MRR / USABLE_HOURS          # $57.74 of revenue per delivery hour
MARKET_BAR = 2.0 * TARGET_MRR            # $20,000 = price * pool * conversion
K = USABLE_HOURS / TARGET_MRR            # 0.01732 = hours_flip / price

CONTACTS_PER_MONTH = 260                 # 60 contacts/week, a declared pace
MONTHS = 12

CHECKS: List[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{label}: {detail}")
    CHECKS.append(label)


def money(value: float) -> str:
    return f"${value:,.0f}"


def money2(value: float) -> str:
    return f"${value:,.2f}"


def facts(row: Economics) -> Tuple[float, float, float]:
    """(dollars per delivery hour, market dollars per month, dollars per contact-month)."""
    rate = row.price / row.service_hours
    market = row.price * row.buyers * row.conversion
    return rate, market, row.price * row.conversion


def verdict_from_facts(rate: float, market: float) -> str:
    """The screen, rewritten without any of its four variables."""
    if rate < BAR:
        return A.DEAD
    if market < MARKET_BAR:
        return A.BURNS
    return A.REACHABLE


def months_to_target(row: Economics) -> float:
    v = A.verdict(row)
    customers_per_month = CONTACTS_PER_MONTH * row.conversion
    return v.accounts_needed / customers_per_month


def section_1_reduction() -> None:
    print("=" * 96)
    print("1. WHAT THE SCREEN IS A FUNCTION OF")
    print("=" * 96)
    print(f"USABLE_HOURS / TARGET_MRR            = {USABLE_HOURS:g} / {TARGET_MRR:,.0f}")
    print(f"  revenue per delivery hour, bar     = ${BAR:.2f}/hr")
    print(f"  price * buyers * conversion, bar   = {money(MARKET_BAR)}/month")
    print()
    print("The three printed tests are one test plus one test.  Proof by identity:")
    print("  need > cap  <=>  TARGET/price > USABLE/hours  <=>  price/hours < BAR")
    print("  contacts/pool > 50%  <=>  TARGET/(price*conv) > buyers/2")
    print("                      <=>  price*buyers*conv < 2*TARGET")
    print()
    print(f"{'venture':28} {'$/hr':>8} {'x bar':>6} {'mkt $/mo':>10} {'x bar':>6} {'screen':>20} {'facts':>20}")
    print("-" * 96)
    for row in ECONOMICS:
        rate, market, _ = facts(row)
        hard = A.verdict(row).hard
        derived = verdict_from_facts(rate, market)
        check(f"reduction:{row.name}", hard == derived, f"{hard} != {derived}")
        print(
            f"{row.name[:28]:28} {rate:>8.0f} {rate / BAR:>6.2f} {market:>10,.0f} "
            f"{market / MARKET_BAR:>6.2f} {hard:>20} {derived:>20}"
        )
    print()
    print("Every row's verdict is reproduced from two products.  The other two")
    print("inputs are not extra information; they are the same information.")
    print()


def section_2_degrees_of_freedom() -> None:
    print("=" * 96)
    print("2. HOW MANY INDEPENDENT NUMBERS THE OUTPUT ACTUALLY CONTAINS")
    print("=" * 96)
    print("The break-even table prints two columns per row.  Both are one constant.")
    for row in ECONOMICS:
        v = A.verdict(row)
        check(f"hours-flip:{row.name}",
              abs(v.flips["service_hours"] / row.price - K) < 1e-12)
        check(f"price-flip:{row.name}",
              abs(v.flips["price"] / row.service_hours - 1.0 / K) < 1e-9)
    print(f"  hours_flip / price  == {K:.6f} for all 14 rows")
    print(f"  price_flip / hours  == {1.0 / K:.4f} for all 14 rows")
    print("  so 'hours now -> flips at' and 'price now -> flips at' are the")
    print("  same number, printed twice with different units.")
    print()

    row = ECONOMICS[4]  # Customs HTS
    moved_buyers = replace(row, buyers=row.buyers // 2)
    moved_conv = replace(row, conversion=row.conversion / 2)
    v, vb, vc = A.verdict(row), A.verdict(moved_buyers), A.verdict(moved_conv)
    check("buyers-flip ignores buyers",
          abs(v.flips["buyers"] - vb.flips["buyers"]) < 1e-9)
    check("conv-flip ignores conversion",
          abs(v.flips["conversion"] - vc.flips["conversion"]) < 1e-12)
    print("  buyers_flip is invariant when buyers change (it depends only on price")
    print("  and conversion); conversion_flip is invariant when conversion changes.")
    print("  A 'flip' that ignores its own input is not a measurement target.")
    print()

    for row in ECONOMICS:
        v = A.verdict(row)
        check(f"margin tie:{row.name}",
              abs(v.margins["buyers"] - v.margins["conversion"]) < 1e-12,
              f"{v.margins['buyers']} vs {v.margins['conversion']}")
    print("  margins['buyers'] == margins['conversion'] on all 14 rows (exact).")
    print("  The field report pretends these are two different measurements.  They")
    print("  are one product.  'nearest input' always resolves the tie to buyers")
    print("  because of the key order in Verdict.closest, not because of evidence.")
    print()

    twin = replace(ECONOMICS[4], price=375.0, service_hours=1.5, buyers=10_400)
    print(f"  {ECONOMICS[4].name}: {A.verdict(ECONOMICS[4]).hard}")
    print(f"  synthetic twin (price/2, hours/2, buyers*2): {A.verdict(twin).hard}")
    check("twin verdict", A.verdict(twin).hard == A.verdict(ECONOMICS[4]).hard)
    print("  Same verdict from three different inputs.  The board is a 2-number")
    print("  test wearing a 4-number costume.")
    print()


def section_3_capacity_cash() -> None:
    print("=" * 96)
    print("3. THE NUMBER THE TOOL NEVER PRINTS: CASH AT ONE-PERSON CAPACITY")
    print("=" * 96)
    print("capacity is printed in accounts.  Multiply by price and it is revenue.")
    print()
    print(f"{'venture':28} {'$/hr':>7} {'accounts':>9} {'ceiling $/mo':>13} "
          f"{'$/contact-mo':>13} {'months to 10k':>14}")
    print("-" * 96)
    ranked = sorted(ECONOMICS, key=lambda r: -(USABLE_HOURS * r.price / r.service_hours))
    for row in ranked:
        rate, market, per_contact = facts(row)
        cap = USABLE_HOURS / row.service_hours
        ceiling = cap * row.price
        check(f"ceiling:{row.name}", abs(ceiling - USABLE_HOURS * rate) < 1e-6)
        print(
            f"{row.name[:28]:28} {rate:>7.0f} {cap:>9.1f} {money(ceiling):>13} "
            f"{money2(per_contact):>13} {months_to_target(row):>14.1f}"
        )
    print()
    print("One person, 173.2 hours, at the stated price and service hours.  This")
    print("is the ceiling the $10k bar is hiding.  The bar is a choice; capacity")
    print("is the business.")
    print()


def section_4_conversion() -> None:
    print("=" * 96)
    print("4. THE INPUT THAT DECIDES EVERYTHING, AND WHAT THE REPO SAYS IT IS")
    print("=" * 96)
    print("13 of 14 rows use one constant: DEFAULT_CONVERSION = "
          f"{DEFAULT_CONVERSION:.3%}.")
    print("The only measured conversion in the repo is in the Customs row note:")
    print("  'verified list 1.1% vs purchased 0.05%'")
    print()
    rates = (0.011, DEFAULT_CONVERSION, 0.001, 0.0005)
    print(f"{'venture':28} " + " ".join(f"{c:>10.3%}" for c in rates))
    print("-" * 76)
    surviving: Dict[float, int] = {c: 0 for c in rates}
    for row in ECONOMICS:
        cells = []
        for c in rates:
            test = replace(row, conversion=c)
            hard = A.verdict(test).hard
            if hard == A.REACHABLE:
                surviving[c] += 1
            cells.append(hard[:10])
        print(f"{row.name[:28]:28} " + " ".join(f"{c:>10}" for c in cells))
    print("-" * 76)
    print(f"{'REACHABLE count':28} " + " ".join(f"{surviving[c]:>10}" for c in rates))
    print()
    check("no row survives a purchased-list conversion",
          surviving[0.0005] == 0, surviving[0.0005])
    print("At the purchased-list rate the repo itself documents, zero of fourteen")
    print("ventures pass.  The board is not a venture analysis.  It is a test of")
    print("whether you own a channel that converts.")
    print()
    print("Minimum viable price, price_min = 2*TARGET / (buyers * conversion):")
    for row in (ECONOMICS[4],):
        for c, label in ((row.conversion, "measured 1.1%"),
                         (DEFAULT_CONVERSION, "default 0.6%"),
                         (0.0005, "purchased 0.05%")):
            floor = MARKET_BAR / (row.buyers * c)
            print(f"  {row.name:28} {label:16} -> {money(floor)}/mo  "
                  f"(now {money(row.price)})")
    print()


def section_5_evidence_weight() -> None:
    print("=" * 96)
    print("5. HOW MUCH OF EACH VERDICT IS INVENTED")
    print("=" * 96)
    print(f"{'venture':28} {'price':>10} {'hours':>10} {'buyers':>10} {'measured':>9}")
    print("-" * 76)
    for row in ECONOMICS:
        measured = sum(
            1 for value in (row.price_provenance, row.hours_provenance,
                            row.buyers_provenance)
            if value not in ("estimate",)
        )
        print(f"{row.name[:28]:28} {row.price_provenance:>10} "
              f"{row.hours_provenance:>10} {row.buyers_provenance:>10} "
              f"{measured:>7}/3")
    print()
    print("conversion is 'published' on 13 rows but is one blended constant, not a")
    print("measurement of that venture.  Only the Customs row carries a measured")
    print("conversion (1.1%, from a verified list) and a counted buyer pool.")
    print("Hours are an estimate on all 14 rows.  The fragility the tool reports is")
    print("therefore the fragility of its own guess, not of a venture.")
    print()


def section_6_robustness(draws: int = 20_000) -> None:
    print("=" * 96)
    print("6. DOES THE VERDICT SURVIVE THE TOOL'S OWN GUESSWORK?")
    print("=" * 96)
    print(f"{draws:,} draws; every 'estimate' input is lognormal, sigma=0.40;")
    print("'published' conversion is lognormal sigma=0.60 on rows using the default.")
    print()
    rng = random.Random(0)
    print(f"{'venture':28} {'base':>20} {'P(reachable)':>13} {'p05 $/hr':>9} {'p95 $/hr':>9}")
    print("-" * 96)
    out: List[Tuple[str, float, str]] = []
    for row in ECONOMICS:
        base = A.verdict(row).hard
        ok = 0
        rates: List[float] = []
        for _ in range(draws):
            price = row.price
            hours = row.service_hours
            buyers = float(row.buyers)
            conv = row.conversion
            if row.price_provenance == "estimate":
                price *= rng.lognormvariate(0.0, 0.40)
            if row.hours_provenance == "estimate":
                hours *= rng.lognormvariate(0.0, 0.40)
            if row.buyers_provenance == "estimate":
                buyers *= rng.lognormvariate(0.0, 0.40)
            if row.conversion_provenance == "published":
                conv *= rng.lognormvariate(0.0, 0.60)
            trial = replace(row, price=price, service_hours=hours,
                            buyers=int(round(buyers)), conversion=conv)
            if A.verdict(trial).hard == A.REACHABLE:
                ok += 1
            rates.append(price / hours)
        rates.sort()
        p05 = rates[int(0.05 * draws)]
        p95 = rates[int(0.95 * draws)]
        share = ok / draws
        out.append((row.name, share, base))
        print(f"{row.name[:28]:28} {base:>20} {share:>12.1%} {p05:>9.0f} {p95:>9.0f}")
    print()
    print("A row that passes only because a number was guessed is a row with a")
    print("probability, not a verdict.  This column is the one the tool omits.")
    print()


def section_7_model() -> None:
    print("=" * 96)
    print("7. THE MODEL LAYER: GOOD NEWS IS DISCARDED, BAD NEWS IS KEPT")
    print("=" * 96)
    row = ECONOMICS[0]  # DOT compliance, hard DEAD
    optimistic = {
        "supply_current": M.Answer("outsourced", 0.99),
        "supply_alternative": M.Answer("retainer", 0.99),
        "supply_switching": M.Answer("integration", 0.99),
    }
    pessimistic = {
        "supply_current": M.Answer("manual", 0.99),
        "supply_alternative": M.Answer("subscription", 0.99),
        "supply_switching": M.Answer("setup", 0.99),
    }
    hard = A.verdict(row).hard
    gated_up, res_up = M.gated_verdict(row, optimistic)
    gated_dn, res_dn = M.gated_verdict(row, pessimistic)
    up_hours = res_up.bands["service_hours"].value
    up_price = res_up.bands["price"].value
    print(f"{row.name}: hard verdict {hard} (price {money(row.price)}, "
          f"{row.service_hours:g} hrs)")
    print(f"  best possible answers -> price {money(up_price)}, {up_hours:.2f} hrs")
    print(f"    arithmetic on moved bands: "
          f"{A.model_verdict(row, res_up.values())}")
    print(f"    after combine(hard, model): {gated_up}")
    print(f"  worst answers -> after combine: {gated_dn}")
    check("optimistic discarded", gated_up == A.DEAD)
    check("pessimistic kept", gated_dn == A.DEAD)
    print()
    print("Every answer set that improves the arithmetic is thrown away by the")
    print("floor.  Every answer set that worsens it is kept.  So the 'model may")
    print("move an input band' layer is a one-way ratchet toward DEAD: it cannot")
    print("change the ranking of a reachable venture upward, and it can only add")
    print("false negatives.  It is a veto with no information in it.")
    print()


def section_8_sample_size() -> None:
    print("=" * 96)
    print("8. THE CALL BUDGET IS A FLOOR MASQUERADING AS A MEASUREMENT PLAN")
    print("=" * 96)
    print("sample_size(margin) = max(8, ceil(0.68 / margin^2)), capped at 200.")
    print("Any margin above 29.2% therefore returns the floor, 8.")
    print()
    floor = math.sqrt(0.68 / 8)
    print(f"  margin at which the floor takes over: {floor:.1%}")
    for margin in (0.134, 0.306, 0.534, 0.711, 1.0):
        print(f"  margin {margin:>6.1%} -> {sample_size(margin):>3} calls")
    print()
    at_floor = [r.name for r in ECONOMICS
                if sample_size(min(A.verdict(r).margins.values())) == 8]
    print(f"  {len(at_floor)} of 14 rows get 8 calls; the budget cannot rank them.")
    check("floor dominates", len(at_floor) == 13, len(at_floor))
    print("The shopping list's information is its ordering, not its call count.")
    print()


def section_9_shortlist() -> None:
    print("=" * 96)
    print("9. WHERE THE DOLLARS ACTUALLY ARE")
    print("=" * 96)
    print("A row is a candidate only if (a) its arithmetic clears both bars, (b) it")
    print("has at least one measured input, and (c) the ceiling pays for the year.")
    print()
    rows: List[Tuple[str, float, float, int, float]] = []
    for row in ECONOMICS:
        rate, market, _ = facts(row)
        measured = sum(1 for v in (row.price_provenance, row.hours_provenance,
                                   row.buyers_provenance) if v != "estimate")
        rows.append((row.name, rate, USABLE_HOURS * rate, measured,
                     months_to_target(row)))
    rows.sort(key=lambda item: (-item[3], -item[2]))
    print(f"{'venture':28} {'$/hr':>7} {'ceiling $/mo':>13} {'measured':>9} "
          f"{'mo -> $10k':>11}")
    print("-" * 78)
    for name, rate, ceiling, measured, months in rows:
        print(f"{name[:28]:28} {rate:>7.0f} {money(ceiling):>13} {measured:>7}/3 "
              f"{months:>11.1f}")
    print()
    print("Only one row has a measured input on more than one axis.  It is also")
    print("the only row whose channel conversion was counted instead of assumed.")
    print()

    row = ECONOMICS[4]
    v = A.verdict(row)
    cap = USABLE_HOURS / row.service_hours
    print(f"{row.name}, the only evidenced row:")
    print(f"  accounts to clear $10k MRR : {v.accounts_needed:.1f}")
    print(f"  one-person account ceiling : {cap:.1f}")
    print(f"  one-person revenue ceiling : {money(cap * row.price)}/month")
    print(f"  contacts to clear $10k      : {v.contacts_needed:,.0f} "
          f"({v.market_share:.0%} of the {row.buyers:,} pool)")
    print(f"  contacts/mo at 60/wk        : {CONTACTS_PER_MONTH}")
    print(f"  months to $10k at that pace : {months_to_target(row):.1f}")
    print(f"  revenue per contact-month   : {money2(row.price * row.conversion)}")
    print(f"  price floor at measured 1.1%: "
          f"{money(MARKET_BAR / (row.buyers * row.conversion))}")
    print(f"  price floor at default 0.6% : "
          f"{money(MARKET_BAR / (row.buyers * DEFAULT_CONVERSION))}")
    print(f"  price floor at purchased    : "
          f"{money(MARKET_BAR / (row.buyers * 0.0005))}")
    print()
    print("Pool-definition sensitivity for that row (the repo never audits it):")
    print(f"  {'pool':>7} {'what it counts':32} {'mkt $/mo @1.1%':>15} "
          f"{'price floor':>12} {'@0.6%':>12}")
    for pool, label in ((16_170, "licensed individuals (CBP)"),
                        (5_200, "repo's 'counted customs brokers'"),
                        (2_500, "brokerage firms (directory)")):
        m11 = row.price * pool * 0.011
        f11 = MARKET_BAR / (pool * 0.011)
        f06 = MARKET_BAR / (pool * DEFAULT_CONVERSION)
        print(f"  {pool:>7,} {label:32} {money(m11):>15} {money(f11):>12} "
              f"{money(f06):>12}")
    print("  CBP reports ~16,170 active licensed brokers; a public broker")
    print("  directory lists ~2,500 firms.  A per-firm subscription sits closer to")
    print("  the firm count, where $750 clears the 1.1% bar by only 3%.")
    print()


def section_10_calibration() -> None:
    print("=" * 96)
    print("10. WHAT THE CALIBRATION ACTUALLY VALIDATED: ONE DIMENSION, THREE TIMES")
    print("=" * 96)
    from vstress.calibrate import auc, stratified_split
    from vstress.data import LABELLED, _FAMILY_PHRASES
    from vstress.questions import ADMITTED

    # Read off vstress/questions.py, in level order.  Every question's score is
    # monotone increasing in the one level its family renders.
    level_scores: Dict[str, Tuple[float, float, float]] = {
        "buyer_role": (0.50, 0.65, 0.80),
        "buyer_list_source": (0.70, 1.00, 1.40),
        "buyer_geography": (0.55, 0.70, 0.80),
        "pain_recurrence": (0.80, 0.90, 1.10),
        "pain_handler": (0.85, 1.00, 1.15),
        "pain_error_caught": (0.90, 1.10, 1.20),
        "supply_current": (0.80, 1.00, 1.30),
        "supply_alternative": (0.90, 1.00, 1.25),
        "supply_switching": (0.95, 1.00, 1.20),
        "workflow_handoff": (0.80, 1.00, 1.25),
        "workflow_system": (0.90, 1.20, 1.30),
        "workflow_rework": (0.80, 1.00, 1.25),
        "access_gatekeeper": (0.80, 0.90, 1.20),
        "access_channel": (0.95, 1.10, 1.20),
        "access_proof": (0.80, 0.90, 1.15),
    }
    for qid, scores in level_scores.items():
        check(f"monotone:{qid}", scores[0] < scores[1] < scores[2], scores)

    def level_of(venture, family: str) -> int:
        found = set()
        for i in range(3):
            block = _FAMILY_PHRASES[family][3 * i:3 * i + 3]
            hits = [j for j, phrase in enumerate(block)
                    if phrase in venture.evidence[family]]
            check(f"one phrase per block:{venture.id}:{family}", len(hits) == 1, hits)
            found.add(hits[0])
        # The fixture picks ONE level per family and renders it three times.
        check(f"one level per family:{venture.id}:{family}", len(found) == 1, found)
        return found.pop()

    disc, hold = stratified_split(LABELLED)
    labels_all = [v.alive for v in LABELLED]
    disc_labels = [v.alive for v in disc]
    hold_labels = [v.alive for v in hold]
    jev = {  # measured above with `python3 run.py calibrate --provider jev`
        "supply": (0.875, 0.897), "pain": (0.667, 0.449),
        "buyer": (0.583, 0.577), "access": (0.556, 0.692),
        "workflow": (0.500, 0.731),
    }
    print(f"{'family':10} {'question':22} {'AUC(disc)':>9} {'AUC(hold)':>9} "
          f"{'jev AUC':>8} {'jev hold':>8}")
    print("-" * 78)
    for family in ("buyer", "pain", "supply", "workflow", "access"):
        family_aucs = []
        for q in ADMITTED:
            if q.family != family:
                continue
            scores_all = [level_scores[q.id][level_of(v, family)] for v in LABELLED]
            by_id = dict(zip((v.id for v in LABELLED), scores_all))
            d = [by_id[v.id] for v in disc]
            h = [by_id[v.id] for v in hold]
            a_d, a_h = auc(d, disc_labels), auc(h, hold_labels)
            family_aucs.append((a_d, a_h))
            print(f"{family:10} {q.id:22} {a_d:>9.3f} {a_h:>9.3f} "
                  f"{jev[family][0]:>8.3f} {jev[family][1]:>8.3f}")
        check(f"identical AUC within {family}",
              len({a for a, _ in family_aucs}) == 1, family_aucs)
    print("-" * 78)
    print("Three questions per family, three identical AUCs per family, by")
    print("construction: all three read the same single level.  The Jev run")
    print("reproduced this exactly (0.875 x3, 0.667 x3, 0.500 x3, 0.583 x3,")
    print("0.556 x3).  So 'three supply questions survive' means one latent")
    print("variable survived and was printed three times, not three independent")
    print("findings.")
    print()
    print("The label rule is 2*supply + workflow + pain >= 5 and buyer + access")
    print(">= 2.  The surviving family is the one the label rule weights double.")
    print("The calibration therefore recovers its own generator, which is the one")
    print("thing it cannot be used to prove.")
    print()
    lv = {f: [level_of(v, f) for v in LABELLED] for f in
          ("buyer", "pain", "supply", "workflow", "access")}
    print(f"  single-factor AUC on the labels: supply {auc(lv['supply'], labels_all):.3f}, "
          f"pain {auc(lv['pain'], labels_all):.3f}, "
          f"workflow {auc(lv['workflow'], labels_all):.3f}, "
          f"buyer {auc(lv['buyer'], labels_all):.3f}, "
          f"access {auc(lv['access'], labels_all):.3f}")
    print("  the fourth option of every question is unrenderable: each question has")
    print("  4 substantive options and each evidence block has only 3 sentences, so")
    print("  one option can never be the right answer in the fixture.")
    print()
    for q in ADMITTED:
        check(f"4 options vs 3 phrases:{q.id}", len(q.substantive) == 4)
    print()


def _summary() -> None:
    print("=" * 96)
    print(f"{len(CHECKS)} assertions passed.")
    print("=" * 96)


def main(argv: List[str]) -> int:
    if "--check" in argv:
        section_1_reduction()
        section_2_degrees_of_freedom()
        section_3_capacity_cash()
        section_4_conversion()
        section_5_evidence_weight()
        section_7_model()
        section_8_sample_size()
        section_9_shortlist()
        section_10_calibration()
        _summary()
        return 0
    section_1_reduction()
    section_2_degrees_of_freedom()
    section_3_capacity_cash()
    section_4_conversion()
    section_5_evidence_weight()
    section_6_robustness()
    section_7_model()
    section_8_sample_size()
    section_9_shortlist()
    section_10_calibration()
    _summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
