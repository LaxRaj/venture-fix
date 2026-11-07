"""Orchestrator: plans with the heavy model, works on the cheap tier, QA-gates every output, and
moves a task up a model tier only when QA rejects it.  It never sends anything or touches money:
outputs that reach a real person land in the approval queue (see money.py)."""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional, Tuple

from . import qa, roles
from .llm import JUDGE_MODEL, ORCH_MODEL, TIERS, Provider, parse_json
from .stub import DEFAULT_PLAN
from .store import Store

ATTEMPTS_PER_TIER = [2, 1, 1]  # tier 0 gets one retry with QA feedback; higher tiers get one shot each
DEFAULT_TOKEN_BUDGET = 400_000  # per rolling 24h, across all agents


class BudgetExceeded(Exception):
    pass


def price_display(v: dict) -> str:
    p = v.get("price_usd") or 0
    unit = {"month": "/mo", "project": " per project", "per_unit": " per unit"}.get(v.get("price_unit"), "")
    return f"${p:,.0f}{unit}"


class Fleet:
    def __init__(self, store: Store, provider: Provider, token_budget: int = DEFAULT_TOKEN_BUDGET, batch: int = 5) -> None:
        self.s, self.p, self.budget, self.batch = store, provider, token_budget, batch

    # ---- context ------------------------------------------------------
    def ctx(self, vid: str, **extra) -> Dict:
        v = self.s.venture(vid)
        research = self.s.one("select body from artifacts where venture_id=? and kind='research' order by id desc limit 1", (vid,))
        c = {"venture": v["data"], "price_display": price_display(v["data"]), "payment_link": v["payment_link"],
             "sender_name": self.s.setting("sender_name"), "sender_address": self.s.setting("sender_address"),
             "research": research["body"] if research else ""}
        c.update(extra)
        return c

    # ---- one model call, accounted -------------------------------------
    def _call(self, vid: str, tid: Optional[int], model: str, kind: str, tier: int, system: str, user: str, ctx: Dict, max_tokens: int):
        if self.s.tokens_today() >= self.budget:
            raise BudgetExceeded(f"{self.budget} tokens in 24h used")
        return self.p.complete(model=model, system=system, user=user, kind=kind, tier=tier, max_tokens=max_tokens, ctx=ctx)

    def _record(self, tid, vid, tier, model, ok, issues, reply) -> None:
        self.s.x("insert into attempts(task_id,venture_id,tier,model,ok,issues,tokens_in,tokens_out,ts) values(?,?,?,?,?,?,?,?,?)",
                 (tid, vid, tier, model, int(ok), json.dumps(issues), reply.tokens_in if reply else 0, reply.tokens_out if reply else 0, time.time()))

    # ---- worker -> QA -> escalate --------------------------------------
    def work(self, vid: str, tid: Optional[int], kind: str, brief: str, ctx: Dict, start_tier: int = 0) -> Tuple[bool, str, int, List[str]]:
        feedback, issues = "", ["never ran"]
        for tier in range(start_tier, len(TIERS)):
            for _ in range(ATTEMPTS_PER_TIER[tier]):
                model = TIERS[tier]
                try:
                    reply = self._call(vid, tid, model, kind, tier, roles.ROLES[kind], roles.prompt(kind, brief, ctx, feedback), ctx, 2000)
                except BudgetExceeded:
                    raise
                except RuntimeError as exc:
                    self._record(tid, vid, tier, model, False, [str(exc)[:200]], None)
                    return False, "", tier, [f"model error: {str(exc)[:200]}"]
                issues = qa.gate(kind, reply.text, ctx)
                if not issues and self.p.name != "stub":
                    issues = self._judge(vid, tid, kind, brief, reply.text, ctx)
                self._record(tid, vid, tier, model, not issues, issues, reply)
                if not issues:
                    return True, reply.text, tier, []
                feedback = "\n".join(f"- {i}" for i in issues)
            self.s.log(vid, f"QA rejected {kind} on {TIERS[tier]} ({issues[0]}); escalating" if tier + 1 < len(TIERS) else f"QA rejected {kind} on top tier")
        return False, "", len(TIERS) - 1, issues

    def _judge(self, vid, tid, kind, brief, text, ctx) -> List[str]:
        """Model judge: may add issues, never removes one.  A garbled judge reply is ignored (deterministic gates are the floor)."""
        try:
            r = self._call(vid, tid, JUDGE_MODEL, "judge", 1, roles.ROLES["judge"], f"Brief: {brief}\n\nOutput to review:\n{text[:6000]}", ctx, 400)
        except BudgetExceeded:
            raise
        except RuntimeError:
            return []
        d = parse_json(r.text)
        if isinstance(d, dict) and d.get("pass") is False:
            return [f"judge: {i}" for i in (d.get("issues") or ["rejected"])][:5]
        return []

    # ---- planning (heavy model) ----------------------------------------
    def ensure_plan(self, vid: str) -> None:
        if self.s.one("select id from tasks where venture_id=? limit 1", (vid,)):
            return
        ctx = self.ctx(vid)
        plan = None
        for _ in range(2):
            r = self._call(vid, None, ORCH_MODEL, "plan", 2, roles.ROLES["plan"], roles.prompt("plan", "Plan the work to get one paid pilot as fast as possible.", ctx), ctx, 1200)
            bad = qa.gate("plan", r.text, ctx)
            self._record(None, vid, 2, ORCH_MODEL, not bad, bad, r)
            if not bad:
                plan = parse_json(r.text)
                break
        if plan is None:
            self.s.log(vid, "orchestrator plan failed validation twice; using the default playbook")
            plan = DEFAULT_PLAN
        for i, t in enumerate(plan):
            self.s.x("insert into tasks(venture_id,kind,title,brief,ord,updated) values(?,?,?,?,?,?)",
                     (vid, t["kind"], t["title"][:120], t["brief"][:600], i, time.time()))
        self.s.log(vid, f"orchestrator planned {len(plan)} tasks")

    # ---- tasks ----------------------------------------------------------
    def run_task(self, t: Dict) -> None:
        vid, kind = t["venture_id"], t["kind"]
        if kind == "outreach":
            return self._outreach(t, "new", "email")
        ctx = self.ctx(vid)
        ok, body, tier, issues = self.work(vid, t["id"], kind, t["brief"], ctx, t["tier"])
        self._finish(t, ok, body, tier, issues)

    def _finish(self, t, ok, body, tier, issues) -> None:
        if ok:
            self.s.x("insert into artifacts(task_id,venture_id,kind,body,tier,ts) values(?,?,?,?,?,?)", (t["id"], t["venture_id"], t["kind"], body, tier, time.time()))
            self.s.x("update tasks set status='done',tier=?,attempts=attempts+1,note='',updated=? where id=?", (tier, time.time(), t["id"]))
            self.s.log(t["venture_id"], f"{t['kind']} accepted by QA on {TIERS[tier]}")
        else:
            self.s.x("update tasks set status='blocked',tier=?,attempts=attempts+1,note=?,updated=? where id=?", (tier, "; ".join(issues)[:400], time.time(), t["id"]))
            self.s.log(t["venture_id"], f"{t['kind']} blocked: {issues[0] if issues else '?'}")

    def _outreach(self, t: Dict, status: str, appr_kind: str) -> None:
        vid = t["venture_id"]
        if not self.s.setting("sender_address"):
            self.s.x("update tasks set status='waiting',note=? where id=?", ("set the sender postal address in Settings (legal requirement for commercial email)", t["id"]))
            return
        todo = self.s.q("select * from prospects where venture_id=? and status=? limit ?", (vid, status, self.batch))
        if not todo:
            if not self.s.one("select id from prospects where venture_id=?", (vid,)):
                self.s.x("update tasks set status='waiting',note=? where id=?", ("import prospects (CSV: name,company,email) to draft outreach", t["id"]))
            return
        tier = t["tier"]
        for pr in todo:
            ctx = self.ctx(vid, prospect_name=pr["name"], prospect_company=pr["company"], prospect_note=pr["note"])
            ok, body, tier, issues = self.work(vid, t["id"], "outreach", t["brief"], ctx, tier)
            if ok:
                d = parse_json(body)
                self.s.x("insert into approvals(venture_id,prospect_id,kind,subject,body,ts) values(?,?,?,?,?,?)", (vid, pr["id"], appr_kind, d["subject"], d["body"], time.time()))
                self.s.x("update prospects set status='drafted' where id=?", (pr["id"],))
            else:
                self.s.x("update prospects set status='blocked',note=? where id=?", ("; ".join(issues)[:300], pr["id"]))
        self.s.x("update tasks set status='waiting',tier=?,note='drafts await your approval; import more prospects for more drafts',updated=? where id=?", (tier, time.time(), t["id"]))

    def _followups(self, vid: str) -> int:
        n = 0
        for pr in self.s.q("select * from prospects where venture_id=? and status='replied'", (vid,)):
            msg = self.s.one("select body from messages where prospect_id=? and direction='in' order by id desc limit 1", (pr["id"],))
            ctx = self.ctx(vid, prospect_name=pr["name"], prospect_company=pr["company"], prospect_note=pr["note"], inbound=(msg or {}).get("body", ""))
            ok, body, _, issues = self.work(vid, None, "followup", "Reply to this prospect and move toward a paid one-month pilot.", ctx, 1)
            if ok:
                d = parse_json(body)
                self.s.x("insert into approvals(venture_id,prospect_id,kind,subject,body,ts) values(?,?,?,?,?,?)", (vid, pr["id"], "followup", d["subject"], d["body"], time.time()))
                self.s.x("update prospects set status='reply_drafted' where id=?", (pr["id"],))
                n += 1
        return n

    # ---- cycles ---------------------------------------------------------
    def run_cycle(self, vid: str) -> Dict:
        v = self.s.venture(vid)
        if not v or v["status"] != "active":
            return {"venture": vid, "skipped": "not active"}
        before = self.s.one("select count(*) n from tasks where venture_id=? and status='done'", (vid,))["n"]
        try:
            self.ensure_plan(vid)
            for t in self.s.q("select * from tasks where venture_id=? and status in ('pending','waiting','blocked') order by ord", (vid,)):
                if t["status"] == "blocked" and t["attempts"] >= 2:
                    continue  # two full ladder failures: a human must look
                self.run_task(t)
            followups = self._followups(vid)
            self._review(vid)
        except BudgetExceeded as exc:
            self.s.log(vid, f"stopped: {exc}")
            return {"venture": vid, "stopped": str(exc)}
        except RuntimeError as exc:  # orchestrator model unreachable: log and let the next cycle retry
            self.s.log(vid, f"orchestrator call failed: {str(exc)[:200]}")
            return {"venture": vid, "error": str(exc)[:200]}
        after = self.s.one("select count(*) n from tasks where venture_id=? and status='done'", (vid,))["n"]
        return {"venture": vid, "tasks_done": after, "newly_done": after - before, "followups": followups}

    def _review(self, vid: str) -> None:
        rows = self.s.q("select kind,status,note from tasks where venture_id=? order by ord", (vid,))
        pend = self.s.one("select count(*) n from approvals where venture_id=? and status='pending'", (vid,))["n"]
        ctx = self.ctx(vid)
        r = self._call(vid, None, ORCH_MODEL, "review", 2, roles.ROLES["review"],
                       f"Tasks: {json.dumps(rows)}\nDrafts awaiting human approval: {pend}\nCash so far (cents): {self.cash(vid)}", ctx, 300)
        self._record(None, vid, 2, ORCH_MODEL, True, [], r)
        self.s.log(vid, "orchestrator: " + r.text.strip()[:400])

    def cash(self, vid: str) -> int:
        return int(self.s.one("select coalesce(sum(cents),0) n from ledger where venture_id=?", (vid,))["n"])

    def run_all(self) -> List[Dict]:
        out = []
        for v in self.s.q("select id from ventures where status='active' order by rowid"):
            out.append(self.run_cycle(v["id"]))
            if out[-1].get("stopped"):
                break
        return out
