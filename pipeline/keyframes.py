"""Stage: keyframes. One still per shot, conditioned on the approved reference images.

For each shot: composes the prompt (shot prompt + fixed character/location wording +
style block), attaches the approved reference images of the characters and location
in the shot (FLUX.2 klein takes up to four), and generates `candidates` images.
The chosen candidate is copied to outputs/keyframes/<shot>.png, which the shots and
assemble stages use. Review outputs/keyframes/contact_sheet.jpg and set
keyframe.chosen_candidate in storyboard.json.

Usage: python -m pipeline.keyframes [--force] [--only s03]
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .common import story
from .common.cache import Manifest, file_hash, stable_hash
from .common.config import ROOT, stage_dir
from .common.sheets import contact_sheet
from .references import approved_path, generate


def candidate_path(shot_id: str, k: int) -> Path:
    return stage_dir("keyframes") / f"{shot_id}_c{k}.png"


def final_path(shot_id: str) -> Path:
    return stage_dir("keyframes") / f"{shot_id}.png"


def shot_refs(sb: dict, shot: dict) -> list[Path]:
    if not shot["keyframe"].get("use_references", True):
        return []
    ids = list(shot["characters"])[:3] + [shot["location"]]
    paths = [approved_path(sb, i) for i in ids]
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"{shot['id']}: reference images missing ({', '.join(p.name for p in missing)}). Run `make references` first.")
    return paths[:4]


def run(force: bool = False, only: list[str] | None = None) -> None:
    sb = story.load()
    d = sb["defaults"]["keyframe"]
    manifest = Manifest()
    made = cached = 0
    rows = []
    for shot in sb["shots"]:
        sid = shot["id"]
        refs = shot_refs(sb, shot)
        prompt = story.keyframe_prompt(sb, shot)
        paths = []
        for k in range(d["candidates"]):
            seed = shot["keyframe"]["seed"] + k
            key = f"keyframe:{sid}:c{k}"
            h = stable_hash({"model": d["model"], "prompt": prompt, "seed": seed, "w": d["width"], "h": d["height"],
                             "refs": [file_hash(p) for p in refs]})
            out = candidate_path(sid, k)
            paths.append(out)
            if (only and sid not in only) or (not force and manifest.fresh(key, h)):
                cached += 1
                continue
            print(f"  keyframe {sid} candidate {k} ...")
            generate(d["model"], prompt, seed, d["width"], d["height"], out, "keyframes",
                     refs=[p.read_bytes() for p in refs], cache_key=h, extra={"shot": sid, "candidate": k})
            manifest.put(key, h, [out])
            made += 1
        rows.append((sid, paths))
        pick = paths[story.chosen(shot["keyframe"].get("chosen_candidate"))]
        if pick.exists():
            final = final_path(sid)
            fh = file_hash(pick)
            if not manifest.fresh(f"keyframe:{sid}", fh):
                shutil.copy(pick, final)
                manifest.put(f"keyframe:{sid}", fh, [final], {"candidate": pick.name})
    sheet = contact_sheet(rows, stage_dir("keyframes") / "contact_sheet.jpg")
    print(f"keyframes: {made} generated, {cached} cached. Review {sheet.relative_to(ROOT)} and set chosen_candidate.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", help="shot ids to (re)generate, e.g. --only s03 s07")
    a = ap.parse_args()
    run(a.force, a.only)
