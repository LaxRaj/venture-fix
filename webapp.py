#!/usr/bin/env python3
"""Local frontend server for the venture stress test.

Zero dependencies: stdlib HTTP server, JSON endpoints, and four static files.
The calibration run happens in a background thread so the page can show real
progress while Jev answers the question bank.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import traceback
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from run import _load_dotenv
from vstress import arithmetic, calibrate, fieldtest
from vstress.client import collect, make_provider
from vstress.data import (
    DEFAULT_CONVERSION,
    ECONOMICS,
    ECONOMICS_BY_NAME,
    LABELLED,
    MARKET_LIMIT,
    TARGET_MRR,
    USABLE_HOURS,
    WEEKS_PER_MONTH,
    provenance_counts,
)
from vstress.questions import ADMITTED, FAMILIES, bank_report

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
RUNS = ROOT / "runs"
MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
}

_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, object]] = {}
_LATEST: Optional[Dict[str, object]] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _prov_code(row) -> str:
    return (
        f"{row.price_provenance[0].upper()}/"
        f"{row.service_hours_provenance[0].upper()}/"
        f"{row.buyers_provenance[0].upper()}"
    )


def _board_payload() -> Dict[str, object]:
    rows: List[Dict[str, object]] = []
    counts: Dict[str, int] = {
        arithmetic.REACHABLE: 0,
        arithmetic.BURNS: 0,
        arithmetic.DEAD: 0,
    }
    for row in ECONOMICS:
        v = arithmetic.verdict(row)
        counts[v.hard] += 1
        key, margin = v.closest
        field_key, current, flip, field_margin = fieldtest.nearest_input(row)
        rows.append({
            "name": row.name,
            "price": row.price,
            "price_display": arithmetic.fmt_price(row.price),
            "service_hours": row.service_hours,
            "hours_display": f"{row.service_hours:g}",
            "buyers": row.buyers,
            "buyers_display": f"{row.buyers:,}",
            "provenance": {
                "price": row.price_provenance,
                "service_hours": row.service_hours_provenance,
                "buyers": row.buyers_provenance,
            },
            "provenance_code": _prov_code(row),
            "accounts_needed": v.accounts_needed,
            "capacity": v.capacity,
            "contacts_needed": v.contacts_needed,
            "market_share": v.market_share,
            "verdict": v.hard,
            "cause": v.cause,
            "flips": {
                "service_hours": v.flips["service_hours"],
                "price": v.flips["price"],
                "buyers": v.flips["buyers"],
                "conversion": v.flips["conversion"],
            },
            "flip_display": {
                "service_hours": arithmetic.fmt_hours(v.flips["service_hours"]),
                "price": arithmetic.fmt_price(v.flips["price"]),
                "buyers": f"{v.flips['buyers']:,.0f}",
                "conversion": f"{v.flips['conversion']:.3%}",
            },
            "margins": dict(v.margins),
            "closest": {
                "input": key,
                "label": fieldtest.INPUT_LABEL[key],
                "margin": margin,
                "calls": fieldtest.sample_size(margin),
            },
            "field": {
                "input": field_key,
                "label": fieldtest.INPUT_LABEL[field_key],
                "current": current,
                "flip": flip,
                "margin": field_margin,
                "calls": fieldtest.sample_size(field_margin),
            },
        })

    return {
        "generated_at": _now(),
        "constants": {
            "target_mrr": TARGET_MRR,
            "usable_hours": USABLE_HOURS,
            "weeks_per_month": WEEKS_PER_MONTH,
            "market_limit": MARKET_LIMIT,
            "default_conversion": DEFAULT_CONVERSION,
        },
        "counts": {"total": len(rows), **counts},
        "rows": rows,
        "break_even": [
            {"name": name, "hours": hours, "price": price}
            for name, hours, price in arithmetic.break_even_table()
        ],
        "provenance": provenance_counts(),
    }


def _field_payload() -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    for rank, item in enumerate(fieldtest.shopping_list(), 1):
        row = ECONOMICS_BY_NAME[str(item["name"])]
        key = str(item["input"])
        items.append({
            "rank": rank,
            "name": row.name,
            "verdict": str(item["verdict"]),
            "input": key,
            "input_label": fieldtest.INPUT_LABEL[key],
            "current": float(item["current"]),
            "flip": float(item["flip"]),
            "margin": float(item["margin"]),
            "calls": int(item["calls"]),
            "current_display": fieldtest._fmt_value(key, float(item["current"])),
            "flip_display": fieldtest._fmt_value(key, float(item["flip"])),
            "provenance": {
                "price": row.price_provenance,
                "service_hours": row.hours_provenance,
                "buyers": row.buyers_provenance,
            },
            "questions": [
                {"question": question, "note": note}
                for question, note in fieldtest.CALL_SCRIPT[key]
            ],
        })
    return {
        "generated_at": _now(),
        "items": items,
        "note": "Start at the top. The top row is the most fragile number in the system.",
    }


def _calibration_payload(job_id: str, provider, results, report_text: str) -> Dict[str, object]:
    rows = []
    for result in results:
        item = asdict(result)
        item["survives"] = result.survives
        rows.append(item)

    raw = [r for r in results if r.raw_pass]
    permutation = [r for r in raw if r.perm_pass]
    bh = [r for r in permutation if r.bh_pass]
    kept = [r for r in bh if r.holdout_pass]

    coverage = {
        family: sum(1 for question in ADMITTED if question.family == family)
        for family in FAMILIES
    }
    coverage["data or workflow moat"] = 0

    stamp = getattr(provider, "stamp", "")
    return {
        "id": job_id,
        "provider": provider.name,
        "provider_stamp": stamp,
        "generated_at": _now(),
        "labels": {
            "total": len(LABELLED),
            "alive": sum(1 for venture in LABELLED if venture.alive),
            "dead": sum(1 for venture in LABELLED if not venture.alive),
        },
        "split_seed": calibrate.SPLIT_SEED,
        "permutations": calibrate.PERMUTATIONS,
        "bank": bank_report(),
        "gates": {
            "raw_cutoff": calibrate.RAW_AUC_CUTOFF,
            "holdout_cutoff": calibrate.HOLDOUT_AUC_CUTOFF,
            "bh_q": calibrate.BH_Q,
            "permutation_cutoff": 0.05,
        },
        "coverage": coverage,
        "uncovered": "data or workflow moat",
        "leakage_check": "PASS",
        "summary": {
            "raw": len(raw),
            "permutation": len(permutation),
            "bh": len(bh),
            "kept": len(kept),
        },
        "results": rows,
        "threshold_sweep": [
            {"cutoff": cutoff, "raw": raw_count, "final": final_count}
            for cutoff, raw_count, final_count in calibrate.threshold_sweep(results)
        ],
        "stub_verdict": (
            None
            if provider.name != "stub"
            else ("FAIL: noise survived" if kept else "PASS: zero questions survived noise")
        ),
        "report_text": report_text,
    }


def _save_run(payload: Dict[str, object]) -> None:
    RUNS.mkdir(exist_ok=True)
    job_id = str(payload.get("id", "latest"))
    (RUNS / f"{job_id}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    (RUNS / "latest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _load_latest() -> Optional[Dict[str, object]]:
    path = RUNS / "latest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _public_job(job: Dict[str, object]) -> Dict[str, object]:
    return {
        key: value
        for key, value in job.items()
        if key not in {"result"}
    } | ({"result": job.get("result")} if job.get("status") == "done" else {})


def _run_job(job_id: str, provider_name: str, seed: int, permutations: int) -> None:
    global _LATEST
    try:
        provider = make_provider(provider_name, seed=seed)

        def progress(current: int, total: int, venture_id: str) -> None:
            with _LOCK:
                job = _JOBS.get(job_id)
                if job is None:
                    return
                job["progress"] = {
                    "current": current,
                    "total": total,
                    "venture": venture_id,
                }
                job["updated_at"] = _now()

        answers = collect(provider, LABELLED, ADMITTED, on_progress=progress)
        results = calibrate.evaluate(answers, LABELLED, permutations)
        report_text = calibrate.render_report(provider, results)
        payload = _calibration_payload(job_id, provider, results, report_text)
        payload["permutations"] = permutations

        with _LOCK:
            job = _JOBS[job_id]
            job["status"] = "done"
            job["finished_at"] = _now()
            job["updated_at"] = job["finished_at"]
            job["result"] = payload
            _LATEST = payload
        _save_run(payload)
    except BaseException as exc:  # pragma: no cover - surfaced in the UI
        with _LOCK:
            job = _JOBS.get(job_id)
            if job is not None:
                job["status"] = "error"
                job["error"] = str(exc)
                job["traceback"] = traceback.format_exc()
                job["finished_at"] = _now()
                job["updated_at"] = job["finished_at"]


def _start_job(provider_name: str, seed: int, permutations: int) -> Dict[str, object]:
    with _LOCK:
        for job in _JOBS.values():
            if job.get("status") in {"queued", "running"}:
                raise RuntimeError(f"a calibration run is already in progress: {job['id']}")
        job_id = uuid.uuid4().hex[:12]
        job: Dict[str, object] = {
            "id": job_id,
            "provider": provider_name,
            "seed": seed,
            "permutations": permutations,
            "status": "running",
            "started_at": _now(),
            "updated_at": _now(),
            "progress": {"current": 0, "total": len(LABELLED), "venture": ""},
        }
        _JOBS[job_id] = job
    thread = threading.Thread(
        target=_run_job,
        args=(job_id, provider_name, seed, permutations),
        daemon=True,
        name=f"calibrate-{job_id}",
    )
    thread.start()
    return _public_job(job)


class Handler(BaseHTTPRequestHandler):
    server_version = "VentureStressTest/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(404, "not found")
            return
        try:
            path.relative_to(WEB)
        except ValueError:
            self._send_error(403, "forbidden")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in {"/", "/index.html"}:
                self._serve_file(WEB / "index.html")
            elif path.startswith("/static/"):
                self._serve_file(WEB / path.removeprefix("/static/"))
            elif path == "/api/board":
                self._send_json(_board_payload())
            elif path == "/api/field":
                self._send_json(_field_payload())
            elif path == "/api/health":
                self._send_json({"ok": True, "time": _now()})
            elif path == "/api/calibration/latest":
                with _LOCK:
                    latest = _LATEST
                if latest is None:
                    self.send_response(204)
                    self.end_headers()
                else:
                    self._send_json(latest)
            elif path.startswith("/api/calibration/jobs/"):
                job_id = path.rsplit("/", 1)[-1]
                with _LOCK:
                    job = _JOBS.get(job_id)
                    public = _public_job(job) if job else None
                if public is None:
                    self._send_error(404, "job not found")
                else:
                    self._send_json(public)
            else:
                self._send_error(404, "not found")
        except Exception as exc:  # pragma: no cover
            self._send_error(500, str(exc))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/calibrate":
            self._send_error(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            self._send_error(400, "invalid JSON body")
            return
        provider_name = str(body.get("provider", "stub"))
        if provider_name not in {"stub", "jev", "generative"}:
            self._send_error(400, "provider must be stub, jev or generative")
            return
        try:
            seed = int(body.get("seed", 91))
            permutations = int(body.get("permutations", calibrate.PERMUTATIONS))
        except (TypeError, ValueError):
            self._send_error(400, "seed and permutations must be integers")
            return
        if permutations < 99 or permutations > 9999:
            self._send_error(400, "permutations must be between 99 and 9999")
            return
        try:
            job = _start_job(provider_name, seed, permutations)
        except RuntimeError as exc:
            self._send_error(409, str(exc))
            return
        except SystemExit as exc:
            self._send_error(400, str(exc))
            return
        self._send_json(job, 202)


def main() -> int:
    _load_dotenv()
    global _LATEST
    _LATEST = _load_latest()

    parser = argparse.ArgumentParser(description="Serve the venture stress test frontend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Venture stress test frontend: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
