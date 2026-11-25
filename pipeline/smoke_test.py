"""Smoke test: call each provider once and log the latency to runs.jsonl.

Tells you early which keys work: Gemini text, Gemini TTS (in Amharic), Cloudflare
FLUX.2 klein, and the Kaggle CLI. Nothing here touches the film's outputs.

Usage: python -m pipeline.smoke_test
"""
from __future__ import annotations

import os
import shutil

from .common.config import stage_dir
from .common.providers import cloudflare, gemini, kaggle
from .common.runlog import Timer, log_call

TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
TTS_MODEL = "gemini-3.8-flash-tts"
IMG_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"


def check(name: str, fn) -> bool:
    try:
        with Timer() as t:
            detail = fn()
        print(f"  OK    {name:<28} {t.elapsed:6.2f}s  {detail}")
        return True
    except SystemExit as e:
        print(f"  FAIL  {name:<28} {e}")
    except Exception as e:  # noqa: BLE001 - we want every failure reported, not raised
        print(f"  FAIL  {name:<28} {type(e).__name__}: {str(e)[:200]}")
    return False


def main() -> None:
    out = stage_dir("smoke")
    print("Smoke test (one call per provider):")

    def text():
        with Timer() as t:
            reply, usage = gemini.generate_text("Reply with the single word: ready", TEXT_MODEL)
        log_call(stage="smoke", provider="gemini", model=TEXT_MODEL, params={"purpose": "smoke"}, latency_s=t.elapsed,
                 status="ok", extra={"usage": usage})
        return repr(reply.strip()[:30])

    def tts():
        with Timer() as t:
            audio, usage = gemini.tts("ሰላም፣ እንዴት ናችሁ?", "Kore", "warm and calm", TTS_MODEL)
        (out / "tts_amharic.wav").write_bytes(audio)
        log_call(stage="smoke", provider="gemini", model=TTS_MODEL, params={"purpose": "smoke", "lang": "am"},
                 latency_s=t.elapsed, status="ok", extra={"usage": usage})
        return f"{len(audio) // 1024} KB -> outputs/smoke/tts_amharic.wav (listen to it!)"

    def image():
        with Timer() as t:
            data = cloudflare.generate_image(IMG_MODEL, "a clay coffee pot on a wooden table, warm light", 512, 512, 7)
        (out / "image.png").write_bytes(data)
        log_call(stage="smoke", provider="cloudflare", model=IMG_MODEL, params={"purpose": "smoke", "width": 512, "height": 512},
                 seed=7, latency_s=t.elapsed, status="ok")
        return f"{len(data) // 1024} KB -> outputs/smoke/image.png"

    def kaggle_cli():
        if not kaggle.kaggle_bin():
            raise SystemExit("kaggle CLI not installed (run make setup)")
        if not kaggle.available():
            raise SystemExit("no Kaggle credentials (see README step 2)")
        res = kaggle.cli("kernels", "list", "--mine", "--page-size", "1", check=False)
        if res.returncode != 0:
            raise SystemExit(res.stderr.strip()[:200] or res.stdout.strip()[:200])
        return f"user {kaggle.username()}"

    def ffmpeg_tool():
        if not shutil.which("ffmpeg"):
            raise SystemExit("ffmpeg missing: sudo apt install ffmpeg")
        return shutil.which("ffmpeg")

    results = [check("ffmpeg", ffmpeg_tool), check(f"Gemini text ({TEXT_MODEL})", text),
               check(f"Gemini TTS ({TTS_MODEL})", tts), check("Cloudflare FLUX.2 klein", image),
               check("Kaggle CLI", kaggle_cli)]
    print(f"\n{sum(results)}/{len(results)} checks passed. Failures and latencies are worth a line in FAILURES.md / COSTS.md.")


if __name__ == "__main__":
    main()
