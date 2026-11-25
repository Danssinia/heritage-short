"""Stage: narration. One Gemini TTS call per line, cached by (model, voice, style, text).

Writes outputs/narration/<shot>_l<i>.wav per line, <shot>.wav per shot (lines joined
with their pauses, leading/trailing silence trimmed) and timings.json, which the
timeline uses to size each shot to its speech.

Usage: python -m pipeline.narration [--force]
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from .common import story
from .common.cache import Manifest, file_hash, stable_hash
from .common.config import ROOT, stage_dir
from .common.media import SR, read_wav, silence, to_pcm, write_wav
from .common.prices import tts_cost
from .common.providers import gemini
from .common.retry import with_retries
from .common.runlog import Timer, log_call

TRIM = (
    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse"
)


def synth_line(sb: dict, shot: dict, i: int, line: dict, manifest: Manifest, force: bool) -> tuple:
    d = sb["defaults"]["narration"]
    voice = d["voices"][line["speaker"]]
    style = line.get("style") or d["style_instruction"]
    key = f"narration:{shot['id']}:l{i}"
    h = stable_hash({"model": d["model"], "voice": voice, "style": style, "text": line["text"], "trim": TRIM})
    out = stage_dir("narration") / f"{shot['id']}_l{i}.wav"
    if not force and manifest.fresh(key, h):
        return out, False
    raw = stage_dir("narration") / "raw" / f"{shot['id']}_l{i}.wav"
    raw.parent.mkdir(exist_ok=True)

    def call(attempt: int):
        with Timer() as t:
            try:
                audio, usage = gemini.tts(line["text"], voice, style, d["model"])
            except Exception as e:
                log_call(stage="narration", provider="gemini", model=d["model"], params={"voice": voice, "style": style, "chars": len(line["text"])},
                         latency_s=0.0, status="error", error=str(e), cache_key=h, attempt=attempt)
                raise
        raw.write_bytes(audio)
        log_call(stage="narration", provider="gemini", model=d["model"],
                 params={"voice": voice, "style": style, "chars": len(line["text"]), "shot": shot["id"], "line": i},
                 latency_s=t.elapsed, status="ok", cost_usd=tts_cost(usage), cost_note="list price, free tier used",
                 cache_key=h, output=str(raw.relative_to(ROOT)), attempt=attempt, extra={"usage": usage})

    with_retries(call, attempts=4)
    to_pcm(raw, out, channels=1, extra_filter=TRIM)
    manifest.put(key, h, [out], {"voice": voice, "speaker": line["speaker"]})
    return out, True


def build_shot(shot: dict, line_files: list, manifest: Manifest) -> dict:
    """Join a shot's lines with their pauses into <shot>.wav and return its timings."""
    lines = shot["narration"]["lines"]
    key = f"narration:{shot['id']}"
    h = stable_hash({"lines": [file_hash(p) for p in line_files], "pauses": [l.get("pause_after_s", 0.35) for l in lines]})
    out = stage_dir("narration") / f"{shot['id']}.wav"
    t = 0.0
    chunks, info = [], []
    for line, path in zip(lines, line_files):
        audio = read_wav(path)
        dur = len(audio) / SR
        info.append({"start": round(t, 3), "end": round(t + dur, 3)})
        chunks.append(audio)
        t += dur
        pause = line.get("pause_after_s", 0.35)
        if line is not lines[-1]:
            chunks.append(silence(pause))
            t += pause
    if not manifest.fresh(key, h):
        write_wav(out, np.concatenate(chunks) if chunks else silence(0.1))
        manifest.put(key, h, [out])
    return {"total": round(t, 3), "lines": info, "path": str(out.relative_to(ROOT))}


def run(force: bool = False) -> dict:
    sb = story.load()
    manifest = Manifest()
    timings, made = {}, 0
    for shot in sb["shots"]:
        files = []
        for i, line in enumerate(shot["narration"]["lines"]):
            path, new = synth_line(sb, shot, i, line, manifest, force)
            made += new
            files.append(path)
        if files:
            timings[shot["id"]] = build_shot(shot, files, manifest)
    (stage_dir("narration") / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    total_speech = sum(v["total"] for v in timings.values())
    print(f"narration: {made} new TTS call(s), {sum(len(s['narration']['lines']) for s in sb['shots']) - made} cached; "
          f"total speech {total_speech:.1f}s")
    return timings


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="ignore the cache and regenerate every line")
    run(ap.parse_args().force)
