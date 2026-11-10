"""The make-or-break test: nine typed questions, answered by Jev from raw search evidence.

Each question targets one way a venture dies (nobody asks for it, a free or AI substitute, a price race,
a licence wall, one-off billing, delivery that needs a team, buyers you cannot reach, a trust barrier).
Evidence is raw search titles and snippets, gathered per question: no language model summarises it first.

Rigour, in three layers:
  1. Every venture is asked three times with option order shuffled.  Any disagreement is "unstable".
  2. Probes: crafted texts with a known answer.  A question Jev gets wrong on probes is untrusted.
  3. Null control: irrelevant text in every field.  A question Jev answers substantively from a recipe is
     untrusted, because it is answering from the venture name, not the evidence.
An untrusted question is shown but can neither kill nor save a venture.

Verdicts: KILLED (a trusted, stable answer that breaks it), STANDS (no kill, and both critical questions,
buyer demand and buyer reach, passed), WOUNDED (no kill, but a critical question is unproven).
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import replace
from typing import Callable, Dict, List, Optional, Tuple

from vstress.client import make_provider
from vstress.questions import (
    ESCAPE_KEY, Option, Question, _ARITHMETIC, _DATES, _INFERENCE, _NEGATION, _UNBOUNDED, _escape, _opt,
)

from .extract import query_for
from .search import SearchBudget

VERSION = 1
RUNS = 3
SOURCES = ("demand_text", "substitute_text", "competition_text", "compliance_text", "pricing_text", "access_text")
CRITICAL = ("demand_signal", "reach")
PASS, WARN, KILL, UNPROVEN = "PASS", "WARN", "KILL", "UNPROVEN"
PER_FIELD = 5          # search results kept per query

# (question, verdict for each option key).  The option score is unused here; the verdict map decides.
_BANK: Tuple[Tuple[Question, Dict[str, str]], ...] = (
    (Question("demand_signal", "pain", "What are buyers doing about this service in the demand text?", "demand_text", "", (
        _opt("hiring", "Posting requests to hire someone for it", 1.0),
        _opt("asking", "Asking peers how to get it done", 1.0),
        _opt("selfserve", "Sharing ways to do it themselves", 0.5),
        _opt("vendors", "Vendors are the ones talking about it", 0.0),
        _escape())),
     {"hiring": PASS, "asking": PASS, "selfserve": WARN, "vendors": UNPROVEN}),
    (Question("substitute", "supply", "What covers this work for these buyers in the substitute text?", "substitute_text", "", (
        _opt("freetool", "A free tool or template", 0.0),
        _opt("software", "Paid software the buyer runs", 0.5),
        _opt("human", "A person or agency doing the work", 1.0),
        _escape())),
     {"freetool": KILL, "software": WARN, "human": PASS}),
    (Question("ai_pressure", "supply", "What role do AI tools play for this work in the substitute text?", "substitute_text", "", (
        _opt("replace", "AI tools do the whole job", 0.0),
        _opt("assist", "AI tools help a person do it", 1.0),
        _escape())),
     {"replace": KILL, "assist": PASS}),
    (Question("competition", "supply", "Which description fits the sellers in the competition text?", "competition_text", "", (
        _opt("giants", "Large established firms", 0.5),
        _opt("crowd", "A crowd of low-price freelancers", 0.0),
        _opt("specialists", "A small group of specialist vendors", 1.0),
        _escape())),
     {"giants": WARN, "crowd": KILL, "specialists": PASS}),
    (Question("delivery", "workflow", "Who does the work in the competition text?", "competition_text", "", (
        _opt("solo", "An independent specialist", 1.0),
        _opt("team", "A small team", 1.0),
        _opt("agency", "A large agency with specialist roles", 0.5),
        _opt("software", "Software with little human work", 0.5),
        _escape())),
     {"solo": PASS, "team": PASS, "agency": WARN, "software": WARN}),
    (Question("regulation", "workflow", "What does the compliance text require for doing this work?", "compliance_text", "", (
        _opt("licence", "A professional licence held by the seller", 0.0),
        _opt("certificate", "A certification or registration", 0.5),
        _opt("contract", "Ordinary business rules and a contract", 1.0),
        _escape())),
     {"licence": KILL, "certificate": WARN, "contract": PASS}),
    (Question("billing", "workflow", "How do vendors charge for this service in the pricing text?", "pricing_text", "price", (
        _opt("retainer", "A recurring retainer or subscription", 1.0),
        _opt("project", "A fee for a single project", 0.5),
        _opt("hourly", "An hourly fee", 0.5),
        _opt("share", "A share of results", 0.5),
        _escape())),
     {"retainer": PASS, "project": WARN, "hourly": WARN, "share": WARN}),
    (Question("reach", "access", "Where do these buyers gather in the access text?", "access_text", "buyer_count", (
        _opt("association", "A trade association or professional body", 1.0),
        _opt("community", "An online community or forum", 1.0),
        _opt("marketplace", "A marketplace or directory listing", 1.0),
        _opt("scattered", "Scattered across the open web", 0.0),
        _escape())),
     {"association": PASS, "community": PASS, "marketplace": PASS, "scattered": WARN}),
    (Question("trust_barrier", "buyer", "What do buyers ask to see from a seller in the demand text?", "demand_text", "", (
        _opt("portfolio", "Past work or case studies", 0.5),
        _opt("credential", "A licence or credential", 0.0),
        _opt("referral", "A referral from a peer", 0.5),
        _opt("sample", "A free sample or trial", 1.0),
        _opt("cheap", "A low price", 0.5),
        _escape())),
     {"portfolio": WARN, "credential": KILL, "referral": WARN, "sample": PASS, "cheap": WARN}),
)


def admission_failures(q: Question) -> List[str]:
    """T1 single hop, T2 no arithmetic, T3 no dates, T4 enumerable: the jev-1.13 weakness list (vstress/questions.py)."""
    f: List[str] = []
    labels = [o.label for o in q.substantive]
    if _NEGATION.search(q.text) or _INFERENCE.search(q.text) or any(_NEGATION.search(l) or _INFERENCE.search(l) for l in labels):
        f.append("T1")
    if _ARITHMETIC.search(q.text) or any(_ARITHMETIC.search(l) for l in labels):
        f.append("T2")
    if _DATES.search(q.text) or any(_DATES.search(l) for l in labels):
        f.append("T3")
    keys = [o.key for o in q.options]
    if not (q.source in SOURCES and sum(1 for o in q.options if o.escape) == 1 and len(q.substantive) >= 2
            and len(keys) == len(set(keys)) and len({o.label for o in q.options}) == len(q.options)
            and not any(_UNBOUNDED.search(l) for l in labels)):
        f.append("T4")
    return f


def _admit():
    bad = [f"{q.id}: {', '.join(admission_failures(q))}" for q, _ in _BANK if admission_failures(q)]
    missing = [q.id for q, v in _BANK if set(v) != {o.key for o in q.substantive}]
    if bad or missing:
        raise ImportError("make-or-break bank failed admission: " + "; ".join(bad + [f"{m}: verdict map incomplete" for m in missing]))
    return tuple(q for q, _ in _BANK), {q.id: v for q, v in _BANK}


QUESTIONS, VERDICTS = _admit()
BY_ID = {q.id: q for q in QUESTIONS}


# ---------------------------------------------------------------------------
# Evidence: raw search results, per field.  No model reads them before Jev does.
# ---------------------------------------------------------------------------

def queries(v: dict) -> Dict[str, List[str]]:
    o, b = v["offer"], v["buyer"]
    return {
        "demand_text": [f"{b} looking to hire {o} reddit", f"{o} for {b} upwork job"],
        "substitute_text": [f"how do {b} handle {o} themselves", f"{o} AI tool for {b}"],
        "competition_text": [f"{o} agency for {b}", f"{o} freelancer for {b} fiverr"],
        "compliance_text": [f"{o} for {b} license requirements regulations"],
        "pricing_text": [query_for(o, b), f"{o} for {b} agency rates"],     # the prove stage already paid for these
        "access_text": [f"{b} association community forum"],
    }


def gather(v: dict, search) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Evidence text and source URLs per field.  Raises SearchBudget when the cap is hit (rerun resumes from cache)."""
    text, urls = {}, {}
    for field, qs in queries(v).items():
        lines, seen = [], []
        for q in qs:
            for r in search.search(q)[:PER_FIELD]:
                if r["url"] in seen:
                    continue
                seen.append(r["url"])
                lines.append(f"{r['title']} | {r['snippet']} ({r['url']})")
        text[field], urls[field] = "\n".join(lines), seen
    return text, urls


def state_for(vid: str, name: str, fields: Dict[str, str]) -> Dict[str, str]:
    s = {k: v for k, v in fields.items() if v}
    s.update(id=vid, name=name)
    return s


# ---------------------------------------------------------------------------
# Asking Jev: shuffled runs, probes, null control.
# ---------------------------------------------------------------------------

def _shuffled(seed: int) -> List[Question]:
    rng = random.Random(seed)
    out = []
    for q in QUESTIONS:
        opts = list(q.options)
        rng.shuffle(opts)
        out.append(replace(q, options=tuple(opts)))
    return out


def ask_runs(provider_name: str, state: Dict[str, str], runs: int = RUNS, seed: int = 0) -> Dict[str, object]:
    """Ask every applicable question `runs` times with shuffled options.  final = the shared answer, else 'unstable'."""
    qs_ids = {q.id for q in QUESTIONS if state.get(q.source)}
    answers = []
    for i in range(runs):
        provider = make_provider("stub" if provider_name == "stub" else "jev", seed=seed + i)
        qs = [q for q in _shuffled(seed * 101 + i * 17) if q.id in qs_ids]
        got = provider.ask(state, qs)
        answers.append({q: [a.key, round(a.confidence, 3)] for q, a in got.items()})
    final = {}
    for q in sorted(qs_ids):
        keys = [a[q][0] for a in answers if q in a]
        final[q] = keys[0] if len(keys) == runs and len(set(keys)) == 1 else "unstable"
    return {"runs": answers, "final": final}


# A weather report: it describes nobody buying, selling, doing, gathering or paying.  (A recipe was used first and was
# a bad control: a recipe IS someone sharing how to do a job themselves, so 'selfserve' was a fair reading of it.)
NULL_TEXT = ("Weather report: skies stay cloudy over the coast with light rain in the morning, clearing to sun by "
             "late afternoon. Winds are calm and temperatures are mild along the river valley.")
NULL_TAG = "wx"        # part of the null cache file name, so changing the control text never reuses old answers

# Crafted evidence with a known answer.  Only unambiguous (field, question) pairs are scored.
PROBES: Tuple[Tuple[Dict[str, str], Dict[str, str]], ...] = (
    ({"demand_text": "Owner here: we are looking to hire someone to do this for our firm. Budget is ready, please DM me your rates.",
      "substitute_text": "Most shops just download a free template from the web and fill it in themselves.",
      "competition_text": "Hundreds of freelancers on Fiverr offer this at rock-bottom prices of a few dollars.",
      "compliance_text": "Anyone may do this work. It needs ordinary business rules and a signed contract with the client, and no licence.",
      "pricing_text": "Vendors bill this as a recurring retainer or subscription that renews automatically.",
      "access_text": "Nearly all of these firms are members of the state trade association, which runs the industry's main conference."},
     {"demand_signal": "hiring", "substitute": "freetool", "competition": "crowd", "regulation": "contract",
      "billing": "retainer", "reach": "association"}),
    ({"demand_text": "Thread: how I do this myself now. Sharing my DIY method and spreadsheet so you can skip paying anyone.",
      "substitute_text": "An AI tool now does the whole job automatically, end to end, with no person involved.",
      "competition_text": "The market is held by a handful of large established firms, national consulting companies with big brands.",
      "compliance_text": "Only a state-licensed professional may legally perform this work; the seller must hold a professional licence.",
      "pricing_text": "This is charged as a fee for a single project, paid once when the project is delivered.",
      "access_text": "These buyers mostly talk in an online forum and a busy Facebook community group."},
     {"demand_signal": "selfserve", "ai_pressure": "replace", "competition": "giants", "regulation": "licence",
      "billing": "project", "reach": "community"}),
    ({"demand_text": "Before they buy, owners ask to see a free sample or a short free trial of the work.",
      "substitute_text": "Owners hire a freelancer or an agency to do the work for them. AI tools help that person draft it faster.",
      "competition_text": "A small group of specialist vendors serve this niche, and each is an independent specialist working alone.",
      "compliance_text": "Sellers must hold a certification and register with the state before offering this.",
      "pricing_text": "Vendors charge an hourly fee for this work.",
      "access_text": "These buyers are scattered across the open web, with no shared place where they gather."},
     {"trust_barrier": "sample", "substitute": "human", "ai_pressure": "assist", "competition": "specialists",
      "delivery": "solo", "regulation": "certificate", "billing": "hourly", "reach": "scattered"}),
)

TRUST = {"probe_min": 0.67, "null_escape_min": 0.8, "stability_min": 0.67}


def quality(probe_finals: List[Dict[str, str]], null_finals: List[Dict[str, str]], venture_finals: List[Dict[str, str]]) -> Dict[str, dict]:
    """Per question: probe accuracy, escape rate on irrelevant text, stability across ventures, and trusted or not."""
    out = {}
    for q in QUESTIONS:
        scored = [(f.get(q.id), exp[q.id]) for f, (_, exp) in zip(probe_finals, PROBES) if q.id in exp]
        acc = sum(1 for got, want in scored if got == want) / len(scored) if scored else None
        nulls = [f.get(q.id) for f in null_finals if q.id in f]
        null_esc = sum(1 for a in nulls if a in (ESCAPE_KEY, "unstable")) / len(nulls) if nulls else None
        vs = [f[q.id] for f in venture_finals if q.id in f]
        stab = sum(1 for a in vs if a != "unstable") / len(vs) if vs else None
        why = []
        if acc is None or acc < TRUST["probe_min"]:
            why.append(f"probe accuracy {acc if acc is None else round(acc, 2)} below {TRUST['probe_min']}")
        if null_esc is None or null_esc < TRUST["null_escape_min"]:
            why.append(f"answered irrelevant text (escape rate {null_esc if null_esc is None else round(null_esc, 2)}, needs {TRUST['null_escape_min']})")
        if stab is None or stab < TRUST["stability_min"]:
            why.append(f"stability {stab if stab is None else round(stab, 2)} below {TRUST['stability_min']}")
        out[q.id] = {"text": q.text, "probe_accuracy": acc, "probes": len(scored), "null_escape": null_esc,
                     "stability": stab, "trusted": not why, "why_untrusted": why}
    return out


def judge(final: Dict[str, str], qual: Dict[str, dict]) -> Dict[str, object]:
    """Turn one venture's final answers into a verdict.  Untrusted, unstable and escape answers never kill or save."""
    cells = {}
    for q in QUESTIONS:
        a = final.get(q.id)
        if a is None:
            status = "no evidence"
        elif not qual[q.id]["trusted"]:
            status = "untrusted"
        elif a == "unstable":
            status = "unstable"
        elif a == ESCAPE_KEY:
            status = UNPROVEN
        else:
            status = VERDICTS[q.id][a]
        label = next((o.label for o in q.options if o.key == a), a)
        cells[q.id] = {"answer": a, "label": label, "status": status}
    kills = [q for q, c in cells.items() if c["status"] == KILL]
    warns = [q for q, c in cells.items() if c["status"] == WARN]
    weak = [q for q in CRITICAL if cells[q]["status"] != PASS]
    verdict = "KILLED" if kills else "STANDS" if not weak else "WOUNDED"
    return {"verdict": verdict, "kills": kills, "warns": warns, "critical_unproven": weak, "cells": cells}


# ---------------------------------------------------------------------------
# The whole run, cached per venture so a rerun costs nothing.
# ---------------------------------------------------------------------------

def _cache(path: str, make: Callable[[], dict]) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("v") == VERSION:
            return data
    data = dict(make(), v=VERSION)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return data


def run(ventures: List[dict], search, provider_name: str, cache_dir: str, n_null: int = 5, log=print) -> dict:
    os.makedirs(cache_dir, exist_ok=True)
    probe_finals = [_cache(os.path.join(cache_dir, f"probe{i}.json"),
                           lambda i=i, f=f: ask_runs(provider_name, state_for(f"probe{i}", "Probe service", f), seed=900 + i))["final"]
                    for i, (f, _) in enumerate(PROBES)]
    null_finals = [_cache(os.path.join(cache_dir, f"null_{NULL_TAG}{i}.json"),
                          lambda i=i: ask_runs(provider_name, state_for(f"null{i}", ventures[i % len(ventures)]["offer"],
                                                                        {s: NULL_TEXT for s in SOURCES}), runs=1, seed=950 + i))["final"]
                   for i in range(n_null)] if ventures else []
    done, stopped = [], None
    for k, v in enumerate(ventures):
        path = os.path.join(cache_dir, f"{v['id']}.json")
        try:
            def make(v=v, k=k):
                text, urls = gather(v, search)
                got = ask_runs(provider_name, state_for(v["id"], v["offer"], text), seed=k)
                return {"id": v["id"], "evidence": text, "urls": urls, **got}
            done.append((v, _cache(path, make)))
        except SearchBudget as exc:
            stopped = str(exc)
            log(stopped)
            break
        except RuntimeError as exc:
            stopped = f"stopped on {v['offer'][:50]!r}: {exc}"
            log(stopped)
            break
    qual = quality(probe_finals, null_finals, [d["final"] for _, d in done])
    rows = []
    for v, d in done:
        j = judge(d["final"], qual)
        rows.append({"id": v["id"], "offer": v["offer"], "buyer": v["buyer"], "proof_label": v.get("label"),
                     "score": v.get("score"), "picked": v.get("picked", False), **j,
                     "urls": d["urls"], "evidence_chars": {k: len(t) for k, t in d["evidence"].items()}})
    order = {"STANDS": 0, "WOUNDED": 1, "KILLED": 2}
    rows.sort(key=lambda r: (order[r["verdict"]], len(r["kills"]), len(r["critical_unproven"]), len(r["warns"]), -(r["score"] or 0)))
    return {"version": VERSION, "provider": provider_name, "runs": RUNS, "questions": qual,
            "critical": list(CRITICAL), "trust_thresholds": TRUST, "rows": rows,
            "complete": len(done) == len(ventures), "stopped": stopped,
            "counts": {k: sum(1 for r in rows if r["verdict"] == k) for k in order}}


def markdown(res: dict, stub: bool) -> str:
    c = res["counts"]
    L = ["# Make-or-break test (Jev)", ""]
    if stub:
        L += ["**STUB RUN: synthetic answers. Plumbing only.**", ""]
    if not res["complete"]:
        L += [f"**Incomplete run: {res['stopped']}. Rerun to finish (cached work is free).**", ""]
    L += [f"Ventures tested: {len(res['rows'])}. STANDS {c['STANDS']}, WOUNDED {c['WOUNDED']}, KILLED {c['KILLED']}.", "",
          f"Each venture: {len(QUESTIONS)} typed questions, answered by Jev {res['runs']} times with shuffled options, from raw search "
          "results gathered per question (no model summarised them). STANDS needs no kill and a passed answer on both critical "
          "questions (buyer demand, buyer reach). An untrusted, unstable or unanswered question can neither kill nor save.", "",
          "## Can the questions be trusted?", "",
          "| Question | Probe accuracy | Escapes on irrelevant text | Stable across ventures | Trusted |", "|---|---|---|---|---|"]
    f = lambda x: "-" if x is None else f"{x:.0%}"
    for q, v in res["questions"].items():
        L.append(f"| {q} | {f(v['probe_accuracy'])} ({v['probes']}) | {f(v['null_escape'])} | {f(v['stability'])} | "
                 + ("yes" if v["trusted"] else "NO: " + "; ".join(v["why_untrusted"])) + " |")
    L += ["", "## Verdicts", ""]
    for r in res["rows"]:
        star = " (picked)" if r["picked"] else ""
        L += [f"### {r['verdict']}: {r['offer']}{star}", f"- Buyer: {r['buyer']}. Proof label from the top-20 stage: {r['proof_label']}, score {r['score']}."]
        if r["kills"]:
            L.append("- Killed by: " + "; ".join(f"{q} = {r['cells'][q]['label']}" for q in r["kills"]))
        if r["critical_unproven"]:
            L.append("- Critical, unproven: " + "; ".join(f"{q} ({r['cells'][q]['status'].lower()}: {r['cells'][q]['label']})" for q in r["critical_unproven"]))
        if r["warns"]:
            L.append("- Warnings: " + "; ".join(f"{q} = {r['cells'][q]['label']}" for q in r["warns"]))
        passed = [q for q, c in r["cells"].items() if c["status"] == PASS]
        if passed:
            L.append("- Passed: " + "; ".join(f"{q} = {r['cells'][q]['label']}" for q in passed))
        L.append("")
    return "\n".join(L) + "\n"
