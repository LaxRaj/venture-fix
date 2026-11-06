"""Arithmetic and floor-rule tests.  Run with: python3 -I test_arithmetic.py"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vstress import arithmetic as A
from vstress import data as D
from vstress import mapping as M
from vstress import questions as Q
from vstress.fieldtest import sample_size


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def test_division() -> None:
    assert close(A.accounts_needed(10_000, 150), 66.66666666666667)
    assert close(A.capacity(3.0), 173.2 / 3.0)
    assert close(A.contacts_needed(10, 0.5), 20.0)
    try:
        A.accounts_needed(10_000, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero price must fail")


def test_break_even_table() -> None:
    expected = {
        "DOT compliance": ("3 -> 2.60", "$150 -> $173"),
        "Prior-auth appeals": ("8.5 -> 20.78", "$1,200 -> $490"),
        "Veterinary claims": ("4.5 -> 10.39", "$600 -> $259"),
        "Insurance subrogation": ("15 -> 60.62", "$3,500 -> $866"),
    }
    got = {name: (hours, price) for name, hours, price in A.break_even_table()}
    for name, pair in expected.items():
        assert got[name] == pair, (name, got[name], pair)


def test_verdicts() -> None:
    by_name = {v.name: v for v in A.board()}
    assert by_name["DOT compliance"].hard == A.DEAD
    assert by_name["Prior-auth appeals"].hard == A.REACHABLE
    assert by_name["Veterinary claims"].hard == A.REACHABLE
    assert by_name["Insurance subrogation"].hard == A.REACHABLE
    assert by_name["RFP response drafting"].hard == A.BURNS
    assert by_name["Environmental permit monitoring"].hard == A.BURNS


def test_combine_floor() -> None:
    assert A.combine("DEAD ON ARITHMETIC", "REACHABLE") == "DEAD ON ARITHMETIC"
    assert A.combine("REACHABLE", "BURNS THE MARKET") == "BURNS THE MARKET"
    assert A.combine("REACHABLE", "garbage-from-timeout") == "REACHABLE"
    assert A.combine("BURNS THE MARKET", "REACHABLE") == "BURNS THE MARKET"
    assert A.combine("DEAD ON ARITHMETIC", "garbage") == "DEAD ON ARITHMETIC"
    try:
        A.combine("garbage", "REACHABLE")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown hard verdict must raise")


def test_dot_is_fragile() -> None:
    v = A.verdict(D.ECONOMICS_BY_NAME["DOT compliance"])
    key, margin = v.closest
    assert key in {"service_hours", "price"}
    assert 0.12 < margin < 0.14, margin
    assert sample_size(margin) == 38, sample_size(margin)


def test_floors() -> None:
    row = D.ECONOMICS_BY_NAME["DOT compliance"]
    answers = {
        "supply_current": M.Answer("manual", 0.99),
        "supply_alternative": M.Answer("subscription", 0.99),
        "supply_switching": M.Answer("setup", 0.99),
    }
    result = M.apply_answers(row, answers)
    band = result.bands["price"]
    assert band.value >= M.FLOORS["price"]
    assert band.low >= M.FLOORS["price"]
    assert band.high >= band.low
    # three low multipliers cannot push price below the floor
    assert band.value < row.price


def test_confidence_gate_changes_nothing() -> None:
    row = D.ECONOMICS_BY_NAME["DOT compliance"]
    answers = {"supply_current": M.Answer("outsourced", 0.10)}
    result = M.apply_answers(row, answers)
    assert result.bands["price"].value == row.price
    assert "supply_current" in result.queued
    assert not result.applied


def test_diagnostic_changes_nothing() -> None:
    row = D.ECONOMICS_BY_NAME["DOT compliance"]
    result = M.apply_answers(row, {"buyer_role": M.Answer("owner", 0.99)})
    assert result.bands["price"].value == row.price
    assert "buyer_role" in result.diagnostics


def test_gated_verdict_cannot_revive() -> None:
    row = D.ECONOMICS_BY_NAME["DOT compliance"]
    revive_attempt = {
        "supply_current": M.Answer("outsourced", 0.99),
        "supply_alternative": M.Answer("retainer", 0.99),
        "supply_switching": M.Answer("integration", 0.99),
    }
    hard = A.verdict(row).hard
    gated, result = M.gated_verdict(row, revive_attempt)
    assert hard == A.DEAD
    assert result.bands["price"].value > row.price
    assert gated == A.DEAD


def test_buyer_count_mapping_applies() -> None:
    row = D.ECONOMICS_BY_NAME["DOT compliance"]
    result = M.apply_answers(
        row, {"buyer_list_source": M.Answer("registry", 0.99)}
    )
    assert result.bands["buyers"].value > row.buyers
    assert "buyer_list_source" in result.applied


def test_leakage_blocked() -> None:
    venture = D.LABELLED[0]
    state = D.build_state(venture)
    assert "alive" not in state and "kill_reason" not in state
    assert set(D.STATE_FIELDS).issubset(state)


def test_calibration_fixture_is_varied() -> None:
    assert len(D.LABELLED) == 43
    alive = sum(1 for v in D.LABELLED if v.alive)
    assert 10 <= alive <= 30, alive
    profiles = {
        tuple(v.evidence[field] for field in D.STATE_FIELDS)
        for v in D.LABELLED
    }
    assert len(profiles) >= 30, len(profiles)
    for v in D.LABELLED:
        assert (v.kill_reason == "") == v.alive, v.id


def test_question_bank() -> None:
    assert len(Q.ADMITTED) == 15
    assert len(Q.REJECTED_EXAMPLES) == 6
    counts = {}
    for q in Q.ADMITTED:
        counts[q.family] = counts.get(q.family, 0) + 1
    assert counts == {"buyer": 3, "pain": 3, "supply": 3, "workflow": 3, "access": 3}
    for expected, bad in Q.REJECTED_EXAMPLES:
        assert expected in Q.admission_failures(bad), (expected, Q.admission_failures(bad))


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
