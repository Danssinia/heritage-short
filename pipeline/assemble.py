"""Stage: assemble. The whole edit in code, from the storyboard. No model calls.

1. Timeline: each shot lasts max(planned, narration offset + speech + tail), snapped to 24 fps frames.
2. Picture: one segment per shot and export. Source = Wan clip if generated, else the
   shot's fallback over its keyframe (Ken Burns or still), else a labelled placeholder.
   Clips are trimmed, slowed at most 1.25x, then held with a gentle drift if still short.
   Vertical segments are reframed per shot (center crop or blurred fill).
3. Join: cuts and crossfades as the storyboard says, then the AI end card.
4. Sound: narration placed on the timeline, score cues trimmed and faded, each source
   brought to a similar loudness, score ducked under the voice (sidechaincompress),
   then a two-pass loudnorm to the target LUFS and true peak.
5. Export: subtitles burned in, H.264 + AAC MP4, both aspect ratios.

Every segment and the mix are cached by input hash, so changing one shot re-renders
one segment per export and re-joins; nothing else is redone.

Usage:
  python -m pipeline.assemble            final film, both exports
  python -m pipeline.assemble --radio    radio cut: narration + placeholder music on black, with subtitles
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from . import music as music_stage
from . import shots as shots_stage
from . import subtitles as subs_stage
from .common import story
from .common.cache import Manifest, file_hash, stable_hash
from .common.config import ROOT, stage_dir
from .common.media import (SR, duration, ffmpeg, find_font, loudness_normalize, loudnorm_two_pass,  # noqa: F401
                           measure_loudness, read_wav, require_ffmpeg, to_pcm, write_wav)
from .keyframes import final_path as keyframe_path

FPS = 24
RENDER_VERSION = 3
MAX_SLOWDOWN = 1.25
END_CARD_XFADE = 0.6


# ------------------------------------------------------------------ timeline
def snapped_timeline(sb: dict) -> dict:
    t = story.timeline(sb)
    for s in t["shots"]:
        s["start_f"] = round(s["start"] * FPS)
    for i, s in enumerate(t["shots"]):
        nxt = t["shots"][i + 1]["start_f"] if i + 1 < len(t["shots"]) else round(t["end_card"]["start"] * FPS)
        s["frames"] = nxt - s["start_f"]
    t["end_card"]["start_f"] = round(t["end_card"]["start"] * FPS)
    t["end_card"]["frames"] = round(sb["end_card"]["duration_s"] * FPS)
    t["total_f"] = t["end_card"]["start_f"] + t["end_card"]["frames"]
    return t


def joins(sb: dict) -> list[tuple[str, float]]:
    """Transition into segment j (j >= 1): shots 2..n, then the end card."""
    out = []
    for shot in sb["shots"][1:]:
        tr = shot["transition_in"]
        out.append(("crossfade", tr.get("duration_s", 0.6)) if tr["type"] == "crossfade" else ("cut", 0.0))
    out.append(("crossfade", END_CARD_XFADE))
    return out


# ------------------------------------------------------------------ sources
def shot_source(sb: dict, shot: dict, manifest: Manifest, expected: dict) -> tuple[str, Path | None]:
    sid = shot["id"]
    if shot["motion"]["mode"] == "i2v" and sid in expected and manifest.fresh(f"shots:{sid}", expected[sid]):
        return "clip", shots_stage.clip_path(sid)
    kf = keyframe_path(sid)
    if kf.exists():
        mode = shot["motion"]["mode"] if shot["motion"]["mode"] != "i2v" else shot["motion"]["fallback"]
        return mode, kf
    return "placeholder", None


def master_filter(kind: str, shot: dict, src: Path | None, seconds: float, w: int, h: int) -> tuple[list, str]:
    """Return (ffmpeg inputs, video filter) that produce a w x h, 24 fps stream of `seconds`."""
    n = max(1, round(seconds * FPS))
    if kind == "clip":
        trim = shot["motion"].get("trim_head_s", 0.3)
        usable = max(0.5, duration(src) - trim)
        factor = min(MAX_SLOWDOWN, seconds / usable) if seconds > usable else 1.0
        hold = seconds - usable * factor
        vf = (f"trim=start={trim},setpts=PTS-STARTPTS,setpts={factor:.4f}*PTS,fps={FPS},"
              f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1")
        if hold > 0.04:
            vf += (f",tpad=stop_mode=clone:stop_duration={hold + 0.2:.3f},"
                   f"zoompan=z='min(1+0.0005*on,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={FPS}")
        return ["-i", src], vf
    if kind == "ken_burns":
        kb = shot["motion"].get("ken_burns", {})
        z0, z1 = kb.get("zoom_from", 1.0), kb.get("zoom_to", 1.1)
        pan = kb.get("pan", "none")
        z = f"{z0}+({z1}-{z0})*on/{n}"
        x = {"left": f"(iw-iw/zoom)*(1-on/{n})", "right": f"(iw-iw/zoom)*on/{n}"}.get(pan, "iw/2-(iw/zoom/2)")
        y = {"up": f"(ih-ih/zoom)*(1-on/{n})", "down": f"(ih-ih/zoom)*on/{n}"}.get(pan, "ih/2-(ih/zoom/2)")
        vf = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
              f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={FPS},setsar=1")
        return ["-loop", "1", "-framerate", FPS, "-i", src], vf
    if kind == "still":
        return ["-loop", "1", "-framerate", FPS, "-i", src], f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    font = find_font()
    return (["-f", "lavfi", "-i", f"color=c=0x202020:s={w}x{h}:r={FPS}"],
            f"drawtext=fontfile='{font}':text='{shot['id']} (no picture yet)':fontcolor=white:fontsize={h // 18}:x=(w-tw)/2:y=(h-th)/2")


def reframe_filter(shot: dict, w: int, h: int) -> str:
    """Filter turning a 16:9 master stream into a w x h vertical frame."""
    r = shot["reframe_9x16"]
    if r["mode"] == "center_crop":
        fx = r.get("focus_x", 0.5)
        return f"crop=ih*{w}/{h}:ih:(iw-ih*{w}/{h})*{fx}:0,scale={w}:{h},setsar=1"
    return (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=30:2,"
            f"eq=brightness=-0.08[bg];[b]scale={w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")


def render_segment(sb, shot, kind, src, frames, tail_f, fade_in, export, manifest) -> Path:
    w, h = export["width"], export["height"]
    total_f = frames + tail_f
    seconds = total_f / FPS
    key = f"segment:{export['name']}:{shot['id']}"
    hsh = stable_hash({"v": RENDER_VERSION, "kind": kind, "src": file_hash(src) if src else None, "frames": total_f,
                       "fade": fade_in, "export": export, "motion": shot["motion"], "reframe": shot["reframe_9x16"]})
    out = stage_dir("cuts") / export["name"] / f"{shot['id']}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    if manifest.fresh(key, hsh):
        return out
    if export["aspect"] == "16:9":
        inputs, vf = master_filter(kind, shot, src, seconds, w, h)
        chain = vf
    else:
        inputs, vf = master_filter(kind, shot, src, seconds, 1920, 1080)
        chain = f"{vf},{reframe_filter(shot, w, h)}"
    if fade_in:
        chain += f",fade=t=in:st=0:d={fade_in}"
    ffmpeg(inputs + ["-filter_complex", f"[0:v]{chain}[v]", "-map", "[v]", "-frames:v", total_f, "-r", FPS,
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-an", out])
    manifest.put(key, hsh, [out], {"kind": kind})
    return out


def render_end_card(sb: dict, export: dict, frames: int, manifest: Manifest) -> Path:
    w, h = export["width"], export["height"]
    ec = sb["end_card"]
    key = f"segment:{export['name']}:end_card"
    hsh = stable_hash({"v": RENDER_VERSION, "ec": ec, "export": export, "frames": frames})
    out = stage_dir("cuts") / export["name"] / "end_card.mp4"
    if manifest.fresh(key, hsh):
        return out
    font = find_font()
    txt_file = stage_dir("cuts") / export["name"] / "end_card_sub.txt"
    import textwrap
    txt_file.write_text("\n".join(textwrap.wrap(ec.get("subtext", ""), 34 if h > w else 60)), encoding="utf-8")
    title_file = stage_dir("cuts") / export["name"] / "end_card_title.txt"
    title_file.write_text(ec["text"], encoding="utf-8")
    title_size, sub_size = (h // 14, h // 40) if h <= w else (w // 9, w // 26)
    vf = (f"drawtext=fontfile='{font}':textfile='{title_file}':fontcolor=white:fontsize={title_size}:x=(w-tw)/2:y=h*0.40,"
          f"drawtext=fontfile='{font}':textfile='{txt_file}':fontcolor=0xE8DCC0:fontsize={sub_size}:line_spacing={sub_size // 2}:"
          f"x=(w-tw)/2:y=h*0.40+{title_size * 1.6:.0f},fade=t=out:st={frames / FPS - 0.8:.2f}:d=0.8")
    ffmpeg(["-f", "lavfi", "-i", f"color=c=0x1E1612:s={w}x{h}:r={FPS}", "-vf", vf, "-frames:v", frames,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", out])
    manifest.put(key, hsh, [out])
    return out


def join_segments(segments: list[Path], starts_f: list[int], tr: list[tuple[str, float]], out: Path) -> Path:
    inputs, graph = [], []
    for j, p in enumerate(segments):
        inputs += ["-i", p]
        # same timebase, rate, format and SAR on every input, or xfade/concat refuse to link
        graph.append(f"[{j}:v]setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,setsar=1,settb=AVTB[i{j}]")
    acc = "[i0]"
    for j in range(1, len(segments)):
        kind, d = tr[j - 1]
        label = f"[j{j}]"
        if kind == "crossfade":
            graph.append(f"{acc}[i{j}]xfade=transition=fade:duration={d}:offset={starts_f[j] / FPS:.4f},settb=AVTB{label}")
        else:
            graph.append(f"{acc}[i{j}]concat=n=2:v=1:a=0,settb=AVTB{label}")
        acc = label
    ffmpeg(inputs + ["-filter_complex", ";".join(graph), "-map", acc, "-r", FPS,
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", out])
    return out


# ------------------------------------------------------------------ sound
def fit(a: np.ndarray, n: int) -> np.ndarray:
    """Trim or zero-pad samples to exactly n frames."""
    if len(a) >= n:
        return a[:n]
    return np.concatenate([a, np.zeros((n - len(a), a.shape[1]), dtype=a.dtype)])


def build_mix(sb: dict, t: dict, radio: bool, manifest: Manifest) -> tuple[Path, dict]:
    total = t["total_f"] / FPS
    cache_dir = stage_dir("cuts") / "audio"
    cache_dir.mkdir(parents=True, exist_ok=True)
    nar_dir = stage_dir("narration")
    mix_cfg = sb["mix"]

    # sources
    voice_parts = []
    for s in t["shots"]:
        p = nar_dir / f"{s['id']}.wav"
        if p.exists():
            shot = next(x for x in sb["shots"] if x["id"] == s["id"])
            voice_parts.append((p, s["start_f"] / FPS + shot["narration"]["offset_s"]))
    music_parts = []
    for cue, c in zip(sb["music"]["cues"], t["cues"]):
        take = None if radio else music_stage.chosen_take(sb, cue)
        src = take or music_stage.placeholder_path(cue["id"])
        if src.exists():
            start = next(s for s in t["shots"] if s["id"] == cue["start_shot"])["start_f"] / FPS
            end = total if cue["end_shot"] == sb["shots"][-1]["id"] else next(
                s for s in t["shots"] if s["id"] == cue["end_shot"])["start_f"] / FPS + next(
                s for s in t["shots"] if s["id"] == cue["end_shot"])["frames"] / FPS
            music_parts.append((src, start, end, cue))

    hsh = stable_hash({"v": RENDER_VERSION, "total": t["total_f"], "mix": mix_cfg, "duck": sb["music"]["ducking"],
                       "voice": [(file_hash(p), round(st, 3)) for p, st in voice_parts],
                       "music": [(file_hash(p), round(a, 3), round(b, 3), c.get("fade_in_s"), c.get("fade_out_s")) for p, a, b, c in music_parts]})
    name = "radio" if radio else "film"
    final = cache_dir / f"{name}_mix.wav"
    report_file = cache_dir / f"{name}_mix.json"
    if manifest.fresh(f"mix:{name}", hsh) and report_file.exists():
        return final, json.loads(report_file.read_text())

    n = int(round(total * SR))
    voice = np.zeros((n, 1), dtype=np.float32)
    for p, start in voice_parts:
        a = read_wav(to_pcm(p, cache_dir / f"v_{p.stem}.wav", channels=1))
        i = int(round(start * SR))
        seg = a[: max(0, n - i)]
        voice[i:i + len(seg)] += seg
    # Normalise the whole voice track at once (linear, two-pass): short lines alone are too
    # brief for a reliable loudness reading, and one gain keeps the lines consistent.
    v_raw = write_wav(cache_dir / f"{name}_voice_raw.wav", voice)
    v_norm = cache_dir / f"{name}_voice_norm.wav"
    loudnorm_two_pass(v_raw, v_norm, mix_cfg["voice_lufs"], -2.0, channels=1)
    voice = fit(read_wav(v_norm), n)
    music = np.zeros((n, 2), dtype=np.float32)
    for p, start, end, cue in music_parts:
        norm = loudness_normalize(p, cache_dir / f"m_{cue['id']}.wav", mix_cfg["music_lufs"], channels=2)
        a = read_wav(norm)
        length = int(round((end - start) * SR))
        a = a[:length] if len(a) >= length else np.concatenate([a, np.zeros((length - len(a), 2), np.float32)])
        fi, fo = int(cue.get("fade_in_s", 1.0) * SR), int(cue.get("fade_out_s", 1.5) * SR)
        env = np.ones(length, dtype=np.float32)
        if fi:
            env[:fi] = np.linspace(0, 1, min(fi, length))
        if fo:
            env[-fo:] = np.linspace(1, 0, min(fo, length))
        i = int(round(start * SR))
        seg = (a * env[:, None])[: max(0, n - i)]
        music[i:i + len(seg)] += seg
    vpath = write_wav(cache_dir / f"{name}_voice.wav", np.repeat(voice, 2, axis=1))
    mpath = write_wav(cache_dir / f"{name}_music.wav", music)
    d = sb["music"]["ducking"]
    ducked = cache_dir / f"{name}_music_ducked.wav"
    ffmpeg(["-i", mpath, "-i", vpath, "-filter_complex",
            f"[0:a][1:a]sidechaincompress=threshold={d['threshold']}:ratio={d['ratio']}:attack={d['attack_ms']}:release={d['release_ms']}[d]",
            "-map", "[d]", "-ar", SR, "-c:a", "pcm_s16le", ducked])
    raw = fit(read_wav(vpath), n) + fit(read_wav(ducked), n)
    raw_path = write_wav(cache_dir / f"{name}_mix_raw.wav", raw)
    stats = loudnorm_two_pass(raw_path, final, mix_cfg["integrated_lufs"], mix_cfg["true_peak_db"], channels=2)
    after = measure_loudness(final)
    report = {"input_lufs": stats["input_i"], "output_lufs": after["input_i"], "output_true_peak": after["input_tp"],
              "target_lufs": mix_cfg["integrated_lufs"], "target_tp": mix_cfg["true_peak_db"],
              "music_sources": [str(p.relative_to(ROOT)) for p, *_ in music_parts]}
    report_file.write_text(json.dumps(report, indent=2))
    manifest.put(f"mix:{name}", hsh, [final, report_file])
    return final, report


def mux(video: Path, audio: Path, ass: Path | None, out: Path) -> Path:
    args = ["-i", video, "-i", audio]
    if ass:
        args += ["-vf", f"ass=filename='{ass}'"]
    args += ["-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-shortest", "-movflags", "+faststart", out]
    ffmpeg(args)
    return out


# ------------------------------------------------------------------ entry points
def run_radio() -> Path:
    require_ffmpeg()
    sb = story.load()
    manifest = Manifest()
    music_stage.make_placeholders(sb)
    paths = subs_stage.run()
    t = snapped_timeline(sb)
    audio, report = build_mix(sb, t, radio=True, manifest=manifest)
    final_dir = stage_dir("final")
    black = stage_dir("cuts") / "radio_black.mp4"
    ffmpeg(["-f", "lavfi", "-i", f"color=c=black:s=1280x720:r={FPS}", "-frames:v", t["total_f"],
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", black])
    out = mux(black, audio, paths["radio"], final_dir / "radio_cut.mp4")
    print(f"radio cut: {out.relative_to(ROOT)}  ({duration(out):.1f}s, {report['output_lufs']} LUFS)")
    return out


def run() -> list[Path]:
    require_ffmpeg()
    sb = story.load()
    manifest = Manifest()
    music_stage.make_placeholders(sb)
    paths = subs_stage.run()
    t = snapped_timeline(sb)
    _, _, _, expected, _ = shots_stage.build_jobs(sb, manifest, include_cached=True)
    tr = joins(sb)
    audio, mix_report = build_mix(sb, t, radio=False, manifest=manifest)
    final_dir = stage_dir("final")
    outputs, sources = [], {}
    for export in sb["exports"]:
        segs, starts = [], []
        for i, (shot, ts) in enumerate(zip(sb["shots"], t["shots"])):
            kind, src = shot_source(sb, shot, manifest, expected)
            sources[shot["id"]] = kind
            tail_f = round(tr[i][1] * FPS) if tr[i][0] == "crossfade" else 0
            fade = shot["transition_in"].get("duration_s", 1.0) if shot["transition_in"]["type"] == "fade_from_black" else 0
            segs.append(render_segment(sb, shot, kind, src, ts["frames"], tail_f, fade, export, manifest))
            starts.append(ts["start_f"])
        segs.append(render_end_card(sb, export, t["end_card"]["frames"], manifest))
        starts.append(t["end_card"]["start_f"])
        out = final_dir / f"heritage_{export['name']}_{export['aspect'].replace(':', 'x')}.mp4"
        ass = paths[export["name"]] if sb["subtitles"]["burn_in"] else None
        fh = stable_hash({"v": RENDER_VERSION, "segs": [file_hash(p) for p in segs], "starts": starts, "tr": tr,
                          "audio": file_hash(audio), "ass": file_hash(ass) if ass else None})
        if manifest.fresh(f"final:{export['name']}", fh):
            print(f"  {export['name']}: unchanged, kept {out.relative_to(ROOT)}")
            outputs.append(out)
            continue
        joined = join_segments(segs, starts, tr, stage_dir("cuts") / export["name"] / "joined.mp4")
        out = mux(joined, audio, ass, out)
        manifest.put(f"final:{export['name']}", fh, [out])
        outputs.append(out)
        print(f"  {export['name']}: {out.relative_to(ROOT)} ({duration(out):.2f}s)")
    shutil.copy(paths["srt"], final_dir / "heritage.en.srt")
    report = {
        "total_s": t["total_f"] / FPS, "shots": [{**{k: s[k] for k in ("id", "start", "duration", "planned", "extended")},
                                                  "source": sources[s["id"]]} for s in t["shots"]],
        "mix": mix_report, "outputs": [str(o.relative_to(ROOT)) for o in outputs],
    }
    (final_dir / "assembly_report.json").write_text(json.dumps(report, indent=2))
    fallbacks = [k for k, v in sources.items() if v != "clip"]
    print(f"assemble: {report['total_s']:.1f}s film; loudness {mix_report['output_lufs']} LUFS, "
          f"true peak {mix_report['output_true_peak']} dB; shots without a Wan clip: {', '.join(fallbacks) or 'none'}")
    return outputs


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radio", action="store_true")
    a = ap.parse_args()
    run_radio() if a.radio else run()
