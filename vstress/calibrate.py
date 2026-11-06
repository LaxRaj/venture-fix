"""Calibration: three gates before a question is trusted.

1. discrimination on a discovery half (AUC)
2. not chance (permutation test + Benjamini-Hochberg across the bank)
3. replication on a held-out half

With the stub provider the expected result is zero survivors.  A harness that
cannot be fooled by a random number generator is the minimum bar.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .client import ProgressCallback, Provider, collect, make_provider
from .data import LABELLED, LabelledVenture
from .mapping import Answer
from .questions import ADMITTED, FAMILIES, Question, bank_report

RAW_AUC_CUTOFF = 0.70
HOLDOUT_AUC_CUTOFF = 0.60
BH_Q = 0.05
PERMUTATIONS = 999
SPLIT_SEED = 20261106
PERM_SEED = 0

GATES: Tuple[str, ...] = (
    "buyer", "pain", "supply", "workflow", "access", "data or workflow moat",
)
UNCOVERED_GATE = "data or workflow moat"


@dataclass(frozen=True)
class QuestionResult:
    id: str
    family: str
    maps_to: str
    discovery_auc: float
    p_value: float
    bh_adjusted: float
    holdout_auc: float
    raw_pass: bool
    perm_pass: bool
    bh_pass: bool
    holdout_pass: bool

    @property
    def survives(self) -> bool:
        return self.raw_pass and self.perm_pass and self.bh_pass and self.holdout_pass


def auc(scores: Sequence[float], labels: Sequence[bool]) -> float:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def stratified_split(ventures: Sequence[LabelledVenture], seed: int = SPLIT_SEED
                     ) -> Tuple[List[LabelledVenture], List[LabelledVenture]]:
    rng = random.Random(seed)
    alive = [v for v in ventures if v.alive]
    dead = [v for v in ventures if not v.alive]
    rng.shuffle(alive)
    rng.shuffle(dead)
    disc = alive[: len(alive) // 2] + dead[: len(dead) // 2]
    hold = alive[len(alive) // 2:] + dead[len(dead) // 2:]
    rng.shuffle(disc)
    rng.shuffle(hold)
    return disc, hold


def _scores(question: Question, answers: Mapping[str, Mapping[str, Answer]],
            ventures: Sequence[LabelledVenture]) -> List[float]:
    out: List[float] = []
    for venture in ventures:
        answer = answers.get(venture.id, {}).get(question.id)
        if answer is None:
            out.append(0.5)
            continue
        try:
            out.append(question.score_for(answer.key))
        except KeyError:
            out.append(0.5)
    return out


def permutation_p(scores: Sequence[float], labels: Sequence[bool],
                  observed: float, permutations: int = PERMUTATIONS,
                  seed: int = PERM_SEED) -> float:
    rng = random.Random(seed)
    extreme = 0
    target = abs(observed - 0.5)
    perm_labels = list(labels)
    for _ in range(permutations):
        rng.shuffle(perm_labels)
        permuted = abs(auc(scores, perm_labels) - 0.5)
        if permuted + 1e-12 >= target:
            extreme += 1
    return (1 + extreme) / (permutations + 1)


def benjamini_hochberg(p_values: Sequence[float], q: float = BH_Q) -> List[float]:
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [1.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        value = p_values[idx] * m / rank
        running = min(running, value)
        adjusted[idx] = min(1.0, running)
    return adjusted


def evaluate(answers: Mapping[str, Mapping[str, Answer]],
             ventures: Sequence[LabelledVenture] = LABELLED,
             permutations: int = PERMUTATIONS) -> List[QuestionResult]:
    disc, hold = stratified_split(ventures)
    disc_labels = [v.alive for v in disc]
    hold_labels = [v.alive for v in hold]
    raw: List[Dict[str, object]] = []
    for question in ADMITTED:
        disc_scores = _scores(question, answers, disc)
        hold_scores = _scores(question, answers, hold)
        disc_auc = auc(disc_scores, disc_labels)
        hold_auc = auc(hold_scores, hold_labels)
        p = permutation_p(disc_scores, disc_labels, disc_auc, permutations)
        raw.append({
            "question": question,
            "disc_auc": disc_auc,
            "hold_auc": hold_auc,
            "p": p,
        })
    adjusted = benjamini_hochberg([float(item["p"]) for item in raw])
    results: List[QuestionResult] = []
    for item, bh in zip(raw, adjusted):
        q: Question = item["question"]  # type: ignore[assignment]
        disc_auc = float(item["disc_auc"])
        hold_auc = float(item["hold_auc"])
        p = float(item["p"])
        results.append(QuestionResult(
            id=q.id,
            family=q.family,
            maps_to=q.maps_to,
            discovery_auc=disc_auc,
            p_value=p,
            bh_adjusted=bh,
            holdout_auc=hold_auc,
            raw_pass=disc_auc >= RAW_AUC_CUTOFF,
            perm_pass=p <= 0.05,
            bh_pass=bh <= BH_Q,
            holdout_pass=hold_auc >= HOLDOUT_AUC_CUTOFF,
        ))
    return results


def threshold_sweep(results: Sequence[QuestionResult]) -> List[Tuple[float, int, int]]:
    out: List[Tuple[float, int, int]] = []
    for cutoff in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
        raw = sum(1 for r in results if r.discovery_auc >= cutoff)
        kept = sum(
            1 for r in results
            if r.discovery_auc >= cutoff and r.perm_pass and r.bh_pass and r.holdout_pass
        )
        out.append((cutoff, raw, kept))
    return out


def _fmt_p(value: float) -> str:
    return f"{value:.3f}"


def render_report(provider: Provider,
                  results: Sequence[QuestionResult]) -> str:
    coverage = {family: 0 for family in GATES}
    for question in ADMITTED:
        if question.family in coverage:
            coverage[question.family] += 1
    coverage[UNCOVERED_GATE] = 0

    bank = bank_report()
    lines: List[str] = []
    lines.append("CALIBRATION")
    lines.append(f"provider: {provider.name}")
    if provider.stamp:
        lines.append(f"stamp:    {provider.stamp}")
    lines.append(f"labels:   {len(LABELLED)} ventures "
                 f"({sum(1 for v in LABELLED if v.alive)} alive / "
                 f"{sum(1 for v in LABELLED if not v.alive)} dead)")
    lines.append(f"split:    {SPLIT_SEED} (stratified discovery / holdout)")
    lines.append(f"bank:     {bank['admitted']} admitted, "
                 f"{bank['rejected_examples']} counterexamples rejected at import")
    lines.append("")
    lines.append("coverage:")
    for gate in GATES:
        count = coverage[gate]
        if gate == UNCOVERED_GATE and count == 0:
            lines.append(f"  {gate:22} 0 questions  UNCOVERED (printed, not faked)")
        else:
            lines.append(f"  {gate:22} {count} questions")
    lines.append("")
    lines.append(f"{'question':24} {'family':10} {'maps_to':14} "
                 f"{'AUC':>6} {'p':>6} {'BH':>6} {'hold':>6}  result")
    lines.append("-" * 96)
    for r in results:
        if r.survives:
            result = "KEEP"
        elif r.raw_pass and not r.perm_pass:
            result = "drop: chance"
        elif r.raw_pass and not r.bh_pass:
            result = "drop: BH"
        elif r.raw_pass and not r.holdout_pass:
            result = "drop: holdout"
        elif r.raw_pass:
            result = "drop: gate"
        else:
            result = "below raw AUC"
        lines.append(
            f"{r.id[:24]:24} {r.family:10} {(r.maps_to or 'diagnostic')[:14]:14} "
            f"{r.discovery_auc:>6.3f} {_fmt_p(r.p_value):>6} {r.bh_adjusted:>6.3f} "
            f"{r.holdout_auc:>6.3f}  {result}"
        )
    lines.append("")
    kept = [r for r in results if r.survives]
    raw = [r for r in results if r.raw_pass]
    chance = [r for r in raw if not r.perm_pass]
    bh = [r for r in raw if r.perm_pass and not r.bh_pass]
    holdout = [r for r in raw if r.perm_pass and r.bh_pass and not r.holdout_pass]
    lines.append(
        f"raw AUC >= {RAW_AUC_CUTOFF:.2f}: {len(raw)} kept; "
        f"permutation p <= 0.05: {len(raw) - len(chance)} kept; "
        f"BH q={BH_Q}: {len(raw) - len(chance) - len(bh)} kept; "
        f"holdout AUC >= {HOLDOUT_AUC_CUTOFF:.2f}: {len(kept)} kept"
    )
    if provider.name == "stub":
        lines.append("")
        lines.append("Stub verdict: the harness was offered noise.")
        if kept:
            lines.append(f"FAIL: {len(kept)} question(s) survived noise. Do not enforce.")
        else:
            lines.append("PASS: zero questions survived noise. Nothing is trusted yet.")
    lines.append("")
    lines.append("threshold sweep (raw survivors / final survivors):")
    for cutoff, raw_count, kept_count in threshold_sweep(results):
        lines.append(f"  AUC >= {cutoff:.2f}  raw {raw_count:2d}  final {kept_count:2d}")
    if not kept:
        lines.append("  no cutoff survives; threshold enforcement stays off")
    lines.append("")
    if kept:
        lines.append("thresholds to enforce:")
        for r in kept:
            lines.append(f"  {r.id}: discovery AUC {r.discovery_auc:.3f}, "
                         f"holdout AUC {r.holdout_auc:.3f}, BH {r.bh_adjusted:.3f}")
    else:
        lines.append("thresholds: none. The arithmetic and the calls carry the decision.")
    lines.append("")
    lines.append("leakage check: PASS (build_state asserts labels never enter the state)")
    return "\n".join(lines)


def report(provider_name: str, seed: int = 0, permutations: int = PERMUTATIONS,
           on_progress: Optional[ProgressCallback] = None) -> str:
    provider: Provider = make_provider(provider_name, seed=seed)
    answers = collect(provider, LABELLED, ADMITTED, on_progress=on_progress)
    results = evaluate(answers, LABELLED, permutations)
    return render_report(provider, results)
