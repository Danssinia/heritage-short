"""Deterministic caching by input hash.

Each artifact has a key (for example "keyframe:s03") and a hash of exactly the
inputs that shape it. The manifest maps key -> hash and paths. If the stored
hash matches and the files exist, the stage skips the model call. Changing one
shot's prompt changes only that shot's hash, so only that shot regenerates;
downstream hashes include upstream file hashes, so the change flows forward.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT, out_dir

CACHE_VERSION = 1


def stable_hash(obj: Any) -> str:
    blob = json.dumps({"v": CACHE_VERSION, "data": obj}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


class Manifest:
    def __init__(self, path: Path | None = None):
        self.path = path or out_dir() / "manifest.json"
        self.data: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def fresh(self, key: str, h: str) -> bool:
        entry = self.data.get(key)
        if not entry or entry.get("hash") != h:
            return False
        return all((ROOT / p).exists() for p in entry.get("paths", []))

    def get(self, key: str) -> dict[str, Any] | None:
        return self.data.get(key)

    def paths(self, key: str) -> list[Path]:
        entry = self.data.get(key) or {}
        return [ROOT / p for p in entry.get("paths", [])]

    def put(self, key: str, h: str, paths: list[Path], meta: dict[str, Any] | None = None) -> None:
        self.data[key] = {
            "hash": h,
            "paths": [str(Path(p).resolve().relative_to(ROOT)) for p in paths],
            "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **({"meta": meta} if meta else {}),
        }
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(tmp, self.path)
