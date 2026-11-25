"""Append-only call log: one JSON line per model call in runs.jsonl.

Every line records model, parameters, seed, latency and an estimated
list-price cost, so COSTS.md and EXPERIMENTS.md can be written from evidence.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import mock, runlog_path

RUN_ID = os.environ.get("HERITAGE_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


def log_call(
    *,
    stage: str,
    provider: str,
    model: str,
    params: dict[str, Any],
    latency_s: float,
    status: str,
    seed: int | None = None,
    cost_usd: float = 0.0,
    cost_note: str = "",
    cache_key: str | None = None,
    output: str | None = None,
    error: str | None = None,
    attempt: int = 1,
    gpu_minutes: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": RUN_ID,
        "stage": stage,
        "provider": provider,
        "model": model,
        "params": params,
        "seed": seed,
        "latency_s": round(latency_s, 3),
        "gpu_minutes": None if gpu_minutes is None else round(gpu_minutes, 2),
        "status": status,
        "attempt": attempt,
        "est_cost_usd": round(cost_usd, 6),
        "cost_note": cost_note,
        "cache_key": cache_key,
        "output": output,
        "error": (error or "")[:500] or None,
        "mock": mock(),
    }
    if extra:
        record["extra"] = extra
    with runlog_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.elapsed = time.perf_counter() - self.start
        return False
