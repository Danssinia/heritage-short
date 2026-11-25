"""Shared logic for the two GPU stages (shots on Wan 2.2, music on ACE-Step).

A stage builds a list of jobs, each with a key and an input hash. Jobs whose output
is already cached are dropped. The rest go to Kaggle in one batch (or to the mock
backend in tests). Results are matched back by key AND hash, so a stale result from
an older storyboard is never imported. Failed jobs are counted; after max_attempts
the stage stops sending them and the edit uses the shot's fallback.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable

from . import config
from .cache import Manifest
from .prices import gpu_cost
from .providers import kaggle
from .runlog import RUN_ID, log_call


def job_paths(kind: str) -> tuple[Path, Path]:
    base = config.stage_dir("_kaggle")
    return base / f"{kind}_job", base / f"{kind}_out"


def failures(manifest: Manifest, kind: str, key: str, h: str) -> int:
    entry = manifest.get(f"{kind}_fail:{key}") or {}
    return entry.get("meta", {}).get("count", 0) if entry.get("hash") == h else 0


def record_failure(manifest: Manifest, kind: str, key: str, h: str) -> int:
    n = failures(manifest, kind, key, h) + 1
    manifest.put(f"{kind}_fail:{key}", h, [], {"count": n})
    return n


def write_job_dir(kind: str, cfg: dict, items: list[dict], files: list[Path]) -> Path:
    job_dir, _ = job_paths(kind)
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True)
    for f in files:
        shutil.copy(f, job_dir / f.name)
    (job_dir / "jobs.json").write_text(json.dumps({"kind": kind, "run_id": RUN_ID, "config": cfg, "items": items}, indent=2, ensure_ascii=False))
    return job_dir


def bundle(kind: str) -> Path:
    """Zip the job folder and kernel for running by hand in the Kaggle website."""
    job_dir, _ = job_paths(kind)
    kernel = config.ROOT / "kaggle" / ("wan22_i2v" if kind == "shots" else "acestep") / "kernel.py"
    out = config.stage_dir("_kaggle") / f"{kind}_bundle.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(job_dir.iterdir()):
            if f.name != "dataset-metadata.json":
                z.write(f, f"heritage-{kind}-jobs/{f.name}")
        z.write(kernel, "kernel.py")
    return out


def run_jobs(kind: str, cfg: dict, items: list[dict], files: list[Path], no_remote: bool, timeout_s: int) -> Path | None:
    job_dir = write_job_dir(kind, cfg, items, files)
    _, out_dir = job_paths(kind)
    if config.mock():
        return kaggle.mock_run(kind, job_dir, out_dir)
    if no_remote or not kaggle.available():
        z = bundle(kind)
        why = "--no-remote was given" if no_remote else "the kaggle CLI or its credentials were not found"
        print(f"  {len(items)} {kind} job(s) not sent ({why}).")
        print(f"  Manual route: upload {z.relative_to(config.ROOT)} on kaggle.com (see README, 'Running Kaggle by hand'),")
        print(f"  then: python -m pipeline.{kind} --import <downloaded_output_folder_or_zip>")
        return None
    try:
        return kaggle.run_batch(kind, job_dir, out_dir, RUN_ID, timeout_s)
    except Exception as e:  # keep going: the edit falls back for missing shots
        print(f"  Kaggle run failed: {e}")
        for it in items:
            log_call(stage=kind, provider="kaggle", model=cfg["model"], params={"key": it["key"]},
                     latency_s=0.0, status="error", error=str(e), cache_key=it["hash"])
        return None


def import_results(kind: str, results_dir: Path, expected: dict[str, str], cfg: dict,
                   place: Callable[[dict, Path], Path], manifest: Manifest) -> dict[str, Any]:
    """Copy outputs whose key+hash match the current storyboard; log one line per job."""
    if str(results_dir).endswith(".zip"):
        unzip_to = config.stage_dir("_kaggle") / f"{kind}_import"
        if unzip_to.exists():
            shutil.rmtree(unzip_to)
        with zipfile.ZipFile(results_dir) as z:
            z.extractall(unzip_to)
        results_dir = unzip_to
    found = list(Path(results_dir).rglob("results.json"))
    if not found:
        raise SystemExit(f"No results.json under {results_dir}")
    res_file = found[0]
    res = json.loads(res_file.read_text())
    summary = {"ok": [], "failed": [], "stale": []}
    for it in res.get("items", []):
        key, h = it["key"], it.get("hash")
        if expected.get(key) != h:
            summary["stale"].append(key)
            continue
        minutes = (it.get("latency_s") or 0) / 60.0
        common = dict(stage=kind, provider="kaggle", model=cfg["model"],
                      params={"key": key, "gpu": res.get("gpu"), "dtype": res.get("dtype"), **(it.get("params") or {})},
                      seed=it.get("seed"), latency_s=it.get("latency_s") or 0.0, gpu_minutes=minutes,
                      cost_usd=gpu_cost(minutes), cost_note="list-price equivalent of free Kaggle T4 time",
                      cache_key=h)
        if it.get("status") == "ok" and (res_file.parent / it["file"]).exists():
            dest = place(it, res_file.parent / it["file"])
            manifest.put(f"{kind}:{key}", h, [dest], {"gpu": res.get("gpu"), "latency_s": it.get("latency_s")})
            log_call(status="ok", output=str(dest.relative_to(config.ROOT)), **common)
            summary["ok"].append(key)
        else:
            n = record_failure(manifest, kind, key, h)
            log_call(status="error", error=it.get("error") or "missing output file", attempt=n, **common)
            summary["failed"].append(key)
    print(f"  imported {len(summary['ok'])} ok, {len(summary['failed'])} failed, {len(summary['stale'])} stale (ignored)")
    return summary
