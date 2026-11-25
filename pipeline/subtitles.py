"""Stage: subtitles. English subtitles timed to the measured narration.

Writes outputs/subtitles/film.en.srt (to upload to platforms) and one .ass file per
export, with the font size and bottom margin set for that frame so the text stays
inside the safe area of the vertical video. Lines are wrapped at max_chars_per_line
and long subtitles are split into consecutive cues of at most max_lines lines.

Usage: python -m pipeline.subtitles
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

from .common import story
from .common.config import stage_dir


def split_cue(text: str, start: float, end: float, max_chars: int, max_lines: int) -> list[tuple[float, float, list[str]]]:
    lines = textwrap.wrap(text, max_chars)
    chunks = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)] or [[""]]
    total = sum(len(" ".join(c)) for c in chunks) or 1
    out, t = [], start
    for c in chunks:
        share = (end - start) * len(" ".join(c)) / total
        out.append((t, t + share, c))
        t += share
    return out


def cues(sb: dict, t: dict) -> list[tuple[float, float, list[str]]]:
    cfg = sb["subtitles"]
    result = []
    for shot in t["shots"]:
        for line in shot["lines"]:
            result += split_cue(line["subtitle_en"], line["start"], line["end"] + 0.25,
                                cfg["max_chars_per_line"], cfg["max_lines"])
    # never overlap the next cue
    fixed = []
    for i, (a, b, txt) in enumerate(result):
        if i + 1 < len(result):
            b = min(b, result[i + 1][0] - 0.04)
        fixed.append((a, max(a + 0.5, b), txt))
    return fixed


def _srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _ass_time(s: float) -> str:
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def write_srt(items, path: Path) -> Path:
    blocks = [f"{i}\n{_srt_time(a)} --> {_srt_time(b)}\n" + "\n".join(txt) for i, (a, b, txt) in enumerate(items, 1)]
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def write_ass(items, path: Path, width: int, height: int, font: str, margin_pct: float) -> Path:
    vertical = height > width
    size = 42 if vertical else 50
    margin_v = int(height * margin_pct / 100) if vertical else int(height * 0.07)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for a, b, txt in items:
        safe = [re.sub(r"[{}]", "", l) for l in txt]
        events.append(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},Default,,0,0,0,," + r"\N".join(safe))
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return path


def run() -> dict[str, Path]:
    sb = story.load()
    t = story.timeline(sb)
    items = cues(sb, t)
    out = stage_dir("subtitles")
    paths = {"srt": write_srt(items, out / "film.en.srt")}
    font = sb["subtitles"].get("font", "DejaVu Sans")
    for ex in sb["exports"]:
        paths[ex["name"]] = write_ass(items, out / f"{ex['name']}.ass", ex["width"], ex["height"], font,
                                      sb["subtitles"].get("vertical_margin_pct", 20))
    paths["radio"] = write_ass(items, out / "radio.ass", 1280, 720, font, 20)
    print(f"subtitles: {len(items)} cue(s)")
    return paths


if __name__ == "__main__":
    run()
