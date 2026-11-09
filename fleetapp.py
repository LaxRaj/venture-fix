#!/usr/bin/env python3
"""Agent-fleet web app.  Stdlib only.

    python3 fleetapp.py                      # stub provider unless ANTHROPIC_API_KEY is set
    python3 fleetapp.py --auto 600 --top 3   # run a cycle for the top 3 ventures every 10 minutes
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from fleet import money
from fleet.llm import ORCH_MODEL, TIERS, make_provider
from fleet.orchestrator import Fleet, price_display
from fleet.store import Store

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "web" / "fleet.html"
RUN_LOCK = threading.Lock()
STATE = {"running": False, "last": None, "paused_until": 0.0}
PAUSE_SECONDS = 3600  # after a provider rate limit / token budget stop, automatic cycles wait this long
PUBLIC_GET = ("/site/",)  # landing pages are meant for the world; "/" is only the (data-free) page shell


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


def token_ok(supplied: str, expected: str) -> bool:
    return bool(expected) and bool(supplied) and hmac.compare_digest(supplied.encode(), expected.encode())


def load_seed(store: Store, top: int) -> None:
    rows = json.loads((ROOT / "ventures_seed.json").read_text())
    store.seed_ventures(rows)
    # Focus beats spreading: only the first `top` ventures start active.
    ids = [r["id"] for r in rows]
    for i, vid in enumerate(ids):
        if store.one("select count(*) n from tasks where venture_id=?", (vid,))["n"] == 0:
            store.x("update ventures set status=? where id=?", ("active" if i < top else "parked", vid))


def overview(s: Store, fleet: Fleet) -> dict:
    vs = []
    for v in s.q("select * from ventures order by rowid"):
        d = json.loads(v["data"])
        t = s.q("select status, count(*) n from tasks where venture_id=? group by status", (v["id"],))
        vs.append({"id": v["id"], "offer": d["offer"], "buyer": d["buyer"], "price": price_display(d), "status": v["status"],
                   "payment_link": v["payment_link"], "tasks": {r["status"]: r["n"] for r in t},
                   "pending_approvals": s.one("select count(*) n from approvals where venture_id=? and status='pending'", (v["id"],))["n"],
                   "prospects": s.one("select count(*) n from prospects where venture_id=?", (v["id"],))["n"],
                   "cash_cents": fleet.cash(v["id"])})
    return {"ventures": vs, "provider": fleet.p.name, "models": {"orchestrator": ORCH_MODEL, "tiers": TIERS},
            "tokens_today": s.tokens_today(), "token_budget": fleet.budget, "sent_today": money.sent_today(s),
            "send_cap": money.DAILY_SEND_CAP, "running": STATE["running"], "last": STATE["last"],
            "paused_until": STATE["paused_until"] if STATE["paused_until"] > time.time() else 0,
            "cash_cents": sum(v["cash_cents"] for v in vs),
            "settings": {k: s.setting(k) for k in ("sender_name", "sender_address", "sender_email")}}


def detail(s: Store, vid: str) -> dict:
    tasks = s.q("select * from tasks where venture_id=? order by ord", (vid,))
    for t in tasks:
        t["history"] = s.q("select tier,model,ok,issues,tokens_in+tokens_out tokens from attempts where task_id=? order by id", (t["id"],))
        a = s.one("select body,tier from artifacts where task_id=? order by id desc limit 1", (t["id"],))
        t["artifact"] = a
    return {"tasks": tasks, "venture": s.venture(vid),
            "prospects": s.q("select * from prospects where venture_id=? order by id", (vid,)),
            "approvals": s.q("select a.*, p.company, p.email from approvals a left join prospects p on p.id=a.prospect_id where a.venture_id=? order by a.id desc limit 60", (vid,)),
            "ledger": s.q("select * from ledger where venture_id=? order by id desc", (vid,)),
            "events": s.q("select * from events where venture_id=? order by id desc limit 40", (vid,))}


def run_async(fleet: Fleet, vid: str | None) -> bool:
    if not RUN_LOCK.acquire(blocking=False):
        return False

    def go() -> None:
        STATE["running"] = True
        try:
            res = [fleet.run_cycle(vid)] if vid else fleet.run_all()
            STATE["last"] = {"at": time.time(), "result": res}
            if any(r.get("stopped") for r in res):  # free tier or token budget exhausted: let automatic cycles back off
                STATE["paused_until"] = time.time() + PAUSE_SECONDS
        except Exception:  # noqa: BLE001
            STATE["last"] = {"at": time.time(), "error": traceback.format_exc(limit=3)}
        finally:
            STATE["running"] = False
            RUN_LOCK.release()

    threading.Thread(target=go, daemon=True).start()
    return True


def make_handler(s: Store, fleet: Fleet, admin_token: str = ""):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a) -> None:  # noqa: D401
            pass

        def _authed(self) -> bool:
            """No token configured means loopback-only mode (main() refuses a public bind without one)."""
            if not admin_token:
                return True
            bearer = self.headers.get("Authorization", "")
            if bearer.startswith("Bearer ") and token_ok(bearer[7:], admin_token):
                return True
            for part in self.headers.get("Cookie", "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == "fleet_token" and token_ok(v, admin_token):
                    return True
            return False

        def _send(self, payload, status=200, ctype="application/json", headers=()) -> None:
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            for k, v in headers:
                self.send_header(k, v)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if "text" in ctype else ""))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                return self._send(PAGE.read_bytes(), ctype="text/html")
            if path.startswith("/site/"):
                parts = path.split("/")
                f = money.SITE / (parts[2] if len(parts) > 2 else "") / "index.html"
                if f.resolve().parent.parent == money.SITE.resolve() and f.exists():
                    return self._send(f.read_bytes(), ctype="text/html")
                return self._send({"error": "not found"}, 404)
            if not self._authed():
                return self._send({"error": "unauthorized"}, 401)
            if path == "/api/state":
                return self._send(overview(s, fleet))
            if path.startswith("/api/venture/"):
                return self._send(detail(s, path.rsplit("/", 1)[1]))
            self._send({"error": "not found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if path == "/webhook/stripe":
                code, msg = money.stripe_event(s, raw, self.headers.get("Stripe-Signature", ""))
                return self._send({"result": msg}, code)
            try:
                b = json.loads(raw or b"{}")
            except ValueError:
                return self._send({"error": "bad json"}, 400)
            if path == "/login":
                if not token_ok(str(b.get("token", "")), admin_token):
                    return self._send({"error": "wrong token"}, 401)
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                cookie = f"fleet_token={admin_token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000{secure}"
                return self._send({"ok": True}, headers=[("Set-Cookie", cookie)])
            if not self._authed():
                return self._send({"error": "unauthorized"}, 401)
            try:
                self._send(self.route(path, b))
            except Exception as exc:  # noqa: BLE001
                self._send({"error": str(exc)}, 400)

        def route(self, path: str, b: dict) -> dict:
            if path == "/api/run":
                return {"started": run_async(fleet, b.get("venture_id"))}
            if path == "/api/settings":
                for k in ("sender_name", "sender_address", "sender_email"):
                    if k in b:
                        s.set_setting(k, str(b[k]).strip())
                return {"ok": True}
            if path == "/api/venture/status":
                s.x("update ventures set status=? where id=?", ("active" if b["active"] else "parked", b["venture_id"]))
                return {"ok": True}
            if path == "/api/venture/payment_link":
                link = str(b.get("link", "")).strip()
                if link and not link.startswith("https://"):
                    raise ValueError("payment link must be an https URL (create a Stripe Payment Link)")
                s.x("update ventures set payment_link=? where id=?", (link, b["venture_id"]))
                return {"published": money.publish_landing(s, b["venture_id"])}
            if path == "/api/publish":
                return {"published": money.publish_landing(s, b["venture_id"])}
            if path == "/api/prospects/import":
                return {"imported": money.import_prospects(s, b["venture_id"], b["csv"])}
            if path == "/api/approve":
                if b.get("action") == "reject":
                    money.reject(s, int(b["id"]))
                    return {"ok": True}
                ok, msg = money.approve(s, int(b["id"]), b.get("body"))
                return {"ok": ok, "message": msg}
            if path == "/api/reply":
                money.inbound(s, int(b["prospect_id"]), b["body"])
                return {"ok": True}
            if path == "/api/revenue":
                ok = money.record_revenue(s, b["venture_id"], int(round(float(b["dollars"]) * 100)), "manual", f"manual-{time.time()}", b.get("note", ""))
                return {"ok": ok}
            if path == "/api/task/reset":
                s.x("update tasks set status='pending',attempts=0,tier=0,note='' where id=?", (int(b["id"]),))
                return {"ok": True}
            raise ValueError("unknown route")

    return H


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 only with FLEET_ADMIN_TOKEN set (put Caddy in front for HTTPS)")
    ap.add_argument("--require-token", action="store_true",
                    help="exit unless FLEET_ADMIN_TOKEN is set; use behind a reverse proxy, where the bind is loopback but the world can reach it")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--db", default=str(ROOT / "runs" / "fleet.db"))
    ap.add_argument("--provider", choices=["anthropic", "openai", "stub"],
                    help="openai = any OpenAI-compatible endpoint via FLEET_BASE_URL (Ollama is free)")
    ap.add_argument("--top", type=int, default=3, help="ventures that start active")
    ap.add_argument("--auto", type=int, default=0, help="seconds between automatic cycles (0 = manual)")
    ap.add_argument("--budget", type=int, default=400_000, help="tokens per rolling 24h")
    a = ap.parse_args()
    try:
        from run import _load_dotenv
        _load_dotenv()
    except Exception:  # noqa: BLE001
        pass
    token = os.environ.get("FLEET_ADMIN_TOKEN", "")
    if (a.require_token or not is_loopback(a.host)) and len(token) < 16:
        raise SystemExit("refusing to listen on a public address without FLEET_ADMIN_TOKEN (16+ characters): "
                         "every /api route can approve emails and record revenue")
    s = Store(a.db)
    load_seed(s, a.top)
    fleet = Fleet(s, make_provider(a.provider), token_budget=a.budget)
    if a.auto:
        def loop() -> None:
            while True:
                if time.time() >= STATE["paused_until"]:  # backing off after a rate limit
                    run_async(fleet, None)
                time.sleep(a.auto)
        threading.Thread(target=loop, daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(s, fleet, token))
    print(f"fleet on http://{a.host}:{a.port}  provider={fleet.p.name}  orchestrator={ORCH_MODEL}  tiers={TIERS}  auth={'token' if token else 'none (loopback)'}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
