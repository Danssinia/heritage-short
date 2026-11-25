"""Stage: references. Character and location reference sheets, made before any keyframe.

For each character and location, generates `reference_candidates` images (seed, seed+1, ...)
and a contact sheet. You look at outputs/references/contact_sheet.jpg, pick the best
candidate for each subject and write its index into `approved_candidate` in storyboard.json.
That approved image becomes the golden reference every keyframe is conditioned on.

Usage: python -m pipeline.references [--force]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .common import story
from .common.cache import Manifest, file_hash, stable_hash
from .common.config import ROOT, stage_dir
from .common.prices import klein_cost
from .common.providers import cloudflare
from .common.retry import with_retries
from .common.runlog import Timer, log_call
from .common.sheets import contact_sheet

REF_W, REF_H = 1024, 1024
PHOTO_HINT = (" Base the face, features and build on the person in the reference photo,"
              " redrawn as an illustrated character in this style, not a photograph.")


def candidate_path(subject_id: str, k: int) -> Path:
    return stage_dir("references") / f"{subject_id}_c{k}.png"


def approved_path(sb: dict, subject_id: str) -> Path:
    subj = story.subjects(sb)[subject_id]
    return candidate_path(subject_id, story.chosen(subj.get("approved_candidate")))


def generate(model: str, prompt: str, seed: int, width: int, height: int, out: Path, stage: str,
             refs: list[bytes] | None = None, cache_key: str = "", extra: dict | None = None) -> None:
    def call(attempt: int):
        with Timer() as t:
            try:
                data = cloudflare.generate_image(model, prompt, width, height, seed, refs=refs)
            except Exception as e:
                log_call(stage=stage, provider="cloudflare", model=model, params={"width": width, "height": height, "refs": len(refs or [])},
                         seed=seed, latency_s=0.0, status="error", error=str(e), cache_key=cache_key, attempt=attempt)
                raise
        out.write_bytes(data)
        log_call(stage=stage, provider="cloudflare", model=model,
                 params={"width": width, "height": height, "refs": len(refs or []), "prompt_chars": len(prompt), **(extra or {})},
                 seed=seed, latency_s=t.elapsed, status="ok",
                 cost_usd=klein_cost(width, height, len(refs or [])) if "klein-4b" in model else 0.0,
                 cost_note="list price, free daily allowance used", cache_key=cache_key,
                 output=str(out.relative_to(ROOT)), attempt=attempt)

    with_retries(call, attempts=4)


def run(force: bool = False) -> None:
    sb = story.load()
    d = sb["defaults"]["keyframe"]
    n = d.get("reference_candidates", 4)
    manifest = Manifest()
    made = cached = 0
    rows = []
    for subj in sb["characters"] + sb["locations"]:
        prompt = story.reference_prompt(sb, subj)
        paths = [candidate_path(subj["id"], k) for k in range(n)]
        refs, photo_hash = None, None
        if subj.get("photo"):
            photo = ROOT / subj["photo"]
            if not photo.is_file():
                if all(p.exists() for p in paths):
                    print(f"  note: {subj['id']}: photo {subj['photo']} not found; keeping the existing candidates")
                    cached += n
                    rows.append((subj["id"], paths))
                    continue
                raise SystemExit(f"references: {subj['id']} has photo {subj['photo']} but the file is missing "
                                 f"(put it in private/ or remove \"photo\" from storyboard.json)")
            refs = [photo.read_bytes()]
            photo_hash = file_hash(photo)
            prompt += PHOTO_HINT
        for k in range(n):
            seed = subj["seed"] + k
            key = f"reference:{subj['id']}:c{k}"
            inputs = {"model": d["model"], "prompt": prompt, "seed": seed, "w": REF_W, "h": REF_H}
            if photo_hash:
                inputs["photo"] = photo_hash
            h = stable_hash(inputs)
            out = paths[k]
            if not force and manifest.fresh(key, h):
                cached += 1
                continue
            print(f"  reference {subj['id']} candidate {k} ...")
            generate(d["model"], prompt, seed, REF_W, REF_H, out, "references", refs=refs, cache_key=h,
                     extra={"subject": subj["id"], "candidate": k, "from_photo": refs is not None})
            manifest.put(key, h, [out])
            made += 1
        rows.append((subj["id"], paths))
    sheet = contact_sheet(rows, stage_dir("references") / "contact_sheet.jpg")
    print(f"references: {made} generated, {cached} cached. Review {sheet.relative_to(ROOT)} and set approved_candidate.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    run(ap.parse_args().force)
