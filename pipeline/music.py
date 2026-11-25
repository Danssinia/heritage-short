"""Stage: music. Score cues with ACE-Step 1.5 on a Kaggle T4, plus placeholder music for the radio cut.

Each cue spans its shots (the last one also covers the end card) and is generated
with headroom, then trimmed to the real length in the edit. Each cue gets `candidates` takes
(seed, seed+1, ...). Listen to outputs/music/<cue>_c<k>.wav under the narration,
then set chosen_candidate in storyboard.json and note why in EXPERIMENTS.md.

Usage:
  python -m pipeline.music                 generate changed cues on Kaggle
  python -m pipeline.music --placeholder   only make placeholder music (radio cut)
  python -m pipeline.music --no-remote / --import PATH   as in pipeline.shots
"""
from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path

import numpy as np

from .common import remote, story
from .common.cache import Manifest, stable_hash
from .common.config import stage_dir
from .common.media import SR, write_wav

TIMEOUT_S = 3 * 3600


def take_path(cue_id: str, k: int) -> Path:
    return stage_dir("music") / f"{cue_id}_c{k}.wav"


def placeholder_path(cue_id: str) -> Path:
    return stage_dir("music") / f"placeholder_{cue_id}.wav"


def cue_length(sb: dict, cue_id: str) -> float:
    """Generated length: planned cue length + 8 s headroom, rounded up to 5 s.

    Based on planned shot durations (not measured narration), so re-recording one
    narration line does not change the music hash and does not regenerate the score.
    The edit trims each take to the real cue length.
    """
    planned = story.timeline(sb, timings={})
    c = next(c for c in planned["cues"] if c["id"] == cue_id)
    return float(max(10, math.ceil((c["duration"] + 8.0) / 5.0) * 5))


def make_placeholders(sb: dict) -> None:
    """Soft sustained chord per cue: not a model call, so not logged in runs.jsonl."""
    roots = {"major": (1.0, 1.26, 1.5), "minor": (1.0, 1.19, 1.5)}
    notes = {"C": 130.8, "D": 146.8, "E": 164.8, "F": 174.6, "G": 196.0, "A": 220.0, "B": 246.9}
    for cue in sb["music"]["cues"]:
        sec = cue_length(sb, cue["id"])
        tt = np.arange(int(sec * SR)) / SR
        root = notes.get(cue["key"][0], 196.0)
        chord = sum(np.sin(2 * np.pi * root * r * tt) for r in roots["minor" if "minor" in cue["key"] else "major"])
        swell = 0.75 + 0.25 * np.sin(2 * np.pi * 0.1 * tt)
        mono = (0.08 * chord * swell).astype(np.float32)
        write_wav(placeholder_path(cue["id"]), np.stack([mono, mono], axis=1))
    print(f"music: placeholder cues written to {stage_dir('music').name}/placeholder_*.wav")


def build_jobs(sb: dict, manifest: Manifest):
    d = sb["defaults"]["music"]
    cfg = {"model": d["model"], "dtype": "auto"}
    items, expected = [], {}
    for cue in sb["music"]["cues"]:
        length = cue_length(sb, cue["id"])
        for k in range(cue["candidates"]):
            key = f"{cue['id']}_c{k}"
            params = {"caption": cue["caption"], "lyrics": "[Instrumental]", "duration_s": length, "bpm": cue["bpm"],
                      "key_scale": cue["key"], "time_signature": cue["time_signature"], "seed": cue["seed"] + k,
                      "steps": d["steps"]}
            h = stable_hash({**params, **cfg})
            expected[key] = h
            if manifest.fresh(f"music:{key}", h) or remote.failures(manifest, "music", key, h) >= 2:
                continue
            items.append({"key": key, "hash": h, **params})
    return cfg, items, expected


def place(item: dict, src: Path) -> Path:
    cue, k = item["key"].rsplit("_c", 1)
    dest = take_path(cue, int(k))
    shutil.copy(src, dest)
    return dest


def chosen_take(sb: dict, cue: dict) -> Path | None:
    p = take_path(cue["id"], story.chosen(cue.get("chosen_candidate")))
    return p if p.exists() else None


def run(placeholder_only: bool = False, no_remote: bool = False, import_path: str | None = None) -> None:
    sb = story.load()
    make_placeholders(sb)
    if placeholder_only:
        return
    manifest = Manifest()
    cfg, items, expected = build_jobs(sb, manifest)
    if import_path:
        remote.import_results("music", Path(import_path), expected, cfg, place, manifest)
        return
    if not items:
        print("music: nothing to generate (all cached)")
        return
    print(f"music: {len(items)} take(s) to generate")
    results = remote.run_jobs("music", cfg, items, [], no_remote, TIMEOUT_S)
    if results:
        remote.import_results("music", results, expected, cfg, place, manifest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placeholder", action="store_true")
    ap.add_argument("--no-remote", action="store_true")
    ap.add_argument("--import", dest="import_path")
    a = ap.parse_args()
    run(a.placeholder, a.no_remote, a.import_path)
