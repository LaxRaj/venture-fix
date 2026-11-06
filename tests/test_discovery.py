"""Offline tests for the discovery pipeline.  Run with: python3 -I test_discovery.py"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from discovery import dedupe as D, ground as G, harvest as H, rank as R, screen as S, seeds, tag as T, verify as V
from discovery.groq_client import StubGroq, extract_json_list, extract_json_object, GroqProvider, DailyLimit, wait_seconds


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
        g.exhausted.add("openai/gpt-oss-120b")
        try:
            g.ask("q")
        except DailyLimit:
            pass
        else:
            raise AssertionError("expected DailyLimit")
    finally:
        Gm._post_json = real
        del os.environ["GROQ_API_KEY"]; del os.environ["GROQ_MODELS"]


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
