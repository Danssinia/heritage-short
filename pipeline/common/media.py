"""FFmpeg and audio helpers. FFmpeg is deterministic, which is why it owns assembly."""
from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 48000  # internal audio sample rate for every mix


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found. Install it: sudo apt install ffmpeg")


def ffmpeg(args: list[str], quiet: bool = True) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-y"] + (["-loglevel", "error"] if quiet else []) + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{' '.join(cmd)}\n{proc.stderr[-3000:]}")


def ffmpeg_stderr(args: list[str]) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-y"] + [str(a) for a in args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{proc.stderr[-3000:]}")
    return proc.stderr


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def to_pcm(src: Path, dst: Path, channels: int, extra_filter: str | None = None) -> Path:
    """Convert any audio to 48 kHz 16-bit PCM WAV with the given channel count."""
    args = ["-i", src]
    if extra_filter:
        args += ["-af", extra_filter]
    args += ["-ar", SR, "-ac", channels, "-c:a", "pcm_s16le", dst]
    ffmpeg(args)
    return dst


def read_wav(path: Path) -> np.ndarray:
    """Return float32 samples shaped (frames, channels) in [-1, 1]."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: expected 16-bit PCM")
        ch = w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return (data.reshape(-1, ch).astype(np.float32)) / 32768.0


def write_wav(path: Path, samples: np.ndarray, sr: int = SR) -> Path:
    if samples.ndim == 1:
        samples = samples[:, None]
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def silence(seconds: float, channels: int = 1) -> np.ndarray:
    return np.zeros((max(0, int(round(seconds * SR))), channels), dtype=np.float32)


def loudness_normalize(src: Path, dst: Path, lufs: float, tp: float = -1.5, channels: int = 1) -> Path:
    """Single-pass EBU R128 normalisation, used to bring sources to similar levels before mixing."""
    return to_pcm(src, dst, channels, extra_filter=f"loudnorm=I={lufs}:TP={tp}:LRA=11")


def loudnorm_two_pass(src: Path, dst: Path, lufs: float, tp: float, channels: int = 2) -> dict:
    """Two-pass loudnorm for the final mix (more accurate than single pass)."""
    stderr = ffmpeg_stderr(["-i", src, "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"])
    start = stderr.rfind("{")
    stats = json.loads(stderr[start: stderr.rfind("}") + 1])
    flt = (
        f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
        f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}:linear=true"
    )
    to_pcm(src, dst, channels, extra_filter=flt)
    return stats


def measure_loudness(path: Path) -> dict:
    stderr = ffmpeg_stderr(["-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    start = stderr.rfind("{")
    return json.loads(stderr[start: stderr.rfind("}") + 1])


def find_font(name: str = "DejaVu Sans") -> str:
    """Path to a TTF for drawtext; falls back to common Ubuntu locations."""
    if shutil.which("fc-match"):
        out = subprocess.run(["fc-match", "-f", "%{file}", name], capture_output=True, text=True).stdout.strip()
        if out and Path(out).exists():
            return out
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if Path(p).exists():
            return p
    raise SystemExit("No font found for the end card. Install one: sudo apt install fonts-dejavu-core")
