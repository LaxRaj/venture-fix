"""Search providers behind one shape: [{title, url, snippet}].

Serper (key, reported 2,500 free queries) is primary; ddgs (no key, unofficial, throttled by
DuckDuckGo without notice) is a fallback.  Every query is cached on disk so it is never paid
for twice, and a hard cap stops a run before it spends more credits than intended.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Callable, Dict, List, Optional

from vstress.client import _post_json

UA = "venture-fix-discovery/1.0"
Result = Dict[str, str]


class SearchBudget(RuntimeError):
    """The per-run search cap was reached; rerun to continue from cache."""


class SerperSearch:
    name = "serper"

    def __init__(self) -> None:
        self.key = os.environ.get("SERPER_API_KEY", "")
        if not self.key:
            raise RuntimeError("SERPER_API_KEY is not set")
        self.calls = 0

    def search(self, query: str, n: int = 6) -> List[Result]:
        raw = _post_json("https://google.serper.dev/search", {"q": query, "num": n, "gl": "us"},
                         {"X-API-KEY": self.key, "User-Agent": UA}, timeout=30)
        self.calls += 1
        return [{"title": str(o.get("title", "")), "url": str(o.get("link", "")), "snippet": str(o.get("snippet", ""))}
                for o in (raw.get("organic") or [])[:n] if o.get("link")]


class DdgsSearch:
    """Optional fallback: `pip install ddgs`.  Unofficial; throttled and retried politely."""

    name = "ddgs"

    def __init__(self, sleep: Callable[[float], None] = time.sleep, gap: float = 2.0) -> None:
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError as exc:
            raise RuntimeError("ddgs is not installed (pip install ddgs)") from exc
        self._ddgs = DDGS
        self.sleep, self.gap, self.calls = sleep, gap, 0

    def search(self, query: str, n: int = 6) -> List[Result]:
        last: Optional[Exception] = None
        for attempt in range(3):
            self.sleep(self.gap * (attempt + 1))
            try:
                rows = self._ddgs().text(query, max_results=n)
                self.calls += 1
                return [{"title": str(r.get("title", "")), "url": str(r.get("href", "")), "snippet": str(r.get("body", ""))}
                        for r in rows if r.get("href")]
            except Exception as exc:  # DuckDuckGo rate limits show up as assorted exceptions
                last = exc
        raise RuntimeError(f"ddgs failed: {last}")


class StubSearch:
    """Deterministic fake results.  Plumbing only: prices are invented."""

    name = "stub"
    calls = 0

    def search(self, query: str, n: int = 6) -> List[Result]:
        self.calls += 1
        h = int(hashlib.sha256(query.encode()).hexdigest()[:8], 16)
        price = 100 + h % 900
        return [
            {"title": "STUB vendor pricing", "url": f"https://example.invalid/p/{h % 997}",
             "snippet": f"Plans start at ${price} per month for small teams."},
            {"title": "STUB blog", "url": f"https://example.invalid/b/{h % 991}", "snippet": "A guide with no prices."},
        ]


class ChainSearch:
    """Try providers in order; fall through on an error or an empty result."""

    def __init__(self, providers: List) -> None:
        self.providers = providers
        self.name = "+".join(p.name for p in providers)
        self.used: Optional[str] = None

    @property
    def calls(self) -> int:
        return sum(getattr(p, "calls", 0) for p in self.providers)

    def search(self, query: str, n: int = 6) -> List[Result]:
        errors = []
        for p in self.providers:
            try:
                out = p.search(query, n)
            except RuntimeError as exc:
                errors.append(f"{p.name}: {exc}")
                continue
            if out:
                self.used = p.name
                return out
        if errors and len(errors) == len(self.providers):
            raise RuntimeError("all search providers failed: " + "; ".join(errors))
        return []


class CachedSearch:
    """Disk cache plus a hard cap on *paid* calls.  Cache hits are free and never counted."""

    def __init__(self, inner, cache_dir: str, max_searches: Optional[int] = None) -> None:
        self.inner, self.dir, self.max = inner, cache_dir, max_searches
        self.name, self.fresh, self.hits = inner.name, 0, 0
        os.makedirs(cache_dir, exist_ok=True)

    def search(self, query: str, n: int = 6) -> List[Result]:
        path = os.path.join(self.dir, hashlib.sha256(query.encode()).hexdigest()[:20] + ".json")
        if os.path.exists(path):
            self.hits += 1
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)["results"]
        if self.max is not None and self.fresh >= self.max:
            raise SearchBudget(f"search cap of {self.max} reached; rerun to continue (cached queries are free)")
        out = self.inner.search(query, n)
        self.fresh += 1
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"query": query, "results": out}, fh)
        return out


def make_search(provider: str, cache_dir: str, max_searches: Optional[int] = None) -> CachedSearch:
    if provider == "stub":
        return CachedSearch(StubSearch(), cache_dir, max_searches)
    providers: List = []
    for cls in (SerperSearch, DdgsSearch):
        try:
            providers.append(cls())
        except RuntimeError:
            continue
    if not providers:
        raise SystemExit("no search provider available: set SERPER_API_KEY in .env, or `pip install ddgs` for the "
                         "no-key fallback. Use --provider stub for an offline run.")
    return CachedSearch(ChainSearch(providers), cache_dir, max_searches)
