"""Offline provider.  Tier 0 deliberately makes the mistakes QA exists to catch, so the
escalation loop is exercised without an API key.  Output is template text, not intelligence."""

from __future__ import annotations

import json
from typing import Dict, Optional

from .llm import Provider, Reply

DEFAULT_PLAN = [
    {"kind": "research", "title": "Buyer profile and prospect search recipes",
     "brief": "Define the buyer, where to find 30 of them for free, likely objections, and the first offer."},
    {"kind": "landing", "title": "One-page offer with a pay button",
     "brief": "A mobile-first static page: plain headline, who it is for, what they get, the price, one button."},
    {"kind": "demo", "title": "Free sample deliverable",
     "brief": "A sample of the actual work product for a hypothetical buyer, to attach to outreach."},
    {"kind": "outreach", "title": "Personalised first-touch emails",
     "brief": "One short email per imported prospect, one ask, with an opt-out line and postal address."},
]


class StubProvider(Provider):
    name = "stub"

    def complete(self, *, model, system, user, kind, tier, max_tokens=1500,
                 ctx: Optional[Dict[str, object]] = None) -> Reply:
        ctx = ctx or {}
        v = ctx.get("venture", {})
        offer, buyer = v.get("offer", "the service"), v.get("buyer", "small businesses")
        price = ctx.get("price_display", "$1,000/mo")
        if kind == "plan":
            text = json.dumps(DEFAULT_PLAN)
        elif kind == "research":
            text = (f"Buyer profile: {buyer} that currently handle this by hand.\n"
                    "Where to find them:\n1. Google Maps search for the trade in one metro, copy 30 listings.\n"
                    "2. State licensing board public lookup.\n3. Trade association member directory.\n"
                    "Objections: price, trust, switching cost.\n"
                    f"First offer: a paid one-month pilot of {offer} at {price}.")
        elif kind == "landing":
            cta = ctx.get("payment_link") or "#pay"
            shown = "" if tier == 0 else f"<p><strong>{price}</strong></p>"  # tier 0 forgets the price
            text = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                    f"<title>{offer}</title></head><body><h1>{offer} for {buyer}</h1>"
                    f"<p>We take this recurring task off your plate.</p>{shown}"
                    f'<a href="{cta}">Start a one-month pilot</a></body></html>')
        elif kind == "demo":
            text = ("Sample deliverable (built from public information, not client data)\n\n"
                    + " ".join(f"Step {i}: a worked example of {offer} for a hypothetical {buyer} account." for i in range(1, 14)))
        elif kind in ("outreach", "followup"):
            company = ctx.get("prospect_company", "your company")
            addr = ctx.get("sender_address", "")
            opt = "" if tier == 0 else " If this is not relevant, reply STOP and I will not write again."  # tier 0 forgets it
            text = json.dumps({
                "subject": f"Quick question about {company}",
                "body": (f"Hi, I help {buyer} with {offer.lower()}. I noticed {company} may still do this by hand. "
                         f"I can run a one-month pilot for {price} and send a free sample first. "
                         f"Would a short call this week be useful?{opt} {addr}")})
        elif kind == "judge":
            text = json.dumps({"pass": True, "issues": []})
        elif kind == "review":
            text = "Stub review: continue the plan; the next unblocked step is the first paid pilot."
        else:
            text = "stub"
        return Reply(text, len(user) // 4, len(text) // 4, model)
