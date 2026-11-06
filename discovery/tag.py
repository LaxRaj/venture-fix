"""Tag candidates with Jev's typed answers.  Diagnostics only: tags never change a verdict.

Uses: group candidates by buyer/access answers (channel overlap) and measure how
much evidence a candidate has (share of 'escape' answers).
"""

from __future__ import annotations

from typing import Dict, List

from vstress.client import make_provider
from vstress.data import LabelledVenture, STATE_FIELDS, build_state
from vstress.questions import ADMITTED

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
