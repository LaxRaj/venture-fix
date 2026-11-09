"""QA gates.  Deterministic, fail-closed, and independent of the model that wrote the output.

A model judge may add issues on top of these.  It can never waive one.
"""

from __future__ import annotations

import ast
import re
from html.parser import HTMLParser
from typing import Callable, Dict, List

from .llm import parse_json

OVERCLAIM = re.compile(r"(guarantee[sd]?|100%|risk[- ]free|#1\b|best in |number one|proven results|"
                       r"trusted by \d+|as seen on)", re.I)
# An attributed quote ("..." - Name) or social-proof copy we have no basis for.  The bare word "testimonial"
# is fine: one of the ventures sells testimonial videos.
FAKE_PROOF = re.compile(r"[\"“][^\"”<>]{20,}[\"”]\s*[-—–]\s*[A-Z]|what (?:our )?(?:clients|customers) (?:say|are saying)|"
                        r"(?:our|recent) (?:clients|customers) (?:report|saw|achieved)", re.I)
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}|\[(?:your|insert|company|name|first)[^\]]*\]|lorem ipsum|TODO", re.I)
OPT_OUT = re.compile(r"(unsubscribe|opt[- ]out|reply (?:stop|no)\b)", re.I)
BANNED_CODE = re.compile(r"\b(subprocess|socket|os\.system|eval|exec|__import__|shutil\.rmtree|ctypes)\b")


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: List[str] = []
        self.hrefs: List[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.hrefs += [v for k, v in attrs if k == "href" and v]


def words(s: str) -> int:
    return len(re.findall(r"\w+", s))


def _common(text: str, strict_proof: bool = False) -> List[str]:
    out = []
    if PLACEHOLDER.search(text):
        out.append("unfilled placeholder text")
    m = OVERCLAIM.search(text)
    if m:
        out.append(f"unverifiable claim: '{m.group(0)}'")
    if strict_proof and FAKE_PROOF.search(text):
        out.append("looks like a fabricated testimonial / case study")
    return out


def check_landing(body: str, ctx: Dict) -> List[str]:
    issues = []
    p = _Tags()
    try:
        p.feed(body)
    except Exception as exc:  # noqa: BLE001
        return [f"html does not parse: {exc}"]
    for t in ("title", "h1", "a", "meta"):
        if t not in p.tags:
            issues.append(f"missing <{t}>")
    if "viewport" not in body:
        issues.append("no viewport meta (page must work on a phone)")
    price = ctx.get("price_display", "")
    if price and price not in body:
        issues.append(f"price {price} not shown")
    link = ctx.get("payment_link") or ""
    if link and not any(h.startswith(link) for h in p.hrefs):
        issues.append("call-to-action does not point at the payment link")
    if not link and "#pay" not in p.hrefs:
        issues.append('no call-to-action link (use href="#pay" until a payment link exists)')
    if "<script" in body.lower():
        issues.append("landing page must not ship scripts")
    return issues + _common(body, strict_proof=True)


def check_outreach(body: str, ctx: Dict) -> List[str]:
    from .llm import parse_json as pj
    d = pj(body)
    if not isinstance(d, dict) or not d.get("subject") or not d.get("body"):
        return ["reply must be JSON with subject and body"]
    subj, text = str(d["subject"]), str(d["body"])
    issues = []
    n = words(text)
    if n > 130:
        issues.append(f"body is {n} words; limit 130")
    if n < 25:
        issues.append(f"body is {n} words; too thin to be a real offer")
    if not OPT_OUT.search(text):
        issues.append("no opt-out line")
    addr = ctx.get("sender_address", "")
    if not addr:
        issues.append("settings.sender_address is empty (CAN-SPAM needs a postal address) - a human must set it")
    elif addr.lower() not in text.lower():
        issues.append("sender postal address missing from body")
    if re.match(r"\s*(re|fwd?):", subj, re.I):
        issues.append("subject fakes a reply thread")
    if len(subj) > 70 or (subj.isupper() and len(subj) > 4):
        issues.append("subject too long or shouting")
    if text.count("?") > 2:
        issues.append("more than one ask")
    company = (ctx.get("prospect_company") or "").lower()
    if company and company not in text.lower() and company not in subj.lower():
        issues.append("not personalised: prospect company never named")
    return issues + _common(subj + "\n" + text)


def check_demo(body: str, ctx: Dict) -> List[str]:
    issues = []
    if words(body) < 120:
        issues.append("demo deliverable is under 120 words")
    if not re.search(r"\bsample\b", body, re.I):
        issues.append("must be labelled as a sample")
    if re.search(r"(real|actual) client data", body, re.I):
        issues.append("claims to use real client data")
    return issues + _common(body)


def check_research(body: str, ctx: Dict) -> List[str]:
    issues = []
    for sec in ("buyer profile", "where to find", "objections", "first offer"):
        if sec not in body.lower():
            issues.append(f"missing section: {sec}")
    if len(re.findall(r"(?m)^\s*\d+[.)]", body)) < 3:
        issues.append("needs at least 3 numbered search recipes")
    return issues + _common(body)


def check_tool(body: str, ctx: Dict) -> List[str]:
    code = re.sub(r"^```(?:python)?|```$", "", body.strip(), flags=re.M)
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return [f"python does not parse: {exc}"]
    bad = BANNED_CODE.findall(code)
    return [f"forbidden construct in generated code: {sorted(set(bad))}"] if bad else []


def check_plan(body: str, ctx: Dict) -> List[str]:
    d = parse_json(body)
    if not isinstance(d, list) or not (3 <= len(d) <= 8):
        return ["plan must be a JSON list of 3-8 tasks"]
    issues = []
    for t in d:
        if not isinstance(t, dict) or t.get("kind") not in CHECKS or not t.get("title") or not t.get("brief"):
            issues.append(f"bad task: {t}")
    kinds = [t.get("kind") for t in d if isinstance(t, dict)]
    if "landing" not in kinds or "outreach" not in kinds:
        issues.append("plan needs a landing page and outreach (the shortest path to a paid order)")
    return issues


CHECKS: Dict[str, Callable[[str, Dict], List[str]]] = {
    "research": check_research, "landing": check_landing, "outreach": check_outreach,
    "demo": check_demo, "tool": check_tool, "followup": check_outreach,
}


def gate(kind: str, body: str, ctx: Dict) -> List[str]:
    if kind == "plan":
        return check_plan(body, ctx)
    fn = CHECKS.get(kind)
    return fn(body, ctx) if fn else [f"unknown task kind {kind}"]
