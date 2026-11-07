"""Quality check for the Jev question bank: offline coverage, then agreement with a hand-labelled gold set.

A question earns the right to remove candidates only if, on the gold set, it is answered (low escape rate),
stable across shuffled option order, and agrees with the gold labels.  The gold labels are a reviewer's
judgment from the cached text, not ground truth: they are there for the user to read and correct.
"""

from __future__ import annotations

import json
import os
import random
import re
from typing import Dict, List, Optional

from . import questions_v2 as Q2
from .ground import key

THRESHOLDS = {"escape_max": 0.40, "stability_min": 0.90, "gold_min": 0.80}
HERE = os.path.dirname(os.path.abspath(__file__))
GOLD_PATH = os.path.join(HERE, "gold_tags.json")
_STOP = {"for", "and", "the", "of", "or", "to", "in", "on", "is", "it", "by", "who", "what", "which", "with", "from",
         "that", "this", "must", "up", "does", "work", "business", "buyer", "their", "they", "are"}


def _stems(label: str) -> set:
    return {w[:5] for w in re.findall(r"[a-z]+", label.lower()) if w not in _STOP and len(w) > 2}


def coverage(rows: List[dict]) -> List[dict]:
    """Offline proxy: of the candidates whose source field is non-empty, how often does that text mention any
    option's vocabulary?  A low figure predicts mostly-escape answers.  It is a keyword check, not a Jev result."""
    out = []
    for q in Q2.ADMITTED_V2:
        n = hit = 0
        for r in rows:
            text = Q2.build_state_v2(r).get(q.source, "")
            if not text:
                continue
            n += 1
            toks = {w[:5] for w in re.findall(r"[a-z]+", text.lower())}
            if any(_stems(o.label) & toks for o in q.substantive):
                hit += 1
        out.append({"question": q.id, "source": q.source, "candidates": n, "mentions_option": round(hit / n, 3) if n else None})
    return out


def select_gold(rows: List[dict], n: int = 40, seed: int = 7) -> List[dict]:
    """Deterministic stratified sample: half with a cited price quote (so price questions apply), half without."""
    rng = random.Random(seed)
    withq = sorted((r for r in rows if r.get("evidence_quote")), key=lambda r: key(r))
    without = sorted((r for r in rows if not r.get("evidence_quote")), key=lambda r: key(r))
    rng.shuffle(withq); rng.shuffle(without)
    return withq[: n // 2] + without[: n - min(n // 2, len(withq))]


def load_gold(path: str = GOLD_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def gold_items(doc: dict, rows: List[dict]) -> List[tuple]:
    """(row, labels) pairs: the hand-labelled candidates found in rows, plus the synthetic probe quotes."""
    by_key = {key(r): r for r in rows}
    items = [(by_key[k], g["labels"]) for k, g in doc["labels"].items() if k in by_key]
    for p in doc.get("probes", []):
        items.append(({"id": p["id"], "offer": "", "task": "", "blockers": "", "channel": "", "evidence_quote": p["quote"]},
                      p["labels"]))
    return items


def score(items: List[tuple], tags: Dict[str, dict]) -> Dict[str, dict]:
    """Per question: gold agreement, escape rate, stability, agreement with Groq's price kind, and keep/cut.
    Also reports recall on the classes that trigger removal, since removal is the decision at stake."""
    res: Dict[str, dict] = {}
    for q in Q2.ADMITTED_V2:
        esc_runs = runs_total = stab = tagged = agree = labelled = groq_n = groq_ok = 0
        for r, labels in items:
            t = tags.get(r["id"])
            if not t or t.get("status") != "ok" or q.id not in t["final"]:
                continue
            tagged += 1
            stab += 1 if t["stable"][q.id] else 0
            for run in t["runs"]:
                runs_total += 1
                esc_runs += 1 if run[q.id][0] == "escape" else 0
            want = labels.get(q.id)
            if want:
                labelled += 1
                agree += 1 if t["final"][q.id] == want else 0
            if q.id == "price_kind" and r.get("price_kind") in Q2.GROQ_PRICE_KIND:
                groq_n += 1
                groq_ok += 1 if t["final"][q.id] == Q2.GROQ_PRICE_KIND[r["price_kind"]] else 0
        row = {"tagged": tagged, "labelled": labelled,
               "escape_rate": round(esc_runs / runs_total, 3) if runs_total else None,
               "stability": round(stab / tagged, 3) if tagged else None,
               "gold_agreement": round(agree / labelled, 3) if labelled else None,
               "groq_agreement": round(groq_ok / groq_n, 3) if groq_n else None, "groq_compared": groq_n}
        demote = {"price_kind": {"internal", "ads"}, "audience": {"large"}}.get(q.id)
        if demote:  # of the items whose gold label is a demoting class, how many did Jev get right?
            bad = [(r, l) for r, l in items if l.get(q.id) in demote and (tags.get(r["id"]) or {}).get("status") == "ok"]
            hit = sum(1 for r, l in bad if tags[r["id"]]["final"].get(q.id) == l[q.id])
            row["demoting_gold"] = len(bad)
            row["demoting_recall"] = round(hit / len(bad), 3) if bad else None
            fine = [(r, l) for r, l in items if l.get(q.id) not in demote and l.get(q.id) and (tags.get(r["id"]) or {}).get("status") == "ok"]
            row["wrongly_demoted"] = sum(1 for r, l in fine if tags[r["id"]]["final"].get(q.id) in demote)
        why = []
        if row["escape_rate"] is None or row["escape_rate"] > THRESHOLDS["escape_max"]:
            why.append(f"escape rate {row['escape_rate']} above {THRESHOLDS['escape_max']}")
        if row["stability"] is None or row["stability"] < THRESHOLDS["stability_min"]:
            why.append(f"stability {row['stability']} below {THRESHOLDS['stability_min']}")
        if row["gold_agreement"] is None or row["gold_agreement"] < THRESHOLDS["gold_min"]:
            why.append(f"gold agreement {row['gold_agreement']} below {THRESHOLDS['gold_min']}")
        if demote and row.get("wrongly_demoted"):
            why.append(f"would wrongly demote {row['wrongly_demoted']} labelled-fine items")
        if demote and (row.get("demoting_gold", 0) < 3):
            why.append("too few demoting-class examples to validate removal")
        row["keep"], row["why_cut"] = not why, why
        res[q.id] = row
    return res


def trusted(report: Optional[dict]) -> set:
    """Question ids that passed the quality check.  No report means nothing is trusted, so Jev removes nothing."""
    return {q for q, v in (report or {}).get("questions", {}).items() if v.get("keep")}
