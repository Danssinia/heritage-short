"""Summarise runs.jsonl into the measurement tables for COSTS.md.

Usage: python -m pipeline.costs   (prints Markdown; paste it into COSTS.md)
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict

from .common.config import runlog_path


def main() -> None:
    path = runlog_path()
    if not path.exists():
        print("runs.jsonl is empty: run the pipeline first.")
        return
    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["stage"], r["model"])].append(r)
    print("| Stage | Model | Calls (ok / failed) | Median latency (s) | Total latency (min) | GPU minutes | List-price equivalent (USD) |")
    print("|---|---|---|---|---|---|---|")
    total_cost = total_gpu = 0.0
    for (stage, model), rs in sorted(groups.items()):
        ok = [r for r in rs if r["status"] == "ok"]
        lat = [r["latency_s"] for r in ok if r.get("latency_s")]
        gpu = sum(r.get("gpu_minutes") or 0 for r in rs)
        cost = sum(r.get("est_cost_usd") or 0 for r in rs)
        total_cost += cost
        total_gpu += gpu
        print(f"| {stage} | {model} | {len(ok)} / {len(rs) - len(ok)} | {statistics.median(lat) if lat else 0:.2f} | "
              f"{sum(lat) / 60:.1f} | {gpu:.1f} | {cost:.4f} |")
    print(f"\nTotal: {len(rows)} calls, {total_gpu:.1f} GPU minutes, ${total_cost:.4f} list-price equivalent (we paid $0).")


if __name__ == "__main__":
    main()
