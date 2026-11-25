"""Validate storyboard.json: JSON Schema first, then the cross-field rules a schema cannot express.

Usage: python -m pipeline.validate [path/to/storyboard.json]
Exits non-zero on any error, so `make film` stops before any model is called.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "storyboard.schema.json"


def semantic_errors(sb: dict) -> list[str]:
    errs: list[str] = []
    char_ids = [c["id"] for c in sb["characters"]]
    loc_ids = [l["id"] for l in sb["locations"]]
    shot_ids = [s["id"] for s in sb["shots"]]
    speakers = set(sb["defaults"]["narration"]["voices"])

    for name, ids in (("subject", char_ids + loc_ids), ("shot", shot_ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            errs.append(f"duplicate {name} ids: {dupes}")

    expected = [f"s{i:02d}" for i in range(1, len(shot_ids) + 1)]
    if shot_ids != expected:
        errs.append(f"shot ids must run s01..s{len(shot_ids):02d} in order, got {shot_ids}")

    for s in sb["shots"]:
        sid = s["id"]
        for c in s["characters"]:
            if c not in char_ids:
                errs.append(f"{sid}: unknown character '{c}'")
        if s["location"] not in loc_ids:
            errs.append(f"{sid}: unknown location '{s['location']}'")
        for i, line in enumerate(s["narration"]["lines"]):
            if line["speaker"] not in speakers:
                errs.append(f"{sid} line {i}: speaker '{line['speaker']}' has no voice in defaults.narration.voices")
        if s["narration"]["offset_s"] >= s["duration_s"]:
            errs.append(f"{sid}: narration offset_s is past the end of the shot")
        if s["transition_in"]["type"] != "cut" and "duration_s" not in s["transition_in"]:
            errs.append(f"{sid}: transition '{s['transition_in']['type']}' needs duration_s")
        if s["transition_in"]["type"] == "fade_from_black" and sid != "s01":
            errs.append(f"{sid}: fade_from_black is only allowed on the first shot")

    total = sum(s["duration_s"] for s in sb["shots"]) + sb["end_card"]["duration_s"]
    lo = sb["project"]["target_duration_s"]["min"]
    hi = sb["project"]["target_duration_s"]["max"]
    if not lo <= total <= hi:
        errs.append(f"planned runtime {total:.1f}s is outside {lo}-{hi}s (shots + end card)")

    order = {sid: i for i, sid in enumerate(shot_ids)}
    covered: list[int] = []
    for cue in sb["music"]["cues"]:
        a, b = order.get(cue["start_shot"]), order.get(cue["end_shot"])
        if a is None or b is None:
            errs.append(f"{cue['id']}: start_shot/end_shot not found")
            continue
        if a > b:
            errs.append(f"{cue['id']}: start_shot comes after end_shot")
        covered.extend(range(a, b + 1))
        chosen = cue.get("chosen_candidate")
        if chosen is not None and chosen >= cue["candidates"]:
            errs.append(f"{cue['id']}: chosen_candidate out of range")
    overlap = sorted({shot_ids[i] for i in covered if covered.count(i) > 1})
    if overlap:
        errs.append(f"music cues overlap on shots {overlap}")

    n_kf = sb["defaults"]["keyframe"]["candidates"]
    n_ref = sb["defaults"]["keyframe"].get("reference_candidates", 4)
    for s in sb["shots"]:
        c = s["keyframe"].get("chosen_candidate")
        if c is not None and c >= n_kf:
            errs.append(f"{s['id']}: keyframe.chosen_candidate out of range (candidates={n_kf})")
    for subj in sb["characters"] + sb["locations"]:
        c = subj.get("approved_candidate")
        if c is not None and c >= n_ref:
            errs.append(f"{subj['id']}: approved_candidate out of range (reference_candidates={n_ref})")
    return errs


def warnings(sb: dict) -> list[str]:
    out = []
    for subj in sb["characters"] + sb["locations"]:
        if subj.get("approved_candidate") is None:
            out.append(f"{subj['id']}: no approved reference yet (candidate 0 is used until you choose)")
    for s in sb["shots"]:
        if s["keyframe"].get("chosen_candidate") is None:
            out.append(f"{s['id']}: no keyframe chosen yet (candidate 0 is used until you choose)")
    for cue in sb["music"]["cues"]:
        if cue.get("chosen_candidate") is None:
            out.append(f"{cue['id']}: no music candidate chosen yet (candidate 0 is used until you choose)")
    return out


def validate(path: Path | None = None) -> dict:
    path = path or ROOT / "storyboard.json"
    sb = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
              for e in sorted(validator.iter_errors(sb), key=lambda e: list(e.absolute_path))]
    if not errors:
        errors = semantic_errors(sb)
    if errors:
        raise SystemExit("storyboard.json is invalid:\n  - " + "\n  - ".join(errors))
    return sb


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "storyboard.json"
    sb = validate(target)
    total = sum(s["duration_s"] for s in sb["shots"]) + sb["end_card"]["duration_s"]
    print(f"OK: {len(sb['shots'])} shots, planned runtime {total:.0f}s")
    for w in warnings(sb):
        print(f"  note: {w}")


if __name__ == "__main__":
    main()
