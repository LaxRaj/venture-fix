"""Model layer: a heavy orchestrator model, a cheap-to-expensive worker ladder, and a stub.

Workers always start on the cheapest tier.  The orchestrator moves a task up a tier only after
the QA gate rejected the output, so spend follows difficulty.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from vstress.client import _post_json

API = "https://api.anthropic.com/v1/messages"
TIERS: List[str] = [
    os.environ.get("FLEET_TIER0", "claude-haiku-5-5"),
    os.environ.get("FLEET_TIER1", "claude-sonnet-5-5"),
    os.environ.get("FLEET_TIER2", "claude-opus-5-5"),
]
ORCH_MODEL = os.environ.get("FLEET_ORCH_MODEL", "claude-opus-5-5")
JUDGE_MODEL = os.environ.get("FLEET_JUDGE_MODEL", "claude-sonnet-5-5")


def _post(url, body, headers, timeout=60):
    """_post_json, with dropped connections and timeouts surfaced as RuntimeError so callers retry or stop cleanly."""
    try:
        return _post_json(url, body, headers, timeout=timeout)
    except (OSError, http.client.HTTPException) as exc:  # RemoteDisconnected, ConnectionReset, socket timeout
        raise RuntimeError(f"connection to {url} failed: {type(exc).__name__}: {exc}") from exc


@dataclass
class Reply:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""


class Provider:
    name = "base"
    judge = os.environ.get("FLEET_JUDGE") != "0"  # whether the model judge runs on top of the deterministic gates

    def complete(self, *, model: str, system: str, user: str, kind: str, tier: int,
                 max_tokens: int = 1500, ctx: Optional[Dict[str, object]] = None) -> Reply:
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, key: str) -> None:
        self.key = key

    def complete(self, *, model, system, user, kind, tier, max_tokens=1500, ctx=None) -> Reply:
        body = {"model": model, "max_tokens": max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        headers = {"x-api-key": self.key, "anthropic-version": "2023-06-01"}
        last: Optional[Exception] = None
        for wait in (0, 4, 12):
            time.sleep(wait)
            try:
                raw = _post(API, body, headers, timeout=120)
                text = "".join(b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text")
                u = raw.get("usage", {})
                return Reply(text, int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)), model)
            except RuntimeError as exc:  # network, 429, 5xx are retried; other 4xx is not
                last = exc
                if re.search(r"HTTP 4(?!29)\d\d", str(exc)):
                    break
        raise RuntimeError(f"model call failed: {last}")


class RateLimited(RuntimeError):
    """The provider's (daily) limit is exhausted; further calls this cycle would only fail."""


class OpenAICompatProvider(Provider):
    """Any OpenAI-compatible chat endpoint: Ollama (free, local), Groq or Gemini free tiers.
    FLEET_BASE_URL e.g. http://localhost:11434/v1, FLEET_API_KEY optional (Ollama needs none)."""
    name = "openai"
    judge = os.environ.get("FLEET_JUDGE") == "1"  # off by default: deterministic QA is the floor, and free calls are scarce

    def __init__(self, base: str, key: str = "") -> None:
        self.base, self.key = base.rstrip("/"), key

    def complete(self, *, model, system, user, kind, tier, max_tokens=1500, ctx=None) -> Reply:
        body = {"model": model, "max_tokens": max_tokens, "temperature": 0.3,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        last: Optional[Exception] = None
        for wait in (0, 8, 25):
            time.sleep(wait)
            try:
                raw = _post(f"{self.base}/chat/completions", body, headers, timeout=300)
                u = raw.get("usage") or {}
                text = raw["choices"][0]["message"]["content"] or ""
                return Reply(text, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", len(text) // 4)), model)
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"unexpected response shape: {exc}") from exc
            except RuntimeError as exc:
                last = exc
                if re.search(r"HTTP 4(?!29)\d\d", str(exc)):
                    break
        if last and "HTTP 429" in str(last):
            raise RateLimited(str(last)[:200])
        raise RuntimeError(f"model call failed: {last}")


def make_provider(name: Optional[str] = None) -> Provider:
    if name is None:
        name = ("anthropic" if os.environ.get("ANTHROPIC_API_KEY") else
                "openai" if os.environ.get("FLEET_BASE_URL") else "stub")
    if name == "openai":
        base = os.environ.get("FLEET_BASE_URL")
        if not base:
            raise SystemExit("set FLEET_BASE_URL (Ollama: http://localhost:11434/v1)")
        return OpenAICompatProvider(base, os.environ.get("FLEET_API_KEY", ""))
    if name == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not set; use the stub provider or export the key")
        return AnthropicProvider(key)
    from .stub import StubProvider
    return StubProvider()


def parse_json(text: str):
    """First JSON object or array in a model reply, or None."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except ValueError:
                continue
    return None
