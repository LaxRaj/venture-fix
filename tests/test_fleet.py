"""Fleet tests.  Run with: python3 -I tests/test_fleet.py   (offline; uses the stub provider)"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fleet import money, qa
from fleet.llm import TIERS, Provider, Reply
from fleet.orchestrator import BudgetExceeded, Fleet
from fleet.store import Store
from fleet.stub import StubProvider

V = {"id": "v1", "offer": "Claim Filing Assistant", "buyer": "dropship suppliers", "price_usd": 800.0, "price_unit": "month"}
ADDR = "1 Main St, Springfield"


def fleet(provider=None, budget=10**9):
    s = Store(":memory:")
    s.seed_ventures([V])
    s.set_setting("sender_address", ADDR)
    return s, Fleet(s, provider or StubProvider(), token_budget=budget)


def test_escalation_after_qa_rejection():
    s, f = fleet()
    f.run_cycle("v1")
    land = s.one("select * from tasks where kind='landing'")
    assert land["status"] == "done" and land["tier"] == 1, land  # tier-0 stub forgets the price; QA escalates to sonnet
    hist = s.q("select tier, ok from attempts where task_id=? order by id", (land["id"],))
    assert [h["tier"] for h in hist] == [0, 0, 1] and [h["ok"] for h in hist] == [0, 0, 1], hist


def test_plan_comes_from_heavy_model_and_cheap_tasks_stay_cheap():
    s, f = fleet()
    f.run_cycle("v1")
    research = s.one("select * from tasks where kind='research'")
    assert research["tier"] == 0  # passed QA on the cheapest model: never upgraded
    assert s.one("select count(*) n from attempts where task_id is null and tier=2")["n"] >= 1  # plan + review at the top tier


def test_outreach_waits_for_address_and_prospects():
    s = Store(":memory:"); s.seed_ventures([V])
    f = Fleet(s, StubProvider())
    f.run_cycle("v1")
    t = s.one("select * from tasks where kind='outreach'")
    assert t["status"] == "waiting" and "postal address" in t["note"]
    s.set_setting("sender_address", ADDR)
    f.run_cycle("v1")
    assert "import prospects" in s.one("select note from tasks where kind='outreach'")["note"]


def test_drafts_never_send_without_approval():
    s, f = fleet()
    money.OUTBOX = __import__("pathlib").Path(os.environ.get("TMPDIR", "/tmp")) / f"outbox-{time.time()}"
    assert money.import_prospects(s, "v1", "Ann,Acme Supply,ann@acme.test\nbad line") == 1
    f.run_cycle("v1")
    a = s.one("select * from approvals")
    assert a["status"] == "pending" and not money.OUTBOX.exists()
    ok, msg = money.approve(s, a["id"])
    assert ok and msg.startswith("exported"), msg
    assert len(list(money.OUTBOX.glob("*.eml"))) == 1


def test_approve_reruns_qa_on_edits():
    s, f = fleet()
    money.import_prospects(s, "v1", "Ann,Acme Supply,ann@acme.test")
    f.run_cycle("v1")
    a = s.one("select * from approvals")
    ok, msg = money.approve(s, a["id"], "We guarantee 100% results for Acme Supply. " * 4)
    assert not ok and "QA" in msg
    assert s.one("select status from approvals")["status"] == "pending"


def test_unsubscribe_suppresses_everywhere():
    s, f = fleet()
    money.import_prospects(s, "v1", "Ann,Acme Supply,ann@acme.test")
    f.run_cycle("v1")
    pid = s.one("select id from prospects")["id"]
    money.inbound(s, pid, "Please remove me from your list")
    assert s.one("select status from prospects")["status"] == "unsubscribed"
    assert s.one("select status from approvals")["status"] == "rejected"
    assert money.import_prospects(s, "v1", "Ann,Acme Supply,ann@acme.test") == 0


def test_reply_gets_followup_draft():
    s, f = fleet()
    money.import_prospects(s, "v1", "Ann,Acme Supply,ann@acme.test")
    f.run_cycle("v1")
    money.approve(s, s.one("select id from approvals")["id"])
    money.inbound(s, s.one("select id from prospects")["id"], "Interesting, how does the pilot work?")
    f.run_cycle("v1")
    assert s.one("select count(*) n from approvals where kind='followup' and status='pending'")["n"] == 1


def test_daily_cap():
    s, f = fleet()
    old = money.DAILY_SEND_CAP
    money.DAILY_SEND_CAP = 0
    try:
        money.import_prospects(s, "v1", "Ann,Acme Supply,ann@acme.test")
        f.run_cycle("v1")
        ok, msg = money.approve(s, s.one("select id from approvals")["id"])
        assert not ok and "cap" in msg
    finally:
        money.DAILY_SEND_CAP = old


def test_stripe_signature_and_idempotency():
    s, _ = fleet()
    os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
    ev = json.dumps({"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {
        "client_reference_id": "v1", "payment_status": "paid", "amount_total": 80000, "customer_details": {"email": "a@b.c"}}}}).encode()
    t = str(int(time.time()))
    sig = hmac.new(b"whsec_test", t.encode() + b"." + ev, hashlib.sha256).hexdigest()
    assert money.stripe_event(s, ev, f"t={t},v1={sig}") == (200, "ok")
    assert money.stripe_event(s, ev, f"t={t},v1={sig}") == (200, "ok")  # replay is a no-op
    assert s.one("select sum(cents) n from ledger")["n"] == 80000
    assert money.stripe_event(s, ev, f"t={t},v1={'0' * 64}")[0] == 400
    assert money.stripe_event(s, ev, f"t={int(t) - 3600},v1={hmac.new(b'whsec_test', str(int(t) - 3600).encode() + b'.' + ev, hashlib.sha256).hexdigest()}")[0] == 400
    assert money.stripe_event(s, ev, "")[0] == 400


def test_budget_stops_the_fleet():
    s, f = fleet(budget=1)
    f.run_cycle("v1")  # first call goes through, then the cap trips
    r = f.run_cycle("v1")
    assert r.get("stopped"), r


def test_model_errors_do_not_burn_the_ladder():
    class Down(Provider):
        name = "down"
        def complete(self, **kw):
            raise RuntimeError("HTTP 500")
    s, f = fleet(Down())
    r = f.run_cycle("v1")
    assert "error" in r  # planning needs the orchestrator; with it down nothing is attempted
    assert s.one("select count(*) n from tasks")["n"] == 0


def test_qa_gates():
    ctx = {"sender_address": ADDR, "prospect_company": "Acme", "price_display": "$800/mo"}
    good = json.dumps({"subject": "Quick question about Acme", "body": "Hi, I help suppliers file marketplace claims faster. Acme may still do this by hand. A one-month pilot is $800/mo and the first sample is free. Worth a short call? Reply STOP to opt out. " + ADDR})
    assert qa.gate("outreach", good, ctx) == []
    assert qa.gate("outreach", good.replace("Reply STOP to opt out. ", ""), ctx)
    assert qa.gate("outreach", good.replace("Acme", "Zed"), {**ctx})  # not personalised
    assert qa.gate("outreach", good, {**ctx, "sender_address": ""})
    assert qa.gate("tool", "import subprocess\nsubprocess.run(['ls'])", ctx)
    assert qa.gate("tool", "def f(:", ctx)
    assert qa.gate("landing", "<html><head><title>x</title></head><body><h1>x</h1><script>1</script></body></html>", ctx)
    assert qa.gate("plan", json.dumps([{"kind": "research", "title": "a", "brief": "b"}] * 3), ctx)  # no landing/outreach
    page = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Video Testimonial Repurposing</title></head><body><h1>Video Testimonial Repurposing</h1>'
            '<p>$800/mo</p><a href="#pay">Start</a>%s</body></html>')
    assert qa.gate("landing", page % "", ctx) == []  # regression: the word "testimonial" alone must not trip QA
    assert qa.gate("landing", page % '<p>"We doubled our bookings in a month" - Dana R.</p>', ctx)  # attributed quote is fabricated proof
    assert qa.gate("landing", page % "<p>See what our clients say</p>", ctx)


def test_publish_landing_tags_checkout_with_venture():
    s, f = fleet()
    money.SITE = __import__("pathlib").Path(os.environ.get("TMPDIR", "/tmp")) / f"site-{time.time()}"
    f.run_cycle("v1")
    s.x("update ventures set payment_link=? where id='v1'", ("https://buy.stripe.com/abc",))
    html = open(money.publish_landing(s, "v1")).read()
    assert "https://buy.stripe.com/abc?client_reference_id=v1" in html


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("ok", name)
    print(f"{n} passed")
