"""Run GPU jobs on Kaggle through the official `kaggle` CLI.

Flow for one batch: write jobs.json + inputs to a folder -> upload it as a private
dataset -> push a script kernel that reads the dataset (T4 accelerator, internet on)
-> poll until it finishes -> download /kaggle/working -> import results.json.
The kernel scripts live in kaggle/<name>/kernel.py and are the only code that runs remotely.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from ..config import ROOT
from ..media import SR, ffmpeg, write_wav

ACCELERATOR = os.environ.get("KAGGLE_ACCELERATOR", "NvidiaTeslaT4")


def kaggle_bin() -> str | None:
    """The kaggle CLI, from PATH or next to the running Python (the project's .venv)."""
    local = Path(sys.executable).parent / "kaggle"
    return shutil.which("kaggle") or (str(local) if local.exists() else None)


def available() -> bool:
    if not kaggle_bin():
        return False
    home = Path.home() / ".kaggle"
    return bool(
        os.environ.get("KAGGLE_API_TOKEN")
        or os.environ.get("KAGGLE_KEY")
        or (home / "kaggle.json").exists()
        or (home / "credentials.json").exists()
        or (home / "access_token").exists()
    )


def username() -> str:
    user = os.environ.get("KAGGLE_USERNAME")
    if not user:
        cfg = Path.home() / ".kaggle" / "kaggle.json"
        if cfg.exists():
            user = json.loads(cfg.read_text()).get("username")
    if not user:
        raise SystemExit("Set KAGGLE_USERNAME in .env (your Kaggle username).")
    return user


def cli(*args: str, check: bool = True, timeout: int = 900) -> subprocess.CompletedProcess:
    exe = kaggle_bin()
    if not exe:
        raise RuntimeError("kaggle CLI not found; run make setup")
    proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    if check and proc.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-1500:]}")
    return proc


def push_dataset(folder: Path, slug: str, title: str, message: str) -> str:
    ref = f"{username()}/{slug}"
    (folder / "dataset-metadata.json").write_text(json.dumps(
        {"title": title, "id": ref, "licenses": [{"name": "CC0-1.0"}]}, indent=2))
    exists = cli("datasets", "status", ref, check=False).returncode == 0
    if exists:
        cli("datasets", "version", "-p", str(folder), "-m", message)
    else:
        cli("datasets", "create", "-p", str(folder))
    return ref


def wait_dataset_ready(ref: str, timeout_s: int = 1200) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        out = cli("datasets", "status", ref, check=False).stdout.lower()
        if "ready" in out:
            return
        print(f"    dataset {ref}: {out.strip() or 'processing'}")
        time.sleep(15)
    raise TimeoutError(f"dataset {ref} not ready after {timeout_s}s")


def push_kernel(folder: Path) -> None:
    cli("kernels", "push", "-p", str(folder), "--accelerator", ACCELERATOR)


def kernel_status(ref: str) -> str:
    return cli("kernels", "status", ref, check=False).stdout.strip().lower()


def wait_kernel(ref: str, timeout_s: int, poll_s: int = 60) -> str:
    start = time.time()
    time.sleep(20)
    while time.time() - start < timeout_s:
        status = kernel_status(ref)
        mins = (time.time() - start) / 60
        print(f"    [{mins:5.1f} min] {status}")
        for word in ("complete", "error", "cancel"):
            if word in status:
                return word
        time.sleep(poll_s)
    raise TimeoutError(f"kernel {ref} still running after {timeout_s / 3600:.1f} h; rerun the stage later to collect it")


def download_output(ref: str, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    cli("kernels", "output", ref, "-p", str(dest), "-o", timeout=1800)
    return dest


def prepare_kernel(template_dir: Path, work_dir: Path, slug: str, title: str, dataset_ref: str) -> str:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    shutil.copy(template_dir / "kernel.py", work_dir / "kernel.py")
    ref = f"{username()}/{slug}"
    meta = {
        "id": ref,
        "title": title,
        "code_file": "kernel.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "dataset_sources": [dataset_ref],
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": [],
    }
    (work_dir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    return ref


def run_batch(kind: str, job_dir: Path, out_dir: Path, run_id: str, timeout_s: int) -> Path:
    """Upload a job folder, run the matching kernel on a T4, download its outputs."""
    slug = {"shots": "heritage-wan22-shots", "music": "heritage-acestep-music"}[kind]
    data_slug = f"heritage-{kind}-jobs"
    print(f"  uploading {kind} jobs to Kaggle dataset {data_slug} ...")
    dref = push_dataset(job_dir, data_slug, f"heritage {kind} jobs", f"run {run_id}")
    wait_dataset_ready(dref)
    template = ROOT / "kaggle" / ("wan22_i2v" if kind == "shots" else "acestep")
    kref = prepare_kernel(template, job_dir.parent / f"{kind}_kernel", slug, slug, dref)
    print(f"  pushing kernel {kref} on {ACCELERATOR} ...")
    push_kernel(job_dir.parent / f"{kind}_kernel")
    print(f"  waiting for it to finish (watch it at https://www.kaggle.com/code/{kref}) ...")
    status = wait_kernel(kref, timeout_s)
    print(f"  kernel finished with status: {status}; downloading outputs ...")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    return download_output(kref, out_dir)


# ---------------------------------------------------------------- mock backend
def mock_run(kind: str, job_dir: Path, out_dir: Path) -> Path:
    """Stand-in for the kernel: same results.json contract, no GPU, no model."""
    jobs = json.loads((job_dir / "jobs.json").read_text())
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for job in jobs["items"]:
        t0 = time.perf_counter()
        if kind == "shots":
            fname = f"{job['key']}.mp4"
            frames = job["num_frames"]
            ffmpeg([
                "-loop", "1", "-i", job_dir / job["image"],
                "-vf", f"scale={job['width'] * 2}:-2,zoompan=z='1+0.0015*on':d={frames}:s={job['width']}x{job['height']}:fps=24,hue=h='t*20'",
                "-frames:v", frames, "-pix_fmt", "yuv420p", out_dir / fname,
            ])
        else:
            fname = f"{job['key']}.wav"
            sec = job["duration_s"]
            t = np.arange(int(sec * SR)) / SR
            base = {"G major": 196.0, "E minor": 164.8}.get(job.get("key_scale"), 174.6)
            chord = sum(np.sin(2 * np.pi * base * r * t) for r in (1.0, 1.25, 1.5))
            trem = 0.6 + 0.4 * np.sin(2 * np.pi * (job["bpm"] / 60.0) * t)
            mono = 0.12 * chord * trem
            write_wav(out_dir / fname, np.stack([mono, mono], axis=1).astype(np.float32))
        items.append({"key": job["key"], "hash": job["hash"], "status": "ok", "file": fname,
                      "latency_s": round(time.perf_counter() - t0, 2), "error": None})
    (out_dir / "results.json").write_text(json.dumps(
        {"kind": kind, "gpu": "mock", "dtype": "mock", "items": items}, indent=2))
    return out_dir
