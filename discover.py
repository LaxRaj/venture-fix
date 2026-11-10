#!/usr/bin/env python3
"""Venture discovery CLI: harvest -> dedupe -> tag -> screen -> ground -> verify -> prove -> top -> report.

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

from discovery import prove as PV, top as TOP, volume as VOL, census as CS, tagcheck as TC, dashboard as DB, search as SE, dedupe as D, ground as G, harvest as H, rank as R, screen as S, seeds, tag as T, verify as V
from discovery.groq_client import make_groq, make_lanes, GroqProvider
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
    queries = seeds.all_queries()
    cache = os.path.join(o, "cache")
    if args.provider == "live" and not args.sequential and not args.limit:
        lanes = make_lanes()
        print(f"harvesting on {len(lanes)} lanes in parallel (one per model and key): "
              + ", ".join(f"{l.lane[0].split('/')[-1]}/key{l.lane[1] + 1}" for l in lanes))
        stats = H.harvest_parallel(lanes, queries, cache, max_tokens=args.max_tokens)
        if stats["tokens"]:
            stats["tokens_by_lane"] = {f"{l.lane[0].split('/')[-1]}/key{l.lane[1] + 1}": l.tokens_used for l in lanes}
    else:
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


def _latest_rows(o: str):
    """The most advanced saved stage: verified > grounded > screened."""
    for name in ("verified.json", "grounded.json", "screened.json"):
        path = os.path.join(o, name)
        if os.path.exists(path):
            return _read(path)
    raise SystemExit("no screened candidates yet; run dedupe and screen first")


def _tag_v2(args) -> None:
    o = out_dir(args.provider)
    rows = _latest_rows(o)
    if args.scope == "survivors":
        rows = [r for r in rows if r["screen"].get("verdict") == "SURVIVES"]
    path = os.path.join(o, "tags_v2.json")
    merged = _read(path) if os.path.exists(path) else {}
    if not args.retag:                    # keep earlier answers; only tag candidates with no usable tags yet
        rows = [r for r in rows if merged.get(r["id"], {}).get("status") != "ok"]
    if args.limit:
        rows = rows[:args.limit]
    tags = T.tag_v2(rows, args.provider)
    merged.update(tags)           # keep earlier results for candidates not in this run
    _write(path, merged)
    from collections import Counter
    print(f"tagged {len(tags)} candidates (v2 bank, 2 shuffled runs each): {dict(Counter(t['status'] for t in tags.values()))}")
    qc = os.path.join(o, "tagcheck.json")
    ok_q = sorted(TC.trusted(_read(qc))) if os.path.exists(qc) else []
    print("note: validated questions that may demote the shortlist: " + (", ".join(q for q in ok_q if q in R.DEMOTING) or "none")
          if ok_q else "note: Jev removes nothing from the shortlist until `tagcheck --run` has validated a question.")


def cmd_tagcheck(args) -> None:
    o = out_dir(args.provider)
    rows = _latest_rows(o)
    print("Offline coverage (keyword proxy: how often the source text mentions an answer option; low = expect escapes):")
    for c in TC.coverage(rows):
        cov = "n/a" if c["mentions_option"] is None else f"{100 * c['mentions_option']:.0f}%"
        print(f"  {c['question']:16} reads {c['source']:15} candidates {c['candidates']:>4}  mentions an option: {cov}")
    if not args.run:
        print("\n(proxy only; add --run to test the questions on the gold set)")
        return
    doc = TC.load_gold()
    items = TC.gold_items(doc, rows)
    print(f"\nRunning {len(items)} gold items x 2 shuffled runs = {2 * len(items)} requests ...")
    tags = T.tag_v2([dict(r) for r, _ in items], args.provider)
    report = {"thresholds": TC.THRESHOLDS, "items": len(items), "provider": args.provider, "questions": TC.score(items, tags)}
    _write(os.path.join(o, "tagcheck.json"), report)
    _write(os.path.join(o, "tagcheck_tags.json"), tags)
    print(f"\n{'question':16}{'n':>4}{'escape':>8}{'stable':>8}{'gold':>7}{'vs Groq':>9}  verdict")
    for q, v in report["questions"].items():
        f = lambda x: "-" if x is None else f"{x:.2f}"
        print(f"{q:16}{v['tagged']:>4}{f(v['escape_rate']):>8}{f(v['stability']):>8}{f(v['gold_agreement']):>7}{f(v['groq_agreement']):>9}  "
              + ("KEEP" if v["keep"] else "CUT: " + "; ".join(v["why_cut"])))
        if "demoting_gold" in v:
            print(f"{'':16}removal classes: recall {f(v['demoting_recall'])} on {v['demoting_gold']} labelled, wrongly demoted {v['wrongly_demoted']}")


def cmd_tag(args) -> None:
    if args.bank == "v2":
        return _tag_v2(args)
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


def _merged_rows(o: str):
    """The current candidate list with every cached result applied: the fresh screen, then pools, price search,
    browser grounding and volumes.  Never start from grounded.json: it predates any later dedupe, so candidates
    added since would silently vanish from every later step."""
    rows = _read(os.path.join(o, "screened.json"))
    dirs = [os.path.join(o, d) for d in ("cache_ground", "cache_ground_pools", "cache_ground_search")]
    return VOL.apply_cached(G.merge_cached(rows, *dirs), os.path.join(o, "cache_volume"))


def cmd_volume(args) -> None:
    o = out_dir(args.provider)
    gp = os.path.join(o, "grounded.json")
    rows = _merged_rows(o)
    cache = os.path.join(o, "cache_volume")
    todo = [r for r in VOL.wanted(rows)]
    if args.limit:                                      # smoke test: only the first N uncached
        todo = [r for r in todo if not os.path.exists(os.path.join(cache, VOL.key(r) + ".json"))][:args.limit]
    stats = VOL.fill(make_groq(args.provider), todo, cache, max_tokens=args.max_tokens)
    print(f"volume: {stats}  ({len(VOL.wanted(rows))} per-unit/project candidates)")
    before = {r["id"]: r["screen"]["verdict"] for r in rows}
    merged = VOL.apply_cached(rows, cache)
    _write(gp, merged)
    from collections import Counter
    moved = Counter((before[r["id"]], r["screen"]["verdict"]) for r in merged if before[r["id"]] != r["screen"]["verdict"])
    print("verdict changes from derived monthly prices:", {f"{a} -> {b}": n for (a, b), n in moved.most_common()})
    print("derived survivors:", sum(1 for r in merged if r["screen"].get("derived") and r["screen"]["verdict"] == "SURVIVES"))


def cmd_ground(args) -> None:
    o = out_dir(args.provider)
    # Rebuild from the fresh screen plus every cache (see _merged_rows): a candidate can become a survivor only after
    # its Census pool is added, and grounded.json from an earlier run would miss anything added by a later dedupe.
    rows = _merged_rows(o)
    groq = make_groq(args.provider)
    dirs = [os.path.join(o, "cache_ground")]
    if args.pools_only:
        census = CS.make_census(args.provider, os.path.join(o, "cache_census"))
        if census is None:
            raise SystemExit("--pools-only needs CENSUS_API_KEY")
        d = os.path.join(o, "cache_ground_pools")
        print(f"ground (census pools): {G.ground_pools(census, rows, d)}")
        merged = VOL.apply_cached(G.merge_cached(rows, *dirs, d, os.path.join(o, "cache_ground_search")), os.path.join(o, "cache_volume"))
        _write(os.path.join(o, "grounded.json"), merged)
        print(f"{sum(1 for r in merged if r.get('grounded'))} candidates now carry cited price or pool figures")
        return
    if args.engine == "browser":
        stats = G.ground_all(groq, rows, dirs[0], n=args.top, max_tokens=args.max_tokens, scope="survivors")
    else:
        d = os.path.join(o, "cache_ground_search")
        search = SE.make_search(args.provider, os.path.join(o, "cache_search"), args.max_searches)
        census = CS.make_census(args.provider, os.path.join(o, "cache_census"))
        if census is None:
            print("note: CENSUS_API_KEY not set, so buyer pools stay model guesses")
        stats = G.ground_all_search(groq, search, census, rows, d, n=args.top, max_tokens=args.max_tokens, scope=args.scope)
        dirs += [os.path.join(o, "cache_ground_pools"), d]
    print(f"ground ({args.engine}): {stats}")
    merged = VOL.apply_cached(G.merge_cached(rows, *dirs), os.path.join(o, "cache_volume"))
    _write(os.path.join(o, "grounded.json"), merged)
    print(f"{sum(1 for r in merged if r.get('grounded'))} candidates now carry cited price or pool figures")


_CENSUS_MEMO: dict = {}


def _census_check(url: str, claimed: float):
    """Re-check a cited Census pool against the live API (key from the environment).  Each industry code is
    fetched once per run because many candidates share a sector.  None if unreachable."""
    key = os.environ.get("CENSUS_API_KEY", "")
    return CS.check_pool(url, claimed, key, memo=_CENSUS_MEMO) if key else None


def cmd_verify(args) -> None:
    o = out_dir(args.provider)
    src = "grounded.json" if os.path.exists(os.path.join(o, "grounded.json")) else "screened.json"
    rows = _read(os.path.join(o, src))
    fetcher = V.stub_fetch if args.provider == "stub" else V.fetch
    census_check = (lambda url, v: True) if args.provider == "stub" else _census_check
    n = 0
    for r in rows:
        if r["screen"]["verdict"] == "SURVIVES":
            r["verify"] = V.grade(r, fetcher, census_check)
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
    p2, pc = os.path.join(o, "tags_v2.json"), os.path.join(o, "tagcheck.json")
    rows = R.apply_jev_gate(rows, _read(p2) if os.path.exists(p2) else {}, TC.trusted(_read(pc) if os.path.exists(pc) else None))
    text = R.report(rows, meta["n_queries"], meta["n_raw"], meta["saturation"], args.provider == "stub")
    dest = os.path.join(HERE, "analysis", "venture_universe_stub.md" if args.provider == "stub" else "venture_universe.md")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(dest, HERE)}")


def _gated_rows(o: str):
    """verified rows with the Jev gate applied: the input to prove and top."""
    rows = _read(os.path.join(o, "verified.json"))
    p2, pc = os.path.join(o, "tags_v2.json"), os.path.join(o, "tagcheck.json")
    trusted = TC.trusted(_read(pc) if os.path.exists(pc) else None)
    return R.apply_jev_gate(rows, _read(p2) if os.path.exists(p2) else {}, trusted), trusted


def cmd_prove(args) -> None:
    o = out_dir(args.provider)
    rows, _ = _gated_rows(o)
    todo = PV.eligible(rows)
    print(f"{len(todo)} survivors are eligible for the proof search (stress-surviving, cited price, not removed by Jev)")
    search = SE.make_search(args.provider, os.path.join(o, "cache_search"), args.max_searches)
    stats = PV.prove_all(make_groq(args.provider), search, rows, os.path.join(o, "cache_prove"))
    print(f"prove: {stats}")


def cmd_top(args) -> None:
    o = out_dir(args.provider)
    rows, trusted = _gated_rows(o)
    rows = PV.apply_cached(rows, os.path.join(o, "cache_prove"))
    n = sum(1 for r in rows if r.get("proof"))
    if not n:
        raise SystemExit("no proof yet; run `prove` first")
    result = TOP.build(rows, trusted)
    _write(os.path.join(o, "top.json"), result)
    dest = os.path.join(HERE, "analysis", "venture_top20_stub.md" if args.provider == "stub" else "venture_top20.md")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(TOP.markdown(result, args.provider == "stub"))
    print(f"{n} proved rows; counts {result['counts']}")
    print(f"wrote {os.path.relpath(dest, HERE)} and {os.path.relpath(os.path.join(o, 'top.json'), HERE)}")


def cmd_dashboard(args) -> None:
    path = DB.build(out_dir(args.provider), stub=args.provider == "stub")
    print(f"wrote {os.path.relpath(path, HERE)}  (open it in a browser; no server needed)")
    if args.open:
        import webbrowser
        webbrowser.open("file://" + path)


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
        if name == "tag":
            sp.add_argument("--bank", choices=("v2", "v1"), default="v2", help="v2: five decision-focused questions (default); v1: the original 15")
            sp.add_argument("--scope", choices=("survivors", "all"), default="survivors", help="v2: which candidates to tag")
            sp.add_argument("--retag", action="store_true", help="v2: tag again even candidates that already have tags")
        if name == "harvest":
            sp.add_argument("--sequential", action="store_true", help="one lane at a time (the old behaviour)")
        if name in ("harvest", "ground"):
            sp.add_argument("--max-tokens", type=int, default=None,
                            help="stop a run once this many Groq tokens are used (free tier is ~200k/day per model)")
        if name == "ground":
            sp.add_argument("--engine", choices=("search", "browser"), default="search",
                            help="search: search API + Census (cheap, default); browser: Groq browsing (17-62k tokens each)")
            sp.add_argument("--top", type=int, default=10, help="ground this many candidates this run")
            sp.add_argument("--scope", choices=("all", "survivors"), default="all", help="search engine: which candidates")
            sp.add_argument("--max-searches", type=int, default=None, help="cap on paid search calls this run")
            sp.add_argument("--pools-only", action="store_true", help="only add Census buyer pools: no search, no Groq tokens")
        sp.set_defaults(fn=fn)
    vp = sub.add_parser("volume", help="guess a typical monthly volume for per-unit/project offers, so they can be scored")
    vp.add_argument("--provider", choices=("live", "stub"), default="stub")
    vp.add_argument("--limit", type=int, default=None, help="smoke test: only this many new candidates")
    vp.add_argument("--max-tokens", type=int, default=None)
    vp.set_defaults(fn=cmd_volume)
    pp = sub.add_parser("prove", help="find real vendors already charging for each survivor's service (cached; capped paid searches)")
    pp.add_argument("--provider", choices=("live", "stub"), default="stub")
    pp.add_argument("--max-searches", type=int, default=200, help="cap on paid search calls this run")
    pp.set_defaults(fn=cmd_prove)
    tp = sub.add_parser("top", help="score proved survivors, write the top 20 and the 7 picks")
    tp.add_argument("--provider", choices=("live", "stub"), default="stub")
    tp.set_defaults(fn=cmd_top)
    tc = sub.add_parser("tagcheck", help="quality-check the Jev question bank: offline coverage, then --run on the gold set")
    tc.add_argument("--provider", choices=("live", "stub"), default="stub")
    tc.add_argument("--run", action="store_true", help="send the gold set to Jev (two shuffled runs each)")
    tc.set_defaults(fn=cmd_tagcheck)
    dp = sub.add_parser("dashboard", help="build a self-contained HTML dashboard from whatever stages exist")
    dp.add_argument("--provider", choices=("live", "stub"), default="live")
    dp.add_argument("--open", action="store_true", help="open it in your browser")
    dp.set_defaults(fn=cmd_dashboard)
    args = p.parse_args(argv)
    if args.command == "models":
        cmd_models(args)
    else:
        args.fn(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
