"""Groq (OpenAI-compatible) client: cheap generation, capped web-search grounding, and a stub.

Two modes keep the free tier usable:
  generate  no web search.  Candidates and their numbers are model *guesses*.
  ground    web search (gpt-oss browser_search) for ONE candidate at a time, capped.
Model names are not assumed: `python3 discover.py models` lists what your key can use.
Daily-token limits are read from the 429 message; a model that is out for the day is
skipped and the next one in GROQ_MODELS is used.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

from vstress.client import _post_json

BASE = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"
UA = "venture-fix-discovery/1.0"  # Cloudflare in front of Groq rejects the default Python-urllib agent (error 1010)
CITATION = re.compile(r"【[^】]*】")  # search citation markers such as 【1†L2-L3】
WAIT_LIMIT = 90.0  # a per-minute limit shorter than this is waited out; longer means a daily limit

SCHEMA_HELP = (
    '[{"offer": "short name", "buyer": "who pays", "task": "the recurring painful task", '
    '"price_usd": number, "price_unit": "month" | "project" | "per_unit" | "contingency", '
    '"price_url": null, "hours_per_account_month": number, "pool_count": number, "pool_url": null, '
    '"channel": "free way to reach buyers", "blockers": "licence, compliance, saturation, offshore price competition", '
    '"evidence": {"buyer": "short sentence", "pain": "short sentence", "supply": "what buyers use today", '
    '"workflow": "how the work is handled", "access": "how to reach them"}}]'
)

GEN_PROMPT = (
    "You brainstorm businesses a solo operator with no capital could start. Do not browse. From general knowledge, "
    "list up to 6 distinct, concrete offers for the query as a JSON array only, shaped like: " + SCHEMA_HELP + ". "
    "Rules: price_usd (US dollars), hours_per_account_month and pool_count are your best honest estimates as plain numbers; pool_count is how many such businesses exist in the US written as a full integer and never abbreviated; each offer gets its own estimate; use "
    "price_unit 'month' only if a flat monthly retainer is realistic; price_url and pool_url must be null; never "
    "invent a URL; be candid in blockers; keep every sentence short. Query: "
)

GROUND_PROMPT = (
    "Search the web (at most 3 searches), then answer. For the service '{offer}' sold to '{buyer}', find (1) what "
    "such buyers or competitors charge, as a monthly price if possible, with the page URL where you saw it; (2) how "
    "many such businesses exist in the US, with the page URL. Reply with one JSON object only: "
    '{{"price_usd": number or null, "price_unit": "month"|"project"|"per_unit"|"contingency"|null, '
    '"price_url": string or null, "pool_count": number or null, "pool_url": string or null}}. '
    "Use null for anything you did not see on a page. Never guess a number or a URL."
)


def _collect_keys() -> List[str]:
    """GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3 ... and an optional comma list in GROQ_API_KEYS, de-duplicated.
    Groq limits apply per organization, so extra keys only help if they belong to a different one."""
    keys: List[str] = []
    cands = [os.environ.get("GROQ_API_KEY", "")] + [os.environ.get(f"GROQ_API_KEY_{i}", "") for i in range(2, 10)]
    cands += (os.environ.get("GROQ_API_KEYS") or "").split(",")
    for k in cands:
        k = k.strip()
        if k and k not in keys:
            keys.append(k)
    return keys


class DailyLimit(RuntimeError):
    """Every configured model is out of tokens for the day."""


THINK = re.compile(r"<think>.*?</think>", re.S)


def _clean(text: str) -> str:
    return THINK.sub("", CITATION.sub("", text or ""))


def extract_json_list(text: str) -> List[dict]:
    """Pull the first JSON array of objects out of a model reply; [] if none."""
    text = _clean(text)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def extract_json_object(text: str) -> Optional[dict]:
    text = _clean(text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def wait_seconds(message: str) -> float:
    """Seconds Groq asks us to wait, from 'Please try again in 7m58.2s'; 0 if absent."""
    m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m(?!s))?(?:(\d+(?:\.\d+)?)s)?", message)
    if not m:
        return 0.0
    h, mi, s = (float(x) if x else 0.0 for x in m.groups())
    return h * 3600 + mi * 60 + s


class GroqProvider:
    name = "groq"

    def __init__(self, sleep: Callable[[float], None] = time.sleep, retries: int = 4, lane=None) -> None:
        self.lane = lane                                   # (model, key index) to pin to, for parallel work
        self.keys = _collect_keys()
        self.key = self.keys[0] if self.keys else ""      # first key: model listing
        models = os.environ.get("GROQ_MODELS") or os.environ.get("GROQ_MODEL") or DEFAULT_MODEL
        self.models = [m.strip() for m in models.split(",") if m.strip()]
        self.exhausted: set = set()                        # (model, key index) pairs out of tokens for the day
        self.sleep = sleep
        self.retries = retries
        self.tokens_used = 0
        self.tokens_by_key: Dict[int, int] = {}            # key index -> tokens, to see whether extra keys help
        if not self.keys:
            raise SystemExit("groq provider needs GROQ_API_KEY. Use --provider stub for an offline run.")

    def _pick(self):
        """Next (model, key index) that still has tokens: try each key on a model before moving to the next model.
        A pinned lane only ever uses its own pair, so parallel workers never share a per-minute budget."""
        if self.lane is not None:
            if self.lane in self.exhausted:
                raise DailyLimit(f"daily token limit reached on lane {self.lane[0]} / key {self.lane[1] + 1}")
            return self.lane
        for m in self.models:
            for ki in range(len(self.keys)):
                if (m, ki) not in self.exhausted:
                    return m, ki
        raise DailyLimit("daily token limit reached on: " + ", ".join(self.models)
                         + f" across {len(self.keys)} key(s). Rerun later; cached work is kept.")

    def _chat(self, prompt: str, search: bool, max_out: int) -> str:
        while True:
            model, ki = self._pick()  # raises DailyLimit when none are left
            body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
            body["max_completion_tokens"] = max_out
            if model.startswith("openai/gpt-oss"):
                body["reasoning_effort"] = "low"
                if search:
                    body.update(tools=[{"type": "browser_search"}], tool_choice="auto")
            elif search:
                raise RuntimeError(f"{model} has no known search tool; use an openai/gpt-oss model for browsing")
            delay = 5.0
            for _ in range(self.retries):
                try:
                    raw = _post_json(f"{BASE}/chat/completions", body,
                                     {"Authorization": f"Bearer {self.keys[ki]}", "User-Agent": UA}, timeout=180)
                    used = int((raw.get("usage") or {}).get("total_tokens") or 0)
                    self.tokens_used += used
                    self.tokens_by_key[ki] = self.tokens_by_key.get(ki, 0) + used
                    return raw["choices"][0]["message"]["content"] or ""  # type: ignore[index]
                except RuntimeError as exc:
                    msg = str(exc)
                    if "HTTP 429" in msg:
                        wait = wait_seconds(msg)
                        if "per day" in msg or wait > WAIT_LIMIT:
                            self.exhausted.add((model, ki))  # out for the day on this key; try the next key, then model
                            break
                        self.sleep(max(wait, delay))
                        delay = min(delay * 2, 60.0)
                        continue
                    if "tool_use_failed" in msg and not search:
                        return ""  # the model tried to browse though no tools were offered: treat as "no answer"
                    if "HTTP 5" in msg:
                        self.sleep(delay)
                        delay = min(delay * 2, 60.0)
                        continue
                    raise
            else:
                raise RuntimeError("rate limited after retries; rerun to resume from cache")

    def ask(self, query_text: str) -> List[dict]:
        """Stage 1: ungrounded brainstorm.  Numbers are guesses."""
        return extract_json_list(self._chat(GEN_PROMPT + query_text, search=False, max_out=2500))

    def complete(self, prompt: str, max_out: int = 600) -> str:
        """Plain completion, no tools.  Used to read search snippets (about 1-2k tokens)."""
        return self._chat(prompt, search=False, max_out=max_out)

    def ground(self, offer: str, buyer: str) -> Optional[dict]:
        """Browsing grounding (legacy engine): capped web search for one candidate's price and pool."""
        text = self._chat(GROUND_PROMPT.format(offer=offer, buyer=buyer), search=True, max_out=1500)
        return extract_json_object(text)

    def list_models(self) -> List[str]:
        req = urllib.request.Request(f"{BASE}/models")
        req.add_header("Authorization", f"Bearer {self.key}")
        req.add_header("User-Agent", UA)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"could not reach Groq: {exc}") from exc
        return sorted(m.get("id", "") for m in data.get("data", []))


def make_lanes() -> List["GroqProvider"]:
    """One provider per (model, key) pair.  Groq's per-minute token limit applies to each pair separately, so
    running them side by side multiplies throughput.  Lane models come from GROQ_LANE_MODELS (default: the two
    gpt-oss models, which are the ones brainstorming has been tested on)."""
    keys = _collect_keys()
    models = [m.strip() for m in (os.environ.get("GROQ_LANE_MODELS") or "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",") if m.strip()]
    if not keys:
        raise SystemExit("groq provider needs GROQ_API_KEY. Use --provider stub for an offline run.")
    return [GroqProvider(lane=(m, ki)) for ki in range(len(keys)) for m in models]


class StubGroq:
    """Deterministic fake candidates.  Plumbing only: every number is invented."""

    name = "stub"
    tokens_used = 0

    def ask(self, query_text: str) -> List[dict]:
        h = int(hashlib.sha256(query_text.encode()).hexdigest()[:8], 16)
        out = []
        for i in range(3):
            price = 150 + (h + i * 97) % 1800
            out.append({
                "offer": f"STUB alpha{h % 9973} beta{(h >> 5) % 991} gamma{(h + i * 31) % 983} service",
                "buyer": f"STUB buyer {h % 101}",
                "task": "STUB recurring task",
                "price_usd": float(price), "price_unit": ("month", "month", "contingency")[i],
                "price_url": None, "hours_per_account_month": float(2 + (h + i) % 12),
                "pool_count": float(2000 + (h * (i + 3)) % 90000), "pool_url": None,
                "channel": "STUB channel", "blockers": "STUB",
                "evidence": {k: f"STUB {k} evidence." for k in ("buyer", "pain", "supply", "workflow", "access")},
            })
        return out

    def complete(self, prompt: str, max_out: int = 600) -> str:
        m = re.search(r"\[(\d+)\] [^|]*\| ([^(]*?\$(\d+)[^(]*?)\s*\(", prompt)
        if not m:
            return '{"price_usd": null, "price_unit": null, "source_index": null, "quote": null}'
        return json.dumps({"price_usd": int(m.group(3)), "price_unit": "month", "source_index": int(m.group(1)),
                           "price_kind": "vendor_fee", "audience": "small_business",
                           "quote": re.search(r"[^.]*\$\d+[^.]*", m.group(2)).group(0).strip()})

    def ground(self, offer: str, buyer: str) -> Optional[dict]:
        h = int(hashlib.sha256((offer + buyer).encode()).hexdigest()[:8], 16)
        return {"price_usd": float(200 + h % 900), "price_unit": "month",
                "price_url": f"https://example.invalid/price/{h % 1000}",
                "pool_count": float(3000 + h % 40000), "pool_url": f"https://example.invalid/pool/{h % 1000}"}


def make_groq(provider: str):
    return StubGroq() if provider == "stub" else GroqProvider()
