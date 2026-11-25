"""Paths, environment and the mock switch, shared by every stage.

Secrets come from the environment or a local .env file (never committed).
HERITAGE_MOCK=1 swaps every model call for a local stand-in and writes to
outputs_mock/ and runs_mock.jsonl, so tests never touch the real outputs or log.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")


def mock() -> bool:
    return os.environ.get("HERITAGE_MOCK") == "1"


def out_dir() -> Path:
    d = ROOT / ("outputs_mock" if mock() else "outputs")
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_dir(name: str) -> Path:
    d = out_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def runlog_path() -> Path:
    return ROOT / ("runs_mock.jsonl" if mock() else "runs.jsonl")


def env(name: str, required: bool = True, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(
            f"Missing {name}. Copy .env.example to .env and fill it in (see README, step 2)."
        )
    return value


STORYBOARD = ROOT / "storyboard.json"
