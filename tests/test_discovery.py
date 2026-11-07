"""Offline tests for the discovery pipeline.  Run with: python3 -I test_discovery.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from discovery import volume as VOL, questions_v2 as Q2, tagcheck as TC, census as CS, extract as X, search as SE, dashboard as DB, dedupe as D, ground as G, harvest as H, rank as R, screen as S, seeds, tag as T, verify as V
from discovery.groq_client import make_lanes, StubGroq, extract_json_list, extract_json_object, GroqProvider, DailyLimit, wait_seconds


def cand(offer, **kw):
    base = {"offer": offer, "buyer": "b", "task": "t", "price_usd": 750.0, "price_unit": "month", "price_url": None,
            "hours_per_account_month": 10.0, "pool_count": 50000.0, "pool_url": None, "channel": "c", "blockers": "",
            "evidence": {k: "x" for k in H.EVIDENCE_KEYS}, "source_query": "q", "query_index": 0,
            "sector": "s", "pain": "p", "model": "m"}
    base.update(kw)
    return base


def test_seed_matrix() -> None:
    qs = seeds.build_queries()
    assert len(qs) == len(seeds.SECTORS) * len(seeds.PAINS) >= 300
    assert len({q["id"] for q in qs}) == len(qs)
    assert qs == seeds.build_queries()  # deterministic


def test_merged_rows_ignore_a_stale_grounded_file() -> None:
    import discover as DV
    def row(i, price):
        c = cand(f"offer{i} s{i}", price_usd=float(price), hours_per_account_month=10.0, pool_count=50000.0)
        c["id"] = f"v{i}"; c["sector"] = "law firms"; c["screen"] = S.screen(c); return c
    old, new = [row(0, 750), row(1, 300)], [row(0, 750), row(1, 300), row(2, 900)]      # a later dedupe added a third candidate
    with tempfile.TemporaryDirectory() as o:
        json.dump(new, open(os.path.join(o, "screened.json"), "w"))
        json.dump(old, open(os.path.join(o, "grounded.json"), "w"))                      # stale: written before the third arrived
        os.makedirs(os.path.join(o, "cache_ground_pools"))
        G._write(os.path.join(o, "cache_ground_pools", G.key(new[2]) + ".json"), "offer2 s2",
                 {"pool_count": 12345.0, "pool_url": "https://api.census.gov/x", "pool_basis": "census", "grounded_via": "census"})
        merged = DV._merged_rows(o)
        assert [r["id"] for r in merged] == ["v0", "v1", "v2"]                            # the new candidate is present
        assert merged[2]["pool_count"] == 12345.0 and merged[2]["grounded_fields"] == ["pool"]   # and picks up its cached pool
        assert merged[0]["screen"] == S.screen(merged[0]) or merged[0]["screen"]["verdict"]    # untouched rows keep their screen


def test_creator_seed_set() -> None:
    core, cre = seeds.build_queries(), seeds.build_creator_queries()
    assert len(core) == len(seeds.SECTORS) * len(seeds.PAINS)                          # the core matrix is untouched
    assert len(cre) == len(seeds.CREATOR_BUYERS) * len(seeds.CREATOR_JOBS) == 77
    assert len({q["id"] for q in cre}) == len(cre)                                      # unique
    assert not ({q["id"] for q in cre} & {q["id"] for q in core})                       # and disjoint from the core set
    assert cre == seeds.build_creator_queries()                                         # deterministic
    for q in cre:
        assert q["sector"] in q["text"] and q["pain"] in q["text"]
        assert q["sector"] in seeds.CREATOR_BUYERS and q["pain"] in seeds.CREATOR_JOBS
        assert q["sector"] not in seeds.SECTORS                                         # never conflated with a core sector
    assert {q["model"] for q in cre} == set(seeds.CREATOR_MODELS)
    assert "per-video or per-clip fee" in {q["model"] for q in cre}
    assert seeds.all_queries() == core + cre                                            # core keeps its order and ids
    assert seeds.build_creator_queries(5) == cre[:5]
    # none of the creator jobs is one of the core pains that produced nonsense in creator sectors
    assert not (set(seeds.CREATOR_JOBS) & set(seeds.PAINS))


def test_extract_json() -> None:
    assert extract_json_list('Sure!\n[{"offer": "a"}, 3, {"offer": "b"}] done') == [{"offer": "a"}, {"offer": "b"}]
    assert extract_json_list("no json here") == []
    assert extract_json_list("[broken") == []


def test_validate() -> None:
    q = {"id": "q1", "sector": "s", "pain": "p", "model": "m"}
    assert H.validate({"offer": "", "buyer": "x"}, q) is None
    v = H.validate({"offer": "A", "buyer": "B", "price_usd": "$1,200", "price_unit": "weird", "price_url": "ftp://x",
                    "pool_count": -5}, q)
    assert H.validate({"offer": "A", "buyer": "B", "pool_count": 12}, q)["pool_count"] is None  # thousands-as-units guard
    assert H.validate({"offer": "A", "buyer": "B", "pool_count": 12000}, q)["pool_count"] == 12000.0
    assert v["price_usd"] == 1200.0 and v["price_unit"] is None and v["price_url"] is None and v["pool_count"] is None


def test_harvest_cache_and_resume() -> None:
    qs = seeds.build_queries(6)
    with tempfile.TemporaryDirectory() as d:
        s1 = H.harvest(StubGroq(), qs, d, limit=3, log=lambda *_: None)
        assert s1["called"] == 3
        s2 = H.harvest(StubGroq(), qs, d, log=lambda *_: None)
        assert s2["cached"] == 3 and s2["called"] == 3  # resumed, did not repeat

        class Flaky:
            def ask(self, text):
                raise RuntimeError("rate limited")
        qs2 = seeds.build_queries(8)
        s3 = H.harvest(Flaky(), qs2, d, log=lambda *_: None)
        assert s3["failed"] == 1 and s3["called"] == 0
        assert len(H.load_cached(d, qs)) == 6 * 3


def test_groq_retries_on_429() -> None:
    import vstress.client as C
    import discovery.groq_client as G
    os.environ["GROQ_API_KEY"] = "test"
    sleeps, calls = [], {"n": 0}

    def fake_post(url, body, headers, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("x returned HTTP 429: slow down")
        return {"choices": [{"message": {"content": '[{"offer": "a", "buyer": "b"}]'}}]}
    real = G._post_json
    G._post_json = fake_post
    try:
        out = GroqProvider(sleep=sleeps.append).ask("q")
    finally:
        G._post_json = real
        del os.environ["GROQ_API_KEY"]
    assert out == [{"offer": "a", "buyer": "b"}] and sleeps == [5.0, 10.0]


def _patched_post(fake):
    import discovery.groq_client as Gm
    real = Gm._post_json
    Gm._post_json = fake
    return Gm, real


def test_wait_seconds_and_citations() -> None:
    assert wait_seconds("Please try again in 7m58.224s. Need more") == 7 * 60 + 58.224
    assert wait_seconds("try again in 577ms") == 0.0 and wait_seconds("nothing") == 0.0
    assert extract_json_list('[{"offer": "a【1†L2-L3】", "buyer": "b"}]') == [{"offer": "a", "buyer": "b"}]
    assert extract_json_object('text {"price_usd": 5} tail') == {"price_usd": 5}
    assert extract_json_object("none") is None


def test_daily_limit_rotates_models() -> None:
    os.environ["GROQ_API_KEY"] = "test"
    os.environ["GROQ_MODELS"] = "openai/gpt-oss-20b,openai/gpt-oss-120b"
    seen = []

    def fake_post(url, body, headers, timeout=60):
        seen.append(body["model"])
        if body["model"] == "openai/gpt-oss-20b":
            raise RuntimeError("x returned HTTP 429: Rate limit on tokens per day (TPD). Please try again in 7m58s.")
        return {"choices": [{"message": {"content": '[{"offer": "a", "buyer": "b"}]'}}], "usage": {"total_tokens": 321}}
    Gm, real = _patched_post(fake_post)
    try:
        g = GroqProvider(sleep=lambda s: None)
        assert g.ask("q") == [{"offer": "a", "buyer": "b"}]
        assert seen == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"] and g.tokens_used == 321
        # a second model out for the day too -> DailyLimit, not an endless retry
        g.exhausted.add(("openai/gpt-oss-120b", 0))
        try:
            g.ask("q")
        except DailyLimit:
            pass
        else:
            raise AssertionError("expected DailyLimit")
    finally:
        Gm._post_json = real
        del os.environ["GROQ_API_KEY"]; del os.environ["GROQ_MODELS"]


def test_stray_tool_call_is_not_fatal() -> None:
    os.environ["GROQ_API_KEY"] = "test"
    def fake_post(url, body, headers, timeout=60):
        raise RuntimeError('x returned HTTP 400: {"error":{"message":"Tool choice is none, but model called a tool","code":"tool_use_failed"}}')
    Gm, real = _patched_post(fake_post)
    try:
        g = GroqProvider(sleep=lambda s: None)
        assert g.complete("p") == ""                                   # no answer, not a crash
        assert X.extract_price(g.complete, "o", "b", RES) is None      # so the candidate just keeps its guess
        try:
            g.ground("o", "b")                                         # with tools offered the same error is a real failure
        except RuntimeError:
            pass
        else:
            raise AssertionError("browser grounding must still surface the error")
    finally:
        Gm._post_json = real
        del os.environ["GROQ_API_KEY"]


def test_multiple_keys_rotate_before_models() -> None:
    for k in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEYS", "GROQ_MODELS"):
        os.environ.pop(k, None)
    os.environ.update(GROQ_API_KEY="k1", GROQ_API_KEY_2="k2", GROQ_API_KEY_3="k1", GROQ_API_KEYS="k4, k2",
                      GROQ_MODELS="openai/gpt-oss-120b,openai/gpt-oss-20b")
    seen = []

    def fake_post(url, body, headers, timeout=60):
        key = headers["Authorization"].split()[-1]
        seen.append((body["model"], key))
        if key == "k1":                                    # the first key is out of tokens for the day
            raise RuntimeError("x returned HTTP 429: Rate limit on tokens per day (TPD). Please try again in 7m58s.")
        return {"choices": [{"message": {"content": "[]"}}], "usage": {"total_tokens": 100}}
    Gm, real = _patched_post(fake_post)
    try:
        g = GroqProvider(sleep=lambda s: None)
        assert g.keys == ["k1", "k2", "k4"]                                         # ordered, de-duplicated
        g.ask("q")
        assert seen == [("openai/gpt-oss-120b", "k1"), ("openai/gpt-oss-120b", "k2")]   # same model, next key first
        assert g.exhausted == {("openai/gpt-oss-120b", 0)} and g.tokens_by_key == {1: 100}
        g.ask("q")
        assert seen[-1] == ("openai/gpt-oss-120b", "k2")                            # exhausted pair is not retried
        g.exhausted.update({("openai/gpt-oss-120b", 1), ("openai/gpt-oss-120b", 2)})
        g.ask("q")
        assert seen[-1] == ("openai/gpt-oss-20b", "k1") or seen[-1] == ("openai/gpt-oss-20b", "k2")   # only then the next model
        g.exhausted.update({(m, i) for m in g.models for i in range(3)})
        try:
            g.ask("q")
        except DailyLimit as exc:
            assert "3 key(s)" in str(exc)
        else:
            raise AssertionError("expected DailyLimit")
    finally:
        Gm._post_json = real
        for k in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEYS", "GROQ_MODELS"):
            os.environ.pop(k, None)


class _Lane(StubGroq):
    """A stub lane that records its calls, can die after a number of calls, and is slow enough to interleave."""
    def __init__(self, name, die_after=None, tokens=0):
        self.name, self.calls, self.die_after, self.tokens_used, self.per_call = name, [], die_after, 0, tokens

    def ask(self, text):
        import time
        time.sleep(0.01)
        if self.die_after is not None and len(self.calls) >= self.die_after:
            raise RuntimeError("daily token limit reached on lane")
        self.calls.append(text)
        self.tokens_used += self.per_call
        return super().ask(text)


def test_parallel_harvest_uses_every_lane_once_per_query() -> None:
    qs = seeds.build_queries(40)
    lanes = [_Lane(f"l{i}") for i in range(4)]
    with tempfile.TemporaryDirectory() as d:
        st = H.harvest_parallel(lanes, qs, d, log=lambda *_: None)
        assert st["called"] == 40 and st["failed"] == 0 and st["lanes"] == 4 and st["lanes_stopped"] == 0
        assert sorted(sum((l.calls for l in lanes), [])) == sorted(q["text"] for q in qs)     # every query exactly once
        assert sum(1 for l in lanes if l.calls) >= 3                                       # the work really was spread out
        assert len(os.listdir(d)) == 40
        st2 = H.harvest_parallel([_Lane("x")], qs, d, log=lambda *_: None)
        assert st2["cached"] == 40 and st2["called"] == 0                                  # resumes from cache


def test_parallel_harvest_survives_a_dying_lane() -> None:
    qs = seeds.build_queries(30)
    dead, a, b = _Lane("dead", die_after=2), _Lane("a"), _Lane("b")
    with tempfile.TemporaryDirectory() as d:
        st = H.harvest_parallel([dead, a, b], qs, d, log=lambda *_: None)
        assert st["lanes_stopped"] == 1 and len(dead.calls) == 2
        assert st["called"] == 30 and st["failed"] == 0                                    # its query was taken by another lane
        assert len(os.listdir(d)) == 30
    with tempfile.TemporaryDirectory() as d:                                                # every lane out: nothing is lost, rest reported
        st = H.harvest_parallel([_Lane("x", die_after=3), _Lane("y", die_after=3)], qs, d, log=lambda *_: None)
        assert st["called"] == 6 and st["failed"] == 24 and st["lanes_stopped"] == 2
        assert len(os.listdir(d)) == 6


def test_parallel_harvest_respects_token_budget() -> None:
    qs = seeds.build_queries(30)
    lanes = [_Lane(f"l{i}", tokens=500) for i in range(3)]
    with tempfile.TemporaryDirectory() as d:
        st = H.harvest_parallel(lanes, qs, d, max_tokens=3000, log=lambda *_: None)
        assert 6 <= st["called"] <= 8 and st["failed"] == 30 - st["called"]                # stops at the budget, within one call per lane


def test_lane_pinning_and_lane_construction() -> None:
    for k in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEYS", "GROQ_LANE_MODELS", "GROQ_MODELS"):
        os.environ.pop(k, None)
    os.environ.update(GROQ_API_KEY="k1", GROQ_API_KEY_2="k2")
    seen = []
    def fake_post(url, body, headers, timeout=60):
        seen.append((body["model"], headers["Authorization"].split()[-1]))
        return {"choices": [{"message": {"content": "[]"}}], "usage": {"total_tokens": 10}}
    Gm, real = _patched_post(fake_post)
    try:
        lanes = make_lanes()
        assert [l.lane for l in lanes] == [("openai/gpt-oss-120b", 0), ("openai/gpt-oss-20b", 0), ("openai/gpt-oss-120b", 1), ("openai/gpt-oss-20b", 1)]
        for l in lanes:
            l.ask("q")
        assert seen == [("openai/gpt-oss-120b", "k1"), ("openai/gpt-oss-20b", "k1"), ("openai/gpt-oss-120b", "k2"), ("openai/gpt-oss-20b", "k2")]
        pinned = lanes[2]
        pinned.exhausted.add(pinned.lane)
        try:
            pinned.ask("q")
        except DailyLimit:
            pass
        else:
            raise AssertionError("a pinned lane out of tokens must raise, not borrow another lane")
        assert len(seen) == 4                                                              # and it sent nothing
        os.environ["GROQ_LANE_MODELS"] = "openai/gpt-oss-20b"
        assert len(make_lanes()) == 2
    finally:
        Gm._post_json = real
        for k in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_LANE_MODELS"):
            os.environ.pop(k, None)


def test_generation_sends_no_search_tool() -> None:
    os.environ["GROQ_API_KEY"] = "test"
    bodies = []

    def fake_post(url, body, headers, timeout=60):
        bodies.append(body)
        return {"choices": [{"message": {"content": "[]"}}]}
    Gm, real = _patched_post(fake_post)
    try:
        g = GroqProvider(sleep=lambda s: None)
        g.ask("q"); g.ground("offer", "buyer")
    finally:
        Gm._post_json = real
        del os.environ["GROQ_API_KEY"]
    assert "tools" not in bodies[0] and bodies[1]["tools"] == [{"type": "browser_search"}]
    assert bodies[0]["max_completion_tokens"] < 3000 and bodies[1]["reasoning_effort"] == "low"


def test_ground_apply_requires_citation() -> None:
    c = cand("a", price_usd=500.0, pool_count=1000.0)
    g = G.apply(c, {"price_usd": 900, "price_unit": "month", "price_url": "https://x.test/p",
                    "pool_count": 77000, "pool_url": None})
    assert g["price_usd"] == 900 and g["grounded_fields"] == ["price"]
    assert g["pool_count"] == 1000.0 and g["guess"]["price_usd"] == 500.0  # uncited pool stays a guess
    none = G.apply(c, {"price_usd": 900, "price_url": None})
    assert none["price_usd"] == 500.0 and none["grounded"] is False
    assert G.apply(c, None)["grounded"] is False


def test_ground_pick_merge_and_resume() -> None:
    rows = []
    for i, price in enumerate((750, 300, 1800)):
        c = cand(f"offer{i} x{i}", price_usd=float(price), hours_per_account_month=10.0); c["id"] = f"v{i}"
        c["screen"] = S.screen(c); rows.append(c)
    assert [r["id"] for r in G.pick(rows, 5)] == ["v2", "v0"]  # v1 fails the hourly bar; fastest first
    with tempfile.TemporaryDirectory() as d:
        st = G.ground_all(StubGroq(), rows, d, n=1, log=lambda *_: None)
        assert st["called"] == 1
        assert G.ground_all(StubGroq(), rows, d, n=1, log=lambda *_: None)["cached"] == 1
        merged = G.merge_cached(rows, d)
        assert merged[2]["grounded"] and merged[2]["price_url"].startswith("https://example.invalid")
        assert merged[0].get("grounded") is None  # not grounded, untouched
        assert merged[2]["screen"]["verdict"] in ("SURVIVES", "FAILS_POOL", "FAILS_HR", "FAILS_CAP")


def test_pick_treats_pool_only_grounding_as_not_priced() -> None:
    def row(i, fields):
        c = cand(f"o{i} u{i}", price_usd=750.0, hours_per_account_month=10.0, pool_count=50000.0)
        c["id"] = f"v{i}"; c["grounded_fields"] = fields; c["grounded"] = bool(fields); c["screen"] = S.screen(c); return c
    rows = [row(0, []), row(1, ["pool"]), row(2, ["price"]), row(3, ["pool", "price"])]
    assert {r["id"] for r in G.pick(rows, 10, "survivors")} == {"v0", "v1"}          # a pool-only row still needs its price
    assert {r["id"] for r in G.pick(rows, 10, "all")} == {"v0", "v1"}


def test_per_unit_prices_are_scored_through_a_guessed_volume() -> None:
    base = dict(price_unit="per_unit", price_usd=40.0, hours_per_account_month=8.0, pool_count=50000.0)
    assert S.screen(cand("a", **base))["verdict"] == "UNIT"                                  # no volume: still not scored
    r = S.screen(cand("a", **base, units_per_account_month=15.0))
    assert r["derived"] is True and r["monthly_price"] == 600.0 and r["verdict"] == "SURVIVES"
    assert r["per_hr"] == 75.0 and r["accounts"] == 5 and r["weeks_base"] == 16.7
    assert S.screen(cand("a", **dict(base, price_usd=3.0), units_per_account_month=20.0))["verdict"] == "FAILS_HR"   # $60/mo over 8h
    assert S.screen(cand("a", **dict(base, price_usd=4000.0), units_per_account_month=3.0))["price_flag"] is True      # derived $12,000/mo
    assert S.screen(cand("a", price_unit="contingency", units_per_account_month=9.0))["verdict"] == "CONTINGENCY"      # volume cannot rescue it
    assert S.screen(cand("a", price_usd=750.0, hours_per_account_month=10.0, pool_count=50000.0))["derived"] is False  # monthly rows unchanged


def test_volume_validation_fill_and_apply() -> None:
    assert VOL.validate({"units_per_month": 8, "unit_name": "video", "basis": "two a week"}) == {"units_per_account_month": 8.0, "unit_name": "video", "volume_basis": "two a week"}
    for bad in (None, {}, {"units_per_month": 0}, {"units_per_month": -3}, {"units_per_month": 9999}, {"units_per_month": "many"}):
        assert VOL.validate(bad) is None                                                     # implausible or missing: no volume, no score
    rows = []
    for i, (unit, price) in enumerate([("per_unit", 40.0), ("project", 900.0), ("month", 500.0), ("contingency", 100.0), ("per_unit", None)]):
        c = cand(f"v{i} q{i}", price_unit=unit, price_usd=price, hours_per_account_month=8.0, pool_count=50000.0); c["id"] = f"v{i}"
        c["screen"] = S.screen(c); rows.append(c)
    assert [r["id"] for r in VOL.wanted(rows)] == ["v0", "v1"]                               # only per-unit/project rows that have a price
    with tempfile.TemporaryDirectory() as d:
        st = VOL.fill(StubGroq(), rows, d, log=lambda *_: None)
        assert st["called"] == 2 and st["answered"] == 2
        assert VOL.fill(StubGroq(), rows, d, log=lambda *_: None)["cached"] == 2            # resumes from cache
        out = VOL.apply_cached(rows, d)
        assert out[0]["units_per_account_month"] == 6.0 and out[0]["screen"]["derived"] and out[0]["screen"]["monthly_price"] == 240.0
        assert out[2] == rows[2] and out[3] == rows[3]                                       # monthly and contingency rows untouched
        assert rows[0]["screen"]["verdict"] == "UNIT"                                        # inputs not mutated

        class Limit(StubGroq):
            def complete(self, prompt, max_out=600):
                raise RuntimeError("daily token limit reached")
        with tempfile.TemporaryDirectory() as d2:
            st2 = VOL.fill(Limit(), rows, d2, log=lambda *_: None)
            assert st2["failed"] == 1 and st2["called"] == 0                                 # a limit stops the run cleanly


def test_derived_survivors_stay_off_the_shortlist() -> None:
    def row(i, derived):
        c = cand(f"o{i} z{i}", price_unit="per_unit" if derived else "month", price_usd=40.0 if derived else 600.0,
                 hours_per_account_month=8.0, pool_count=50000.0, units_per_account_month=15.0 if derived else None)
        c["id"] = f"v{i}"; c["screen"] = S.screen(c); c["verify"] = {"grade": "A", "reason": "r"}; return c
    rows = [row(0, True), row(1, False)]
    assert rows[0]["screen"]["derived"] and rows[0]["screen"]["verdict"] == "SURVIVES"
    assert [r["id"] for r in R.shortlist(rows)] == ["v1"]
    txt = R.report(rows, 1, 2, [], stub=False)
    assert "monthly price derived from a GUESSED volume" in txt and "o0 z0" in txt.split("## Shortlist")[1].split("## All candidates")[0]


def test_token_budget_stops_run() -> None:
    class Spender(StubGroq):
        tokens_used = 0
        def ask(self, q):
            self.tokens_used += 600
            return super().ask(q)
    qs = seeds.build_queries(10)
    with tempfile.TemporaryDirectory() as d:
        st = H.harvest(Spender(), qs, d, max_tokens=1000, log=lambda *_: None)
        assert st["called"] == 2 and st["tokens"] == 1200


def test_dashboard_js_screen_matches_python() -> None:
    """Run the page's own JavaScript screen in Node against screen.py on the same inputs."""
    import json, re, shutil, subprocess
    node = shutil.which("node")
    if not node:
        print("  (skipped: node not installed)")
        return
    html = open(DB.TEMPLATE, encoding="utf-8").read()
    js = re.search(r"/\*__SCREEN_JS_START__\*/(.*?)/\*__SCREEN_JS_END__\*/", html, re.S).group(1)
    cases = [cand("a", price_usd=p, hours_per_account_month=hr, pool_count=pool, price_unit=u)
             for p, hr, pool, u in [(750, 10, 50000, "month"), (300, 3.5, 200000, "month"), (400, 8, 20000, "month"),
                                    (9, 0.1, 62000, "month"), (1800, 10, 20000, "month"), (1200, 15, 150, "month"),
                                    (150, 3, 30000, "month"), (500, None, 100, "month"), (100, 1, 5000, "contingency"),
                                    (6566, 2, 23000, "month"), (2500, 10, 50000, "month"), (2501, 10, 50000, "month"), (7, 0.2, 90000, "month"),
                                    (200, 2, 5000, "project"), (None, 4, 900, "month")]]
    for params in (dict(S.__dict__), ):
        pass
    cases += [cand("d1", price_unit="per_unit", price_usd=40.0, units_per_account_month=15.0, hours_per_account_month=8.0, pool_count=50000.0),
              cand("d2", price_unit="project", price_usd=900.0, units_per_account_month=2.0, hours_per_account_month=30.0, pool_count=40000.0),
              cand("d3", price_unit="per_unit", price_usd=3.0, units_per_account_month=20.0, hours_per_account_month=5.0, pool_count=40000.0),
              cand("d4", price_unit="per_unit", price_usd=4000.0, units_per_account_month=3.0, hours_per_account_month=9.0, pool_count=70000.0),
              cand("d5", price_unit="per_unit", price_usd=40.0, units_per_account_month=None, hours_per_account_month=8.0, pool_count=50000.0)]
    P = {"target": S.TARGET, "deliv": S.DELIV_HOURS, "out": S.OUT_PER_WEEK, "base": S.CONV_BASE, "stress": S.CONV_STRESS,
         "bar": S.BAR_HR, "reach": S.REACH_LIMIT, "flag": S.PRICE_FLAG}
    script = js + "\nconst P=" + json.dumps(P) + ";\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(c=>screenRow(c,P))));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    for c, got in zip(cases, json.loads(out)):
        want = S.screen(c)
        assert got["verdict"] == want["verdict"], (c, got, want)
        assert got.get("price_flag") == want.get("price_flag") and bool(got.get("derived")) == bool(want.get("derived")), (c, got, want)
        for k in ("per_hr", "accounts", "cap", "weeks_base", "weeks_stress", "monthly_price"):
            if k in want:
                assert abs(got[k] - want[k]) < 0.06, (k, got[k], want[k])  # python rounds to 1 dp


def test_dashboard_collect_and_render() -> None:
    qs = seeds.build_queries(12)
    with tempfile.TemporaryDirectory() as d:
        # Only the cache exists (a run in progress): the dashboard must still build, as a preview.
        H.harvest(StubGroq(), qs, os.path.join(d, "cache"), log=lambda *_: None)
        data = DB.collect(d, stub=True)
        assert data["preview"] and data["queries_done"] == 12 and len(data["rows"]) > 0
        assert all("screen" in r for r in data["rows"])
        # Model-written text must not be able to close the script tag.
        data["rows"][0]["offer"] = "</script><img src=x onerror=alert(1)>"
        page = DB.render(data)
        assert "</script><img" not in page and page.count("</script>") == 1  # only the template's own closer
        path = DB.build(d, stub=True)
        assert os.path.exists(path) and "STUB" in open(path, encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as empty:
        assert DB.collect(empty, stub=False)["rows"] == []  # no run yet: still builds


RES = [{"title": "Acme Fleet Compliance", "url": "https://acme.test/pricing", "snippet": "Plans start at $349 per month for small fleets."},
       {"title": "Blog", "url": "https://blog.test/x", "snippet": "No prices here."}]


def test_extract_accepts_only_provable_prices() -> None:
    V = lambda d, res: X.validate(d if d is None or "price_kind" in d or "price_usd" not in d else dict(d, price_kind="vendor_fee"), res)
    good = {"price_usd": 349, "price_unit": "month", "source_index": 0, "quote": "Plans start at $349 per month"}
    ok = V(good, RES)
    assert ok["price_usd"] == 349 and ok["price_url"] == "https://acme.test/pricing" and ok["evidence_quote"].startswith("Plans")
    assert V(dict(good, price_usd=299), RES) is None                      # figure not in the quote
    assert V(dict(good, quote="Plans start at $349 per week"), RES) is None  # quote not in the result
    assert V(dict(good, source_index=1), RES) is None                     # quote not in THAT result
    assert V(dict(good, source_index=7), RES) is None                     # index out of range
    assert V(dict(good, price_usd=0), RES) is None
    assert V(dict(good, price_unit="weekly"), RES) is None
    assert V(None, RES) is None and V({"price_usd": None}, RES) is None
    yr = V({"price_usd": 1200, "price_unit": "year", "source_index": 0, "quote": "Plans start at $349 per month"}, RES)
    assert yr is None                                                               # 1200 is not in the quote
    res2 = [{"title": "t", "url": "https://v.test", "snippet": "Billed annually at $1,200."}]
    ann = V({"price_usd": 1200, "price_unit": "year", "source_index": 0, "quote": "Billed annually at $1,200."}, res2)
    assert ann["price_usd"] == 100.0 and ann["price_unit"] == "month" and ann["price_quoted"] == 1200.0
    rng = [{"title": "t", "url": "https://v.test", "snippet": "Costs $150 to $400 per month depending on scope."}]
    r = V({"price_usd": 150, "price_unit": "month", "source_index": 0, "quote": "$150 to $400 per month"}, rng)
    assert r["price_usd"] == 150 and "range" in r["price_basis"]                      # a range is labelled, never silently taken
    assert ok["price_basis"] == "as quoted"
    assert X.extract_price(lambda p: "garbage", "o", "b", RES) is None and X.extract_price(lambda p: "{}", "o", "b", []) is None


def test_extract_rejects_prices_that_are_not_vendor_fees() -> None:
    q = {"price_usd": 349, "price_unit": "month", "source_index": 0, "quote": "Plans start at $349 per month"}
    assert X.validate(dict(q, price_kind="vendor_fee", audience="small_business"), RES)["price_kind"] == "vendor_fee"
    assert X.validate(dict(q, price_kind="vendor_fee"), RES)["price_usd"] == 349                    # audience optional
    for kind, words in (("buyer_internal_cost", "internal"), ("ad_spend", "ad spend"), ("buyer_savings", "savings"), ("other", "other")):
        r = X.validate(dict(q, price_kind=kind), RES)
        assert r == {"rejected": f"quoted figure is {kind.replace('_', ' ')}, not a vendor's fee"}, r
    assert X.validate(dict(q), RES) == {"rejected": "price kind not stated"}                       # unlabelled: not trusted
    assert X.validate(dict(q, price_kind="made_up"), RES) == {"rejected": "price kind not stated"}
    assert X.validate(dict(q, price_kind="vendor_fee", audience="enterprise"), RES) == {"rejected": "quoted figure is an enterprise price"}
    # a rejection still never leaks a price into the candidate
    c = cand("a", price_usd=500.0)
    assert G.apply(c, {"price_rejected": "quoted figure is ad spend, not a vendor's fee"})["price_usd"] == 500.0
    assert G.apply(c, {"price_rejected": "x"})["price_rejected"] == "x" and G.apply(c, {"price_rejected": "x"})["grounded"] is False


def test_savings_claims_are_not_prices() -> None:
    res = [{"title": "t", "url": "https://v.test", "snippet": "Owners may save $2,000 or more per month in direct costs."}]
    q = {"price_usd": 2000, "price_unit": "month", "source_index": 0, "quote": "save $2,000 or more per month"}
    assert X.validate(dict(q, price_kind="buyer_savings"), res) == {"rejected": "quoted figure is buyer savings, not a vendor's fee"}
    assert X.VERSION >= 3 and "buyer_savings" in X.KINDS and "buyer_savings" in X.PROMPT
    assert Q2.GROQ_PRICE_KIND["buyer_savings"] == "savings" and "savings" in {o.key for o in Q2.BY_ID["price_kind"].options}
    assert not Q2.admission_failures_v2(Q2.BY_ID["price_kind"])                                   # the new option still passes admission


def test_stale_priced_cache_entries_are_redone_for_free() -> None:
    rows = []
    for i in range(3):
        c = cand(f"offer{i} w{i}", price_usd=600.0, hours_per_account_month=5.0); c["id"] = f"v{i}"
        c["screen"] = S.screen(c); c["sector"] = "law firms"; rows.append(c)
    with tempfile.TemporaryDirectory() as d:
        g = os.path.join(d, "g")
        os.makedirs(g)
        G._write(os.path.join(g, G.key(rows[0]) + ".json"), "o0", {"price_usd": 99.0, "price_url": "https://old.test"}, v=1)   # old, priced
        G._write(os.path.join(g, G.key(rows[1]) + ".json"), "o1", {"grounded_via": "serper"}, v=1)                          # old, no price
        G._write(os.path.join(g, G.key(rows[2]) + ".json"), "o2", {"price_usd": 88.0, "price_url": "https://new.test"}, v=X.VERSION)  # current
        search = SE.CachedSearch(SE.StubSearch(), os.path.join(d, "s"), 5)
        st = G.ground_all_search(StubGroq(), search, None, rows, g, n=5, log=lambda *_: None)
        assert st["redone"] == 1 and st["called"] == 1 and st["cached"] == 2                # only the stale priced one is redone
        assert G._stale(os.path.join(g, G.key(rows[0]) + ".json")) is False                # rewritten under the current version


def test_search_chain_cache_and_budget() -> None:
    class Down:
        name = "down"
        def search(self, q, n=6): raise RuntimeError("blocked")
    class Up:
        name = "up"; calls = 0
        def search(self, q, n=6):
            self.calls += 1; return RES
    up = Up()
    chain = SE.ChainSearch([Down(), up])
    assert chain.search("q") == RES and chain.used == "up"                          # falls through a failing provider
    try:
        SE.ChainSearch([Down()]).search("q")
    except RuntimeError as exc:
        assert "all search providers failed" in str(exc)
    else:
        raise AssertionError("expected failure")
    with tempfile.TemporaryDirectory() as d:
        c = SE.CachedSearch(SE.ChainSearch([up]), d, max_searches=2)
        before = up.calls
        c.search("a"); c.search("a"); c.search("b")
        assert up.calls - before == 2 and c.fresh == 2 and c.hits == 1             # repeat is free
        try:
            c.search("c")
        except SE.SearchBudget:
            pass
        else:
            raise AssertionError("expected SearchBudget")
        assert c.search("a") == RES                                                 # cached queries still work at the cap


def test_census_parse_and_pool() -> None:
    rows = [["ESTAB", "EMPSZES", "EMPSZES_LABEL", "NAICS2017", "us"],
            ["1000", "001", "All establishments", "484", "1"],
            ["600", "212", "Establishments with less than 5 employees", "484", "1"],
            ["300", "220", "Establishments with 5 to 9 employees", "484", "1"],
            ["200", "230", "Establishments with 10 to 19 employees", "484", "1"],
            ["50", "241", "Establishments with 20 to 49 employees", "484", "1"]]
    assert CS.parse_small(rows) == 1100
    assert CS.parse_small(rows[:3]) is None                                         # a missing class is not guessed
    assert CS.parse_small([["ESTAB"], ["1"]]) is None and CS.parse_small([]) is None
    assert "key=" not in CS.url_for("484")
    os.environ["CENSUS_API_KEY"] = "k"
    try:
        with tempfile.TemporaryDirectory() as d:
            seen = []
            cen = CS.Census(d, get=lambda url: seen.append(url) or rows)
            p = cen.sector_pool("trucking and freight carriers")
            assert p["pool_count"] == 1100.0 and "key=" not in p["pool_url"] and p["pool_basis"] == "census"
            assert "upper bound" in p["pool_note"]
            two = cen.sector_pool("roofing and HVAC contractors")                   # two NAICS codes are summed
            assert two["pool_count"] == 2200.0
            n = len(seen); cen.sector_pool("trucking and freight carriers")
            assert len(seen) == n                                                   # cached
            assert cen.sector_pool("YouTube and video creators") is None            # no clean NAICS code
            assert cen.sector_pool("unknown sector") is None
    finally:
        del os.environ["CENSUS_API_KEY"]
    assert CS.make_census("live", tempfile.gettempdir()) is None                    # no key: pools stay guesses


def test_census_multi_code_citation_reverifies() -> None:
    rows = [["ESTAB", "EMPSZES", "EMPSZES_LABEL"], ["600", "212", "Establishments with less than 5 employees"],
            ["300", "220", "Establishments with 5 to 9 employees"], ["200", "230", "Establishments with 10 to 19 employees"]]
    os.environ["CENSUS_API_KEY"] = "k"
    try:
        with tempfile.TemporaryDirectory() as d:
            p = CS.Census(d, get=lambda url: rows).sector_pool("roofing and HVAC contractors")   # two codes -> 2 x 1,100
    finally:
        del os.environ["CENSUS_API_KEY"]
    assert p["pool_count"] == 2200.0 and p["pool_url"].endswith("#naics=238160,238220")
    calls = []
    memo = {}
    def get(url):
        calls.append(url); return rows
    assert CS.check_pool(p["pool_url"], 2200.0, "k", get, memo) is True                # re-sums BOTH codes
    assert CS.check_pool(p["pool_url"], 1100.0, "k", get, memo) is False               # one code's count no longer matches
    assert len(calls) == 2                                                             # memoised: 2 codes fetched once
    assert CS.check_pool(CS.url_for("484"), 1100.0, "k", lambda u: rows, {}) is True   # single-code URL still works
    def boom(u): raise RuntimeError("down")
    assert CS.check_pool(p["pool_url"], 2200.0, "k", boom, {}) is None


def test_ground_search_end_to_end_stub() -> None:
    rows = []
    for i, (price, unit) in enumerate([(750, "month"), (300, "month"), (1800, "contingency")]):
        c = cand(f"offer{i} z{i}", price_usd=float(price), price_unit=unit, hours_per_account_month=10.0)
        c["id"] = f"v{i}"; c["screen"] = S.screen(c); c["sector"] = "law firms"; rows.append(c)
    with tempfile.TemporaryDirectory() as d:
        search = SE.CachedSearch(SE.StubSearch(), os.path.join(d, "s"), max_searches=2)
        st = G.ground_all_search(StubGroq(), search, CS.StubCensus(), rows, os.path.join(d, "g"), n=10, log=lambda *_: None)
        assert st["called"] == 2 and st["priced"] == 2 and st["searches_paid"] == 2   # stopped at the cap, not past it
        st2 = G.ground_all_search(StubGroq(), SE.CachedSearch(SE.StubSearch(), os.path.join(d, "s"), 5), CS.StubCensus(),
                                  rows, os.path.join(d, "g"), n=10, log=lambda *_: None)
        assert st2["cached"] == 2 and st2["called"] == 1                             # resumed; finished the third
        merged = G.merge_cached(rows, os.path.join(d, "g"))
        assert all(m["grounded"] for m in merged)
        assert merged[0]["price_url"].startswith("https://example.invalid/p/") and merged[0]["evidence_quote"]
        assert merged[0]["pool_basis"] == "census" and merged[0]["guess"]["price_usd"] == 750.0   # original guess kept
        assert merged[0]["screen"]["verdict"] in ("SURVIVES", "FAILS_HR", "FAILS_CAP", "FAILS_POOL")


def test_pools_only_does_not_block_price_grounding() -> None:
    rows = []
    for i, sector in enumerate(("law firms", "YouTube and video creators")):
        c = cand(f"offer{i} q{i}", price_usd=500.0, hours_per_account_month=5.0, pool_count=1000.0)
        c["id"] = f"v{i}"; c["screen"] = S.screen(c); c["sector"] = sector; rows.append(c)
    with tempfile.TemporaryDirectory() as d:
        st = G.ground_pools(CS.StubCensus(), rows, os.path.join(d, "pools"), log=lambda *_: None)
        assert st["pooled"] == 1 and st["no_naics"] == 1
        assert G.ground_pools(CS.StubCensus(), rows, os.path.join(d, "pools"), log=lambda *_: None)["cached"] == 1
        mid = G.merge_cached(rows, os.path.join(d, "pools"))
        assert mid[0]["grounded_fields"] == ["pool"] and mid[1].get("grounded") is None   # no NAICS: guess untouched
        # a later price search still runs on the pool-grounded row, and the original guess survives both merges
        search = SE.CachedSearch(SE.StubSearch(), os.path.join(d, "s"), 5)
        st2 = G.ground_all_search(StubGroq(), search, None, rows, os.path.join(d, "g"), n=5, log=lambda *_: None)
        assert st2["called"] == 2
        both = G.merge_cached(rows, os.path.join(d, "pools"), os.path.join(d, "g"))
        assert both[0]["grounded_fields"] == ["pool", "price"] and both[0]["guess"]["pool_count"] == 1000.0


def test_grade_requires_price_for_a() -> None:
    page = lambda url: (200, "Plans start at $750 per month")
    pool_only = cand("a", price_url=None, pool_url="http://pool", pool_count=750.0)
    g = V.grade(pool_only, page)
    assert g["grade"] == "B" and "price is still a guess" in g["reason"]               # pool alone cannot reach A
    both = cand("a", price_url="http://p", pool_url="https://api.census.gov/x", pool_count=1100.0)
    assert V.grade(both, page, census_check=lambda u, v: True)["grade"] == "A"
    assert V.grade(both, page, census_check=lambda u, v: None)["grade"] == "A"         # price alone suffices
    census_only = cand("a", price_url=None, pool_url="https://api.census.gov/x", pool_count=1100.0)
    assert V.grade(census_only, page, census_check=lambda u, v: True)["grade"] == "B"
    assert V.grade(census_only, page, census_check=lambda u, v: False)["grade"] == "B"  # loaded, figure differs -> check by hand
    assert V.grade(census_only, page, census_check=lambda u, v: None)["grade"] == "C"
    annual = cand("a", price_usd=100.0, price_quoted=1200.0, price_url="http://p")
    assert V.grade(annual, lambda u: (200, "Billed at $1,200 a year"))["grade"] == "A"  # checks the quoted annual figure


def test_ddgs_missing_is_a_quiet_fallback() -> None:
    import builtins
    real = builtins.__import__
    def no_ddgs(name, *a, **k):
        if name == "ddgs":
            raise ImportError("no ddgs")
        return real(name, *a, **k)
    builtins.__import__ = no_ddgs
    try:
        try:
            SE.DdgsSearch()
        except RuntimeError as exc:
            assert "pip install ddgs" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        builtins.__import__ = real


def test_dedupe() -> None:
    cs = [cand("Short-form video repurposing for YouTubers"), cand("YouTube short form repurposing", price_url="http://u"),
          cand("Bookkeeping cleanup for restaurants"), cand("Roofing appointment setting")]
    u = D.dedupe(cs)
    assert len(u) == 3
    merged = [x for x in u if x["cluster_size"] == 2][0]
    assert merged["price_url"] == "http://u"  # richest record kept
    assert len({x["id"] for x in u}) == 3


def test_screen_matches_ideas_screen() -> None:
    # Rows from analysis/ideas_screen.py at the $3,000 target, base conversion 0.3%.
    short = S.screen(cand("a", price_usd=750, hours_per_account_month=10, pool_count=50000))
    assert short["verdict"] == "SURVIVES" and short["accounts"] == 4.0 and short["weeks_base"] == 13.3
    book = S.screen(cand("b", price_usd=300, hours_per_account_month=3.5, pool_count=200000))
    assert book["accounts"] == 10.0 and book["weeks_base"] == 33.3
    brokerage = S.screen(cand("c", price_usd=400, hours_per_account_month=8, pool_count=20000))
    assert brokerage["verdict"] == "FAILS_HR"
    tracker = S.screen(cand("d", price_usd=9, hours_per_account_month=0.1, pool_count=62000))
    assert tracker["verdict"] == "FAILS_POOL"
    # Accounts are whole customers (rounded up) and big prices are flagged, not failed.
    assert tracker["accounts"] == 334
    big = S.screen(cand("h", price_usd=6566, hours_per_account_month=2, pool_count=23000))
    assert big["accounts"] == 1 and big["weeks_base"] == 3.3 and big["price_flag"] is True and big["verdict"] == "SURVIVES"
    assert S.screen(cand("i", price_usd=2500, hours_per_account_month=10, pool_count=50000))["price_flag"] is False   # not above
    assert S.screen(cand("i", price_usd=2501, hours_per_account_month=10, pool_count=50000))["price_flag"] is True
    assert S.screen(cand("j", price_usd=750, hours_per_account_month=10, pool_count=50000), flag=500.0)["price_flag"] is True
    assert S.screen(cand("e", price_unit="contingency"))["verdict"] == "CONTINGENCY"
    assert S.screen(cand("f", price_unit="project"))["verdict"] == "UNIT"
    assert S.screen(cand("g", pool_count=None))["verdict"] == "INSUFFICIENT"


def test_verify_grades() -> None:
    page = lambda url: (200, "Plans start at $750 per month")
    assert V.grade(cand("a", price_url="http://p"), page)["grade"] == "A"
    assert V.grade(cand("a", price_url="http://p", price_usd=99.0), page)["grade"] == "B"
    assert V.grade(cand("a"), page)["grade"] == "C"
    assert V.grade(cand("a", price_url="http://p"), lambda u: (403, ""))["grade"] == "C"
    assert V.grade(cand("a", price_url="http://p", price_usd=75.0), lambda u: (200, "$7500"))["grade"] == "B"  # no substring hit


def test_tag_stub_and_insufficient() -> None:
    full = cand("a"); full["id"] = "v0"
    thin = cand("b", evidence={k: "" for k in H.EVIDENCE_KEYS}); thin["id"] = "v1"
    tags = T.tag_all([full, thin], "stub")
    assert tags["v0"]["status"] == "ok" and set(tags["v0"]["answers"]) and 0 <= tags["v0"]["escape_rate"] <= 1
    assert tags["v1"]["status"] == "insufficient_evidence"


def test_shortlist_requires_grade_ab() -> None:
    def row(i, grade, off=None):
        c = cand(off or f"o{i}"); c["id"] = f"v{i}"; c["screen"] = S.screen(c); c["verify"] = {"grade": grade, "reason": "r"}
        return c
    rows = [row(0, "C"), row(1, "B"), row(2, "A")]
    top = R.shortlist(rows)
    assert [r["id"] for r in top] == ["v2", "v1"]  # grade C excluded, A before B


def test_shortlist_excludes_flagged_prices() -> None:
    def row(i, price):
        c = cand(f"o{i} k{i}", price_usd=float(price), hours_per_account_month=10.0); c["id"] = f"v{i}"
        c["screen"] = S.screen(c); c["verify"] = {"grade": "A", "reason": "r"}; return c
    rows = [row(0, 6000), row(1, 750)]
    assert rows[0]["screen"]["verdict"] == "SURVIVES" and rows[0]["screen"]["price_flag"]
    assert [r["id"] for r in R.shortlist(rows)] == ["v1"]                                           # the $6,000 offer is kept off
    assert "flagged as enterprise-scale" in R.report(rows, 1, 2, [], stub=False)


def test_question_bank_v2_admission_and_state() -> None:
    assert [q.id for q in Q2.ADMITTED_V2] == ["price_kind", "audience", "regulated_work", "delivery_model", "access_channel"]
    from vstress.questions import Question, _opt, _escape
    for bad in (Question("b1", "price", "How many months per seat?", "quote", "", (_opt("a", "A fee not paid", 1.0), _opt("b", "Another thing", 0.0), _escape())),
                Question("b2", "price", "What kind of amount?", "no_such_field", "", (_opt("a", "A fee", 1.0), _opt("b", "A cost", 0.0), _escape()))):
        assert Q2.admission_failures_v2(bad)                                       # the rules still bite
    assert all(sum(1 for o in q.options if o.escape) == 1 for q in Q2.ADMITTED_V2)
    c = cand("Offer A", evidence_quote="Plans start at $99", task="t", blockers="b", channel="c"); c["id"] = "v1"
    st = Q2.build_state_v2(c)
    assert st["quote"] == "Plans start at $99" and st["regulated_text"] == "t | b" and st["offer_text"] == "Offer A | t"
    assert {q.id for q in Q2.applicable(st)} == {q.id for q in Q2.ADMITTED_V2}
    c2 = dict(c, evidence_quote=None, channel=""); st2 = Q2.build_state_v2(c2)
    assert {q.id for q in Q2.applicable(st2)} == {"regulated_work", "delivery_model"}   # no quote / channel -> those questions skipped


def test_tag_v2_stability_catches_position_bias() -> None:
    import discovery.tag as Tm
    from vstress.mapping import Answer

    class Careful:          # answers by meaning, whatever the option order
        def ask(self, state, questions):
            return {q.id: Answer(next(o.key for o in q.options if o.key in ("vendor", "small", "plain", "service", "direct")), 0.9)
                    if any(o.key in ("vendor", "small", "plain", "service", "direct") for o in q.options) else Answer("escape", 0.5)
                    for q in questions}

    class FirstListed:      # position-biased: always picks whichever option is listed first
        def ask(self, state, questions):
            return {q.id: Answer(q.options[0].key, 0.9) for q in questions}

    real = Tm.make_provider
    rows = []
    for i in range(12):
        c = cand(f"o{i} p{i}", evidence_quote="Plans start at $99 a month", task="t", blockers="b", channel="c"); c["id"] = f"v{i}"; rows.append(c)
    try:
        Tm.make_provider = lambda name, seed=0: Careful()
        good = Tm.tag_v2(rows, "live", log=lambda *_: None)
        assert all(t["status"] == "ok" and all(t["stable"].values()) for t in good.values())
        assert good["v0"]["final"]["price_kind"] == "vendor"
        Tm.make_provider = lambda name, seed=0: FirstListed()
        biased = Tm.tag_v2(rows, "live", log=lambda *_: None)
        unstable = sum(1 for t in biased.values() for v in t["final"].values() if v == "unstable")
        assert unstable > 0                                    # shuffling exposes the bias
        # an unstable answer is never usable by the removal gate
        assert all(R.jev_reason(t, {"price_kind", "audience"}) == "" for t in biased.values() if "unstable" in t["final"].values()
                   and t["final"].get("price_kind") == "unstable" and t["final"].get("audience") == "unstable")
    finally:
        Tm.make_provider = real
    one = cand("Bare offer", task="", blockers="", channel="", evidence_quote=None); one["id"] = "v9"
    out = Tm.tag_v2([one], "stub", log=lambda *_: None)
    assert out["v9"]["status"] == "ok" and set(out["v9"]["final"]) == {"delivery_model"}   # only the questions with input are asked


def test_jev_gate_only_demotes_and_only_through_validated_questions() -> None:
    ok = lambda **f: {"status": "ok", "final": f, "stable": {k: True for k in f}, "runs": []}
    trusted = {"price_kind", "audience"}
    assert "buyer's own cost" in R.jev_reason(ok(price_kind="internal"), trusted)
    assert "ad budget" in R.jev_reason(ok(price_kind="ads"), trusted)
    assert "buyer saving" in R.jev_reason(ok(price_kind="savings"), trusted)
    assert "large-company" in R.jev_reason(ok(audience="large"), trusted)
    assert R.jev_reason(ok(price_kind="vendor", audience="small"), trusted) == ""           # agreement removes nothing
    for quiet in ("escape", "unstable"):
        assert R.jev_reason(ok(price_kind=quiet, audience=quiet), trusted) == ""             # no answer is not a verdict
    assert R.jev_reason(ok(price_kind="internal"), set()) == ""                              # question not validated: no effect
    assert R.jev_reason(ok(price_kind="internal"), {"audience"}) == ""
    assert R.jev_reason({"status": "error"}, trusted) == "" and R.jev_reason({}, trusted) == ""
    rows = [dict(cand("a b"), id="v1", screen={"verdict": "SURVIVES"}), dict(cand("c d"), id="v2", screen={"verdict": "FAILS_HR"})]
    out = R.apply_jev_gate(rows, {"v1": ok(price_kind="internal"), "v2": ok(price_kind="vendor")}, trusted)
    assert out[0]["jev_removed"] and "jev_removed" not in out[1]
    assert out[1]["screen"] == {"verdict": "FAILS_HR"} and out[0]["screen"] == {"verdict": "SURVIVES"}   # verdicts untouched: demote only
    assert "tags2" in out[0] and rows[0].get("jev_removed") is None                                     # inputs not mutated
    assert R.shortlist([dict(out[0], verify={"grade": "A", "reason": "r"}, price_usd=500.0, hours_per_account_month=5.0,
                              screen=S.screen(cand("a b", price_usd=500.0, hours_per_account_month=5.0)))]) == []


def test_tagcheck_scoring_and_thresholds() -> None:
    def item(i, price_label, aud_label):
        r = {"id": f"p{i}", "offer": "", "evidence_quote": "q"}
        return (r, {"price_kind": price_label, "audience": aud_label})
    def tg(price, aud, stable=True, runs=None):
        return {"status": "ok", "final": {"price_kind": price, "audience": aud}, "stable": {"price_kind": stable, "audience": stable},
                "runs": runs or [{"price_kind": [price, .9], "audience": [aud, .9]}] * 2}
    labels = ["vendor", "vendor", "internal", "internal", "ads", "vendor"]
    auds = ["small", "small", "small", "small", "small", "large"]
    items = [item(i, l, a) for i, (l, a) in enumerate(zip(labels, auds))] + [item(6, "vendor", "large"), item(7, "vendor", "large")]
    perfect = {f"p{i}": tg(*(l, a)) for i, (l, a) in enumerate(zip(labels + ["vendor", "vendor"], auds + ["large", "large"]))}
    res = TC.score(items, perfect)
    assert res["price_kind"]["keep"] and res["price_kind"]["gold_agreement"] == 1.0 and res["price_kind"]["demoting_recall"] == 1.0
    assert res["audience"]["keep"] and res["audience"]["demoting_gold"] == 3
    # a model that calls everything a vendor fee misses every demoting class
    lazy = {k: tg("vendor", "small") for k in perfect}
    assert TC.score(items, lazy)["price_kind"]["keep"] is False and TC.score(items, lazy)["price_kind"]["demoting_recall"] == 0.0
    # a model that demotes everything wrongly demotes labelled-fine items: cut, even though it "finds" the bad ones
    harsh = {k: tg("internal", "large") for k in perfect}
    r = TC.score(items, harsh)
    assert r["price_kind"]["wrongly_demoted"] == 5 and not r["price_kind"]["keep"]   # five vendor-labelled items
    assert any("wrongly demote" in w for w in r["price_kind"]["why_cut"])
    # unstable answers fail the stability bar
    shaky = {k: tg("vendor", "small", stable=False) for k in perfect}
    assert any("stability" in w for w in TC.score(items, shaky)["price_kind"]["why_cut"])
    # too few examples of a demoting class: removal cannot be validated
    few = TC.score(items[:2] + items[5:6], {k: v for k, v in perfect.items() if k in ("p0", "p1", "p5")})
    assert any("too few demoting-class" in w for w in few["price_kind"]["why_cut"])
    assert TC.trusted(None) == set() and TC.trusted({"questions": {"a": {"keep": True}, "b": {"keep": False}}}) == {"a"}


def test_gold_file_is_well_formed() -> None:
    doc = TC.load_gold()
    for g in doc["labels"].values():
        for qid, ans in g["labels"].items():
            assert qid in Q2.BY_ID and ans in {o.key for o in Q2.BY_ID[qid].options}, (qid, ans)
    ids = [p["id"] for p in doc["probes"]]
    assert len(ids) == len(set(ids))
    for p in doc["probes"]:
        for qid, ans in p["labels"].items():
            assert ans in {o.key for o in Q2.BY_ID[qid].options}
    assert sum(1 for p in doc["probes"] if p["labels"].get("audience") == "large") >= 3     # enough to validate removal
    assert sum(1 for p in doc["probes"] if p["labels"].get("price_kind") in ("internal", "ads")) >= 3
    assert sum(1 for p in doc["probes"] if p["labels"].get("price_kind") == "savings") >= 3     # the savings option is validated too
    items = TC.gold_items(doc, [])
    assert len(items) == len(doc["probes"]) and all(r["evidence_quote"] for r, _ in items)


def test_dashboard_jev_section_data() -> None:
    qs = seeds.build_queries(6)
    with tempfile.TemporaryDirectory() as d:
        H.harvest(StubGroq(), qs, os.path.join(d, "cache"), log=lambda *_: None)
        data0 = DB.collect(d, stub=True)
        assert data0["jev"]["tagged"] == 0 and data0["jev"]["removed"] == [] and data0["jev"]["trusted"] == []
        rows = data0["rows"][:3]
        ok = lambda **f: {"status": "ok", "final": f, "stable": {k: True for k in f}, "runs": []}
        json.dump({r["id"]: ok(price_kind="internal") for r in rows}, open(os.path.join(d, "tags_v2.json"), "w"))
        data1 = DB.collect(d, stub=True)
        assert data1["jev"]["tagged"] == 3 and data1["jev"]["removed"] == []             # tagged but no quality check: removes nothing
        json.dump({"thresholds": TC.THRESHOLDS, "items": 5, "provider": "stub", "questions": {"price_kind": {"keep": True, "why_cut": [], "tagged": 5}}},
                  open(os.path.join(d, "tagcheck.json"), "w"))
        data2 = DB.collect(d, stub=True)
        assert data2["jev"]["trusted"] == ["price_kind"] and len(data2["jev"]["removed"]) == sum(1 for r in data2["rows"] if r["screen"]["verdict"] == "SURVIVES" and r.get("jev_removed"))
        page = DB.render(data2)
        assert "jevSection" in page and page.count("</script>") == 1


def test_end_to_end_stub() -> None:
    qs = seeds.build_queries(30)
    with tempfile.TemporaryDirectory() as d:
        H.harvest(StubGroq(), qs, d, log=lambda *_: None)
        raw = H.load_cached(d, qs)
        unique = D.dedupe(raw)
        assert 0 < len(unique) <= len(raw)
        rows = [dict(c, screen=S.screen(c)) for c in unique]
        for r in rows:
            if r["screen"]["verdict"] == "SURVIVES":
                r["verify"] = V.grade(r, V.stub_fetch)
        text = R.report(rows, len(qs), len(raw), D.saturation(unique, len(qs)), stub=True)
        assert "STUB RUN" in text and "## Shortlist" in text


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

if __name__ == "__main__":
    for t in TESTS:
        t()
    print(f"{len(TESTS)} discovery tests passed")
