"""Stage: script helpers with Gemini text.

  python -m pipeline.script --backtranslate
      Translates every Amharic narration line back to English, independently of
      subtitle_en, and writes outputs/script/backtranslation.md side by side.
      Use it to catch lines whose meaning drifted, and as an EXPERIMENTS.md entry.

  python -m pipeline.script --draft story.txt
      Drafts a storyboard from a plain-language story into outputs/script/storyboard_draft.json
      (validated against the schema). You review it and copy what you want into storyboard.json.
      The pipeline never overwrites storyboard.json itself: the contract stays human-approved.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .common import story
from .common.config import ROOT, STORYBOARD, stage_dir
from .common.prices import text_cost
from .common.providers import gemini
from .common.retry import with_retries
from .common.runlog import Timer, log_call

MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")


def ask(prompt: str, json_mode: bool, purpose: str) -> str:
    def call(attempt: int):
        with Timer() as t:
            text, usage = gemini.generate_text(prompt, MODEL, json_mode=json_mode)
        log_call(stage="script", provider="gemini", model=MODEL, params={"purpose": purpose, "prompt_chars": len(prompt)},
                 latency_s=t.elapsed, status="ok", cost_usd=text_cost(usage), attempt=attempt, extra={"usage": usage})
        return text
    return with_retries(call, attempts=3)


def backtranslate() -> Path:
    sb = story.load()
    lines = [(s["id"], i, l) for s in sb["shots"] for i, l in enumerate(s["narration"]["lines"])]
    payload = [{"id": f"{sid}.{i}", "amharic": l["text"]} for sid, i, l in lines]
    prompt = ("Translate each Amharic line into natural English. Do not add or remove meaning. "
              "Return a JSON list of objects with keys id and english.\n" + json.dumps(payload, ensure_ascii=False))
    data = json.loads(ask(prompt, True, "backtranslate") or "[]")
    got = {d.get("id"): d.get("english", "") for d in data if isinstance(d, dict)}
    rows = ["| Line | Amharic | Back-translation (Gemini) | Our subtitle |", "|---|---|---|---|"]
    for sid, i, l in lines:
        rows.append(f"| {sid}.{i} | {l['text']} | {got.get(f'{sid}.{i}', '(missing)')} | {l['subtitle_en']} |")
    out = stage_dir("script") / "backtranslation.md"
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return out


def draft(story_file: Path) -> Path:
    schema = (ROOT / "schema" / "storyboard.schema.json").read_text()
    example = STORYBOARD.read_text(encoding="utf-8")
    prompt = (
        "You are a film storyboard writer. Turn the story below into a storyboard JSON for a 60-90 second "
        "short film narrated in Amharic with English subtitles. It must validate against the JSON Schema and "
        "follow the example's conventions (8-12 shots, one idea and one gentle movement per shot, a stated "
        "reason for every shot, short spoken lines). Return only JSON.\n\nSCHEMA:\n" + schema +
        "\n\nEXAMPLE:\n" + example + "\n\nSTORY:\n" + story_file.read_text(encoding="utf-8"))
    text = ask(prompt, True, "draft_storyboard")
    out = stage_dir("script") / "storyboard_draft.json"
    out.write_text(text, encoding="utf-8")
    try:
        from .validate import validate
        validate(out)
        print(f"wrote {out.relative_to(ROOT)} (valid)")
    except SystemExit as e:
        print(f"wrote {out.relative_to(ROOT)} but it does not validate yet:\n{e}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backtranslate", action="store_true")
    ap.add_argument("--draft", type=Path)
    a = ap.parse_args()
    if a.draft:
        draft(a.draft)
    else:
        backtranslate()
