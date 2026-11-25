"""Storyboard helpers shared by stages: loading, prompt composition and the timeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..validate import validate
from .config import STORYBOARD, stage_dir


def load(path: Path | None = None) -> dict:
    return validate(path or STORYBOARD)


def subjects(sb: dict) -> dict[str, dict]:
    return {s["id"]: s for s in sb["characters"] + sb["locations"]}


def reference_prompt(sb: dict, subj: dict) -> str:
    return f"{subj['reference_prompt']}. Style: {sb['style']['style_block']}"


def keyframe_prompt(sb: dict, shot: dict) -> str:
    """Shot prompt + fixed character/location wording + style block, the same way every time."""
    subs = subjects(sb)
    parts = [shot["keyframe"]["prompt"].rstrip(".") + "."]
    chars = [subs[c] for c in shot["characters"]]
    if chars:
        names = {"dad": "The father", "mom": "The mother", "me": "The young person"}
        desc = "; ".join(f"{names.get(c['id'], c['name'])} is {c['description']}" for c in chars)
        parts.append(f"Characters: {desc}.")
    parts.append(f"Setting: {subs[shot['location']]['description']}.")
    parts.append(f"Style: {sb['style']['style_block']}.")
    return " ".join(parts)


def chosen(index: int | None) -> int:
    return 0 if index is None else index


def num_frames(clip_s: float, fps: int = 24) -> int:
    """Wan needs 4k+1 frames."""
    n = round(clip_s * fps)
    return max(5, ((n - 1) // 4) * 4 + 1)


def narration_timings() -> dict[str, Any]:
    p = stage_dir("narration") / "timings.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def timeline(sb: dict, timings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the edit: each shot lasts max(planned, narration offset + speech + tail).

    Returns absolute start/end for shots, lines (for subtitles), music cues and the end card.
    Without narration timings (before TTS runs) the planned durations are used.
    """
    timings = timings if timings is not None else narration_timings()
    t = 0.0
    shots = []
    for s in sb["shots"]:
        nar = s["narration"]
        info = timings.get(s["id"], {})
        speech = info.get("total", 0.0)
        need = nar["offset_s"] + speech + (nar.get("tail_s", 0.6) if speech else 0.0)
        dur = round(max(s["duration_s"], need), 3)
        lines = []
        for i, line in enumerate(nar["lines"]):
            li = (info.get("lines") or [])[i] if i < len(info.get("lines") or []) else None
            if li:
                lines.append({
                    "speaker": line["speaker"], "subtitle_en": line["subtitle_en"],
                    "start": round(t + nar["offset_s"] + li["start"], 3),
                    "end": round(t + nar["offset_s"] + li["end"], 3),
                })
        shots.append({
            "id": s["id"], "start": round(t, 3), "end": round(t + dur, 3), "duration": dur,
            "planned": s["duration_s"], "extended": dur > s["duration_s"], "lines": lines,
            "narration_start": round(t + nar["offset_s"], 3),
        })
        t += dur
    end_card = {"start": round(t, 3), "end": round(t + sb["end_card"]["duration_s"], 3)}
    by_id = {s["id"]: s for s in shots}
    cues = []
    for cue in sb["music"]["cues"]:
        start = by_id[cue["start_shot"]]["start"]
        end = by_id[cue["end_shot"]]["end"]
        if cue["end_shot"] == sb["shots"][-1]["id"]:
            end = end_card["end"]  # let the last cue play under the end card
        cues.append({"id": cue["id"], "start": start, "end": end, "duration": round(end - start, 3)})
    return {"shots": shots, "end_card": end_card, "cues": cues, "total": end_card["end"]}
