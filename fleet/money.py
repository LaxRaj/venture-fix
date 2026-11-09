"""Everything that touches a real person or real money.

- Outbound email only leaves through approve(): a human approved this exact text, QA re-runs on it,
  suppressed addresses are refused, and a daily cap applies.
- Revenue enters the ledger only from a signature-verified Stripe webhook or a manual entry.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import qa
from .store import Store

DAILY_SEND_CAP = int(os.environ.get("FLEET_DAILY_SEND_CAP", "20"))
ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "runs" / "outbox"
SITE = ROOT / "runs" / "site"


def sent_today(s: Store) -> int:
    return s.one("select count(*) n from approvals where status in ('sent','exported') and ts>?", (time.time() - 86400,))["n"]


def approve(s: Store, approval_id: int, edited_body: Optional[str] = None) -> Tuple[bool, str]:
    a = s.one("select * from approvals where id=?", (approval_id,))
    if not a or a["status"] != "pending":
        return False, "not pending"
    pr = s.one("select * from prospects where id=?", (a["prospect_id"],))
    if not pr or pr["status"] == "unsubscribed" or not pr["email"]:
        return False, "prospect missing, has no email, or unsubscribed"
    body = edited_body if edited_body is not None else a["body"]
    ctx = {"sender_address": s.setting("sender_address"), "prospect_company": pr["company"]}
    issues = qa.gate("outreach", json.dumps({"subject": a["subject"], "body": body}), ctx)
    if issues:
        return False, "QA re-check failed: " + "; ".join(issues)
    if sent_today(s) >= DAILY_SEND_CAP:
        return False, f"daily send cap ({DAILY_SEND_CAP}) reached"
    status, detail = _deliver(s, pr["email"], a["subject"], body)
    s.x("update approvals set status=?,body=?,ts=? where id=?", (status, body, time.time(), approval_id))
    s.x("update prospects set status='contacted' where id=? and status in ('drafted','reply_drafted','replied')", (pr["id"],))
    s.x("insert into messages(venture_id,prospect_id,direction,body,ts) values(?,?,?,?,?)", (a["venture_id"], pr["id"], "out", body, time.time()))
    s.log(a["venture_id"], f"{status}: email to {pr['company']} ({detail})")
    return True, f"{status}: {detail}"


def _deliver(s: Store, to: str, subject: str, body: str) -> Tuple[str, str]:
    host, user, pw = os.environ.get("FLEET_SMTP_HOST"), os.environ.get("FLEET_SMTP_USER"), os.environ.get("FLEET_SMTP_PASS")
    msg = EmailMessage()
    msg["To"], msg["Subject"] = to, subject
    msg["From"] = os.environ.get("FLEET_SMTP_FROM", user or s.setting("sender_email") or "me@example.invalid")
    msg["List-Unsubscribe"] = f"<mailto:{msg['From']}?subject=STOP>"
    msg.set_content(body)
    if host and user and pw:
        with smtplib.SMTP(host, int(os.environ.get("FLEET_SMTP_PORT", "587")), timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.send_message(msg)
        return "sent", "via smtp"
    OUTBOX.mkdir(parents=True, exist_ok=True)
    path = OUTBOX / f"{int(time.time() * 1000)}-{re.sub(r'[^a-z0-9]+', '-', to.lower())}.eml"
    path.write_bytes(bytes(msg))
    return "exported", f"no SMTP configured; wrote {path.name} for you to send"


def reject(s: Store, approval_id: int) -> None:
    s.x("update approvals set status='rejected' where id=? and status='pending'", (approval_id,))


def inbound(s: Store, prospect_id: int, body: str) -> None:
    """Record a prospect's reply.  STOP-style replies suppress the address permanently."""
    pr = s.one("select * from prospects where id=?", (prospect_id,))
    if not pr:
        return
    s.x("insert into messages(venture_id,prospect_id,direction,body,ts) values(?,?,?,?,?)", (pr["venture_id"], prospect_id, "in", body, time.time()))
    if re.search(r"\b(stop|unsubscribe|remove me|not interested|do not contact)\b", body, re.I):
        s.x("update prospects set status='unsubscribed' where id=?", (prospect_id,))
        s.x("update approvals set status='rejected' where prospect_id=? and status='pending'", (prospect_id,))
    else:
        s.x("update prospects set status='replied' where id=?", (prospect_id,))


def import_prospects(s: Store, vid: str, csv_text: str) -> int:
    n = 0
    for line in csv_text.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3 or "@" not in parts[2]:
            continue
        if s.one("select id from prospects where email=? and status='unsubscribed'", (parts[2].lower(),)):
            continue  # global suppression
        try:
            s.x("insert into prospects(venture_id,name,company,email,note) values(?,?,?,?,?)", (vid, parts[0], parts[1], parts[2].lower(), ",".join(parts[3:])))
            n += 1
        except Exception:  # noqa: BLE001 - duplicate (venture,email)
            pass
    return n


# ---- revenue ----------------------------------------------------------------
def record_revenue(s: Store, vid: str, cents: int, source: str, ref: str, note: str = "") -> bool:
    if s.one("select id from ledger where ref=?", (ref,)):
        return False
    s.x("insert into ledger(venture_id,cents,source,ref,note,ts) values(?,?,?,?,?,?)", (vid, cents, source, ref, note, time.time()))
    s.log(vid, f"REVENUE ${cents / 100:,.2f} via {source}")
    return True


def verify_stripe(payload: bytes, header: str, secret: str, now: Optional[float] = None, tolerance: int = 300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t, sig = parts.get("t"), [p.split("=", 1)[1] for p in header.split(",") if p.startswith("v1=")]
    if not t or not sig or not secret:
        return False
    if abs((now or time.time()) - int(t)) > tolerance:
        return False
    want = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(want, g) for g in sig)


def stripe_event(s: Store, payload: bytes, header: str) -> Tuple[int, str]:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not verify_stripe(payload, header, secret):
        return 400, "bad signature"
    ev = json.loads(payload)
    if ev.get("type") == "checkout.session.completed":
        o = ev["data"]["object"]
        vid = o.get("client_reference_id") or ""
        if o.get("payment_status") == "paid" and s.venture(vid):
            record_revenue(s, vid, int(o.get("amount_total") or 0), "stripe", ev["id"], o.get("customer_details", {}).get("email", ""))
    return 200, "ok"


# ---- landing publish ----------------------------------------------------------
def publish_landing(s: Store, vid: str) -> Optional[str]:
    """Write the QA-accepted landing page, wiring the CTA to the venture's Stripe link (tagged so the webhook can credit the venture)."""
    a = s.one("select body from artifacts where venture_id=? and kind='landing' order by id desc limit 1", (vid,))
    if not a:
        return None
    html = re.sub(r"^```(?:html)?|```$", "", a["body"].strip(), flags=re.M)
    link = s.venture(vid)["payment_link"]
    if link:
        html = html.replace('href="#pay"', f'href="{link}{"&" if "?" in link else "?"}client_reference_id={vid}"')
    d = SITE / vid
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    return str(d / "index.html")
