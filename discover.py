#!/usr/bin/env python3
"""Venture discovery CLI: harvest -> dedupe -> tag -> screen -> ground -> verify -> report.

harvest brainstorms without web search (numbers are guesses); ground then searches the web for the
best survivors only, replacing guessed price/pool with cited figures.

--provider stub runs every stage offline with synthetic data (written to
discovery/out_stub so it can never mix with a live run).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from discovery import dedupe as D, ground as G, harvest as H, rank as R, screen as S, seeds, tag as T, verify as V
from discovery.groq_client import make_groq, GroqProvider
from run import _load_dotenv


def out_dir(provider: str) -> str:
    path = os.path.join(HERE, "discovery", "out_stub" if provider == "stub" else "out")
    os.makedirs(path, exist_ok=True)
    return path


def _read(path: str):
    if not os.path.exists(path):
        raise SystemExit(f"missing {os.path.relpath(path, HERE)}; run the earlier stage first")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)


def cmd_models(args) -> None:
    for m in GroqProvider().list_models():
        print(m)


def cmd_harvest(args) -> None:
    o = out_dir(args.provider)
    queries = seeds.build_queries()
    cache = os.path.join(o, "cache")
    stats = H.harvest(make_groq(args.provider), queries, cache, limit=args.limit, max_tokens=args.max_tokens)
    print(f"harvest: {stats}  (matrix size {len(queries)})")
    raw = H.load_cached(cache, queries)
    _write(os.path.join(o, "raw.json"), {"n_queries": len(queries), "candidates": raw})
    print(f"{len(raw)} valid candidates cached. Rerun to resume if it stopped early.")


def cmd_dedupe(args) -> None:
    o = out_dir(args.provider)
    raw = _read(os.path.join(o, "raw.json"))
    unique = D.dedupe(raw["candidates"])
    sat = D.saturation(unique, raw["n_queries"])
    _write(os.path.join(o, "unique.json"), {"n_queries": raw["n_queries"], "n_raw": len(raw["candidates"]),
                                            "unique": unique, "saturation": sat})
    print(f"{len(raw['candidates'])} raw -> {len(unique)} unique")


def cmd_tag(args) -> None:
    o = out_dir(args.provider)
    unique = _read(os.path.join(o, "unique.json"))["unique"]
    if args.limit:
        unique = unique[:args.limit]
    tags = T.tag_all(unique, args.provider)
    _write(os.path.join(o, "tags.json"), tags)
    ok = sum(1 for t in tags.values() if t["status"] == "ok")
    print(f"tagged {ok}/{len(unique)} (others: insufficient evidence or error)")


def cmd_screen(args) -> None:
    o = out_dir(args.provider)
    data = _read(os.path.join(o, "unique.json"))
    rows = [dict(c, screen=S.screen(c)) for c in data["unique"]]
    _write(os.path.join(o, "screened.json"), rows)
    from collections import Counter
    print(dict(Counter(r["screen"]["verdict"] for r in rows)))


def cmd_ground(args) -> None:
    o = out_dir(args.provider)
    rows = _read(os.path.join(o, "screened.json"))
    cache = os.path.join(o, "cache_ground")
    stats = G.ground_all(make_groq(args.provider), rows, cache, n=args.top, max_tokens=args.max_tokens)
    print(f"ground: {stats}")
    merged = G.merge_cached(rows, cache)
    _write(os.path.join(o, "grounded.json"), merged)
    print(f"{sum(1 for r in merged if r.get('grounded'))} candidates now carry cited price or pool figures")


def cmd_verify(args) -> None:
    o = out_dir(args.provider)
    src = "grounded.json" if os.path.exists(os.path.join(o, "grounded.json")) else "screened.json"
    rows = _read(os.path.join(o, src))
    fetcher = V.stub_fetch if args.provider == "stub" else V.fetch
    n = 0
    for r in rows:
        if r["screen"]["verdict"] == "SURVIVES":
            r["verify"] = V.grade(r, fetcher)
            n += 1
    _write(os.path.join(o, "verified.json"), rows)
    print(f"graded {n} survivors")


def cmd_report(args) -> None:
    o = out_dir(args.provider)
    rows = _read(os.path.join(o, "verified.json" if os.path.exists(os.path.join(o, "verified.json")) else "screened.json"))
    meta = _read(os.path.join(o, "unique.json"))
    tags_path = os.path.join(o, "tags.json")
    tags = _read(tags_path) if os.path.exists(tags_path) else {}
    for r in rows:
        r["tags"] = tags.get(r["id"], {})
    text = R.report(rows, meta["n_queries"], meta["n_raw"], meta["saturation"], args.provider == "stub")
    dest = os.path.join(HERE, "analysis", "venture_universe_stub.md" if args.provider == "stub" else "venture_universe.md")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(dest, HERE)}")


def main(argv=None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(prog="discover.py", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="list model ids your GROQ_API_KEY can use")
    for name, fn in (("harvest", cmd_harvest), ("dedupe", cmd_dedupe), ("tag", cmd_tag),
                     ("screen", cmd_screen), ("ground", cmd_ground), ("verify", cmd_verify), ("report", cmd_report)):
        sp = sub.add_parser(name)
        sp.add_argument("--provider", choices=("live", "stub"), default="stub",
                        help="stub (default) is offline and synthetic; live uses your keys")
        if name in ("harvest", "tag"):
            sp.add_argument("--limit", type=int, default=None, help="max new calls this run (smoke test)")
        if name in ("harvest", "ground"):
            sp.add_argument("--max-tokens", type=int, default=None,
                            help="stop a run once this many Groq tokens are used (free tier is ~200k/day per model)")
        if name == "ground":
            sp.add_argument("--top", type=int, default=10, help="ground this many top survivors")
        sp.set_defaults(fn=fn)
    args = p.parse_args(argv)
    if args.command == "models":
        cmd_models(args)
    else:
        args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
