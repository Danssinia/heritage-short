"""Stage: shots. Image-to-video with Wan 2.2 TI2V-5B on a Kaggle T4.

Each i2v shot becomes a job keyed by a hash of: the chosen keyframe file, motion
prompt, negative prompt, seed, model, size, frame count, steps, guidance and dtype.
Only shots whose hash changed are sent. Shots that fail max_attempts times are left
to their fallback (Ken Burns or still), which the assemble stage renders locally.

Usage:
  python -m pipeline.shots                  send changed shots to Kaggle and wait
  python -m pipeline.shots --no-remote      do not contact Kaggle; write a bundle for manual upload
  python -m pipeline.shots --import PATH    import a downloaded Kaggle output folder or zip
  python -m pipeline.shots --only s03       limit to some shots
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .common import remote, story
from .common.cache import Manifest, file_hash, stable_hash
from .common.config import stage_dir
from .keyframes import final_path as keyframe_path

TIMEOUT_S = 11 * 3600  # Kaggle sessions stop at about 12 h


def clip_path(shot_id: str) -> Path:
    return stage_dir("shots") / f"{shot_id}.mp4"


def build_jobs(sb: dict, manifest: Manifest, only: list[str] | None = None, include_cached: bool = False):
    d = sb["defaults"]["shot"]
    cfg = {"model": d["model"], "dtype": d["dtype"]}
    items, files, expected, skipped = [], [], {}, []
    for shot in sb["shots"]:
        sid, m = shot["id"], shot["motion"]
        if m["mode"] != "i2v" or (only and sid not in only):
            continue
        kf = keyframe_path(sid)
        if not kf.exists():
            skipped.append(f"{sid} (no keyframe yet)")
            continue
        frames = story.num_frames(m["clip_s"], d["fps"])
        params = {"prompt": m["prompt"], "negative_prompt": sb["style"]["negative_prompt"], "seed": m["seed"],
                  "width": d["width"], "height": d["height"], "num_frames": frames, "steps": d["steps"],
                  "guidance": d["guidance"]}
        h = stable_hash({"keyframe": file_hash(kf), **params, **cfg})
        expected[sid] = h
        if manifest.fresh(f"shots:{sid}", h) and not include_cached:
            continue
        if remote.failures(manifest, "shots", sid, h) >= d["max_attempts"]:
            skipped.append(f"{sid} (failed {d['max_attempts']}x, using {m['fallback']})")
            continue
        img = stage_dir("_kaggle") / "stage_images" / f"{sid}.png"
        img.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(kf, img)
        items.append({"key": sid, "hash": h, "image": img.name, **params})
        files.append(img)
    return cfg, items, files, expected, skipped


def place(item: dict, src: Path) -> Path:
    dest = clip_path(item["key"])
    shutil.copy(src, dest)
    return dest


def run(no_remote: bool = False, only: list[str] | None = None, import_path: str | None = None) -> None:
    sb = story.load()
    manifest = Manifest()
    cfg, items, files, expected, skipped = build_jobs(sb, manifest, only)
    for s in skipped:
        print(f"  skip {s}")
    if import_path:
        remote.import_results("shots", Path(import_path), expected, cfg, place, manifest)
        return
    if not items:
        print("shots: nothing to generate (all cached or not i2v)")
        return
    print(f"shots: {len(items)} job(s) to generate: {', '.join(i['key'] for i in items)}")
    results = remote.run_jobs("shots", cfg, items, files, no_remote, TIMEOUT_S)
    if results:
        remote.import_results("shots", results, expected, cfg, place, manifest)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-remote", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--import", dest="import_path")
    a = ap.parse_args()
    run(a.no_remote, a.only, a.import_path)
