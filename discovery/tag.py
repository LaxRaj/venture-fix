"""Tag candidates with Jev's typed answers.  Diagnostics only: tags never change a verdict.

Uses: group candidates by buyer/access answers (channel overlap) and measure how
much evidence a candidate has (share of 'escape' answers).
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Dict, List

from vstress.client import make_provider
from vstress.data import LabelledVenture, STATE_FIELDS, build_state
from vstress.questions import ADMITTED

from . import questions_v2 as Q2

MIN_EVIDENCE_FIELDS = 3


def to_venture(c: dict) -> LabelledVenture:
    # alive/kill_reason are required by the dataclass but build_state() never exposes them.
    return LabelledVenture(id=c["id"], name=c["offer"], sector=c.get("sector", ""),
                           alive=False, kill_reason="", evidence=dict(c["evidence"]))


def tag_all(unique: List[dict], provider_name: str, seed: int = 91, log=print) -> Dict[str, dict]:
    provider = make_provider("stub" if provider_name == "stub" else "jev", seed=seed)
    out: Dict[str, dict] = {}
    for i, c in enumerate(unique, 1):
        filled = sum(1 for k in STATE_FIELDS if c["evidence"].get(k))
        if filled < MIN_EVIDENCE_FIELDS:
            out[c["id"]] = {"status": "insufficient_evidence", "filled_fields": filled}
            continue
        try:
            answers = provider.ask(build_state(to_venture(c)), ADMITTED)
        except RuntimeError as exc:
            out[c["id"]] = {"status": "error", "error": str(exc)[:200]}
            log(f"tag error on {c['id']}: {exc}")
            continue
        esc = sum(1 for a in answers.values() if a.key == "escape")
        out[c["id"]] = {
            "status": "ok", "answers": {q: [a.key, round(a.confidence, 3)] for q, a in answers.items()},
            "escape_rate": round(esc / len(answers), 3),
        }
        if i % 25 == 0:
            log(f"tagged {i}/{len(unique)}")
    return out


# ---------------------------------------------------------------------------
# Bank v2: decision-focused questions, two runs with shuffled option order.
# ---------------------------------------------------------------------------

def _shuffled(questions, seed: int):
    """Copies of the questions with option order shuffled.  JevProvider lists options in the order given, so
    shuffling here is what makes a second run a real test of whether an answer depends on option order."""
    rng = random.Random(seed)
    out = []
    for q in questions:
        opts = list(q.options)
        rng.shuffle(opts)
        out.append(replace(q, options=tuple(opts)))
    return out


def tag_v2(rows: List[dict], provider_name: str, runs: int = 2, seed: int = 91, log=print) -> Dict[str, dict]:
    """Per candidate: the answers from each run, and a 'final' answer that is the shared answer only if every
    run agreed; otherwise 'unstable'.  An escape answer stays 'escape'."""
    out: Dict[str, dict] = {}
    for i, c in enumerate(rows, 1):
        state = Q2.build_state_v2(c)
        qs = Q2.applicable(state)
        if not qs:
            out[c["id"]] = {"status": "no_input"}
            continue
        answers: List[Dict[str, list]] = []
        try:
            for run in range(runs):
                provider = make_provider("stub" if provider_name == "stub" else "jev", seed=seed + run)
                got = provider.ask(state, _shuffled(qs, seed * 1000 + run * 17 + i))
                answers.append({q: [a.key, round(a.confidence, 3)] for q, a in got.items()})
        except RuntimeError as exc:
            out[c["id"]] = {"status": "error", "error": str(exc)[:200]}
            log(f"tag error on {c['id']}: {exc}")
            continue
        final, stable = {}, {}
        for q in qs:
            keys = [a[q.id][0] for a in answers if q.id in a]
            same = len(keys) == runs and len(set(keys)) == 1
            stable[q.id] = same
            final[q.id] = keys[0] if same else "unstable"
        out[c["id"]] = {"status": "ok", "runs": answers, "final": final, "stable": stable}
        if i % 10 == 0:
            log(f"tagged {i}/{len(rows)}")
    return out
