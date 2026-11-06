"""One provider interface: jev | generative | stub.

All fifteen questions for one venture go in one request.  Each question carries
exactly one evidence field, never the whole state and never a label.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Mapping, Optional, Sequence

from .data import LabelledVenture, build_state
from .questions import Question, payload
from .mapping import Answer

STUB_STAMP = "STUB PROVIDER - SYNTHETIC ANSWERS - PLUMBING ONLY - NOT EVIDENCE"
SYSTEM_PROMPT = (
    "You answer typed questions from one evidence field. Return JSON only. "
    "Choose exactly one option key for each question. Do not calculate, "
    "estimate a number, or invent evidence. If the field does not settle the "
    "question, choose the escape option. Do not explain."
)


class Provider:
    name = "provider"
    stamp = ""

    def ask(self, state: Mapping[str, str], questions: Sequence[Question]) -> Dict[str, Answer]:
        raise NotImplementedError


class StubProvider(Provider):
    name = "stub"
    stamp = STUB_STAMP

    def __init__(self, seed: int = 91) -> None:
        self.seed = int(seed)

    def ask(self, state: Mapping[str, str], questions: Sequence[Question]) -> Dict[str, Answer]:
        rng = random.Random(f"{self.seed}:{state.get('id', '')}")
        out: Dict[str, Answer] = {}
        for q in questions:
            digest = hashlib.sha256(
                f"{self.seed}:{state.get('id', '')}:{q.id}".encode("utf-8")
            ).digest()
            index = int.from_bytes(digest[:8], "big") % len(q.options)
            option = q.options[index]
            confidence = 0.50 + 0.50 * (digest[8] / 255.0)
            out[q.id] = Answer(option.key, confidence, raw="stub")
        return out


def _request_payload(state: Mapping[str, str], questions: Sequence[Question]) -> Dict[str, object]:
    rng = random.Random()  # fresh shuffle on every request; defeats first-option bias
    return {
        "instructions": SYSTEM_PROMPT,
        "questions": [payload(q, state, rng) for q in questions],
        "response_format": {
            "type": "json_object",
            "schema": {
                "answers": [
                    {"id": "question id", "key": "option key", "confidence": "0 to 1"}
                ]
            },
        },
    }


def _post_json(url: str, body: Mapping[str, object], headers: Mapping[str, str],
               timeout: int = 60) -> Dict[str, object]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not reach {url}: {exc.reason}") from exc


def _parse_answers(raw: Mapping[str, object], questions: Sequence[Question]) -> Dict[str, Answer]:
    items = raw.get("answers")
    if items is None and isinstance(raw.get("response"), dict):
        items = raw["response"].get("answers")  # type: ignore[index]
    if not isinstance(items, list):
        raise RuntimeError("provider response has no answers list")
    allowed = {q.id: {o.key for o in q.options} for q in questions}
    out: Dict[str, Answer] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id", ""))
        key = str(item.get("key", ""))
        if qid not in allowed:
            continue
        if key not in allowed[qid]:
            key = "escape"
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        out[qid] = Answer(key, confidence, raw=json.dumps(item, sort_keys=True))
    if not out:
        raise RuntimeError("provider returned no usable answers")
    return out


class GenerativeProvider(Provider):
    """OpenAI-compatible chat completions.  Used for the shadow pass."""

    name = "generative"
    stamp = "GENERATIVE SHADOW PASS - YOUR MODEL - NOT CALIBRATED BY DEFAULT"

    def __init__(self) -> None:
        self.key = os.environ.get("GENERATIVE_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.base = os.environ.get("GENERATIVE_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("GENERATIVE_MODEL", "gpt-4o-mini")
        if not self.key:
            raise SystemExit(
                "generative provider needs GENERATIVE_API_KEY (or OPENAI_API_KEY). "
                "Use --provider stub to exercise the harness without a model."
            )

    def ask(self, state: Mapping[str, str], questions: Sequence[Question]) -> Dict[str, Answer]:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(_request_payload(state, questions))},
            ],
        }
        raw = _post_json(
            f"{self.base}/chat/completions",
            body,
            {"Authorization": f"Bearer {self.key}"},
        )
        try:
            content = raw["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected chat response: {raw}") from exc
        return _parse_answers(json.loads(content), questions)


class JevProvider(Provider):
    """TypeSafe/Jev System One endpoint.

    Jev is not a chat model.  One request carries a shared state and a set of
    typed questions; the response carries one answer per question.  Every
    question names the one evidence field it may read, but the state itself
    contains only filtered evidence (never a label or kill reason).
    """

    name = "jev"
    stamp = "JEV - TYPESAFE - REQUIRES TYPESAFE_API_KEY"

    def __init__(self) -> None:
        self.key = os.environ.get("TYPESAFE_API_KEY", "")
        self.base = os.environ.get(
            "JEV_BASE_URL", "https://api.typesafe.ai/v1/systemone"
        )
        self.model = os.environ.get("JEV_MODEL", "jev-1.13.0")
        if not self.key:
            raise SystemExit(
                "jev provider needs TYPESAFE_API_KEY. "
                "Use --provider stub to exercise the harness without a model."
            )

    def ask(self, state: Mapping[str, str], questions: Sequence[Question]) -> Dict[str, Answer]:
        questions_payload = {}
        for q in questions:
            questions_payload[q.id] = {
                "type": "choice",
                "instructions": (
                    f"{q.text} Use only the '{q.source}' field of the state. "
                    "Choose exactly one option key. Do not calculate or infer."
                ),
                "criteria": {o.key: o.label for o in q.options},
            }
        body = {
            "model": self.model,
            "state": dict(state),
            "questions": questions_payload,
        }
        raw = _post_json(
            self.base,
            body,
            {"Authorization": f"Bearer {self.key}"},
        )
        return _parse_jev_answers(raw, questions)


def _parse_jev_answers(raw: Mapping[str, object],
                       questions: Sequence[Question]) -> Dict[str, Answer]:
    answers = raw.get("answers")
    if not isinstance(answers, dict):
        raise RuntimeError(f"Jev response has no answers object: {raw}")
    allowed = {q.id: {o.key for o in q.options} for q in questions}
    labels = {
        q.id: {o.label: o.key for o in q.options} for q in questions
    }
    out: Dict[str, Answer] = {}
    for qid, item in answers.items():
        if qid not in allowed or not isinstance(item, dict):
            continue
        key = str(item.get("choice", ""))
        if key not in allowed[qid]:
            key = labels[qid].get(key, "escape")
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        out[qid] = Answer(key, confidence, raw=json.dumps(item, sort_keys=True))
    if not out:
        raise RuntimeError("Jev returned no usable choice answers")
    return out


def make_provider(name: str, seed: int = 0) -> Provider:
    if name == "stub":
        return StubProvider(seed=seed)
    if name == "generative":
        return GenerativeProvider()
    if name == "jev":
        return JevProvider()
    raise SystemExit(f"unknown provider {name!r}; choose stub, generative or jev")


ProgressCallback = Callable[[int, int, str], None]


def collect(provider: Provider, ventures: Iterable[LabelledVenture],
            questions: Sequence[Question],
            on_progress: Optional[ProgressCallback] = None
            ) -> Dict[str, Dict[str, Answer]]:
    items = list(ventures)
    out: Dict[str, Dict[str, Answer]] = {}
    for index, venture in enumerate(items, 1):
        state = build_state(venture)
        out[venture.id] = provider.ask(state, questions)
        if on_progress is not None:
            on_progress(index, len(items), venture.id)
    return out
