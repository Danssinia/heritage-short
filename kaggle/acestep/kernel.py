"""Kaggle kernel: ACE-Step 1.5 (diffusers AceStepPipeline) for every take in jobs.json.

Writes <cue>_c<k>.wav and results.json to /kaggle/working. Instrumental only.

T4 GPUs have no native bfloat16, and float16 can overflow inside ACE-Step and produce
invalid samples (NaN/inf, written as a flat full-scale signal). So the kernel first runs a
short probe in each precision (float32, then bfloat16, then float16), keeps the first that
gives real audio, and checks every take before saving it.
"""
import gc
import glob
import json
import os
import subprocess
import sys
import time
import traceback

WORK = "/kaggle/working"
ORDER = ["float32", "bfloat16", "float16"]


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def audio_problem(audio) -> str | None:
    """Return why a waveform is unusable, or None if it looks like real audio."""
    import numpy as np
    import torch
    a = audio if isinstance(audio, torch.Tensor) else torch.as_tensor(np.asarray(audio))
    a = a.detach().float()
    if not torch.isfinite(a).all():
        return "non-finite samples (NaN/inf)"
    peak = a.abs().max().item()
    if peak < 1e-3:
        return f"silent (peak {peak:.2e})"
    if a.std().item() < 1e-3:
        return "flat signal"
    if a.abs().mean().item() > 0.8:
        return "stuck at full scale"
    return None


def main() -> None:
    sh("pip install -q -U diffusers transformers accelerate soundfile")
    try:
        from diffusers import AceStepPipeline
    except ImportError:
        sh("pip install -q -U git+https://github.com/huggingface/diffusers")
        from diffusers import AceStepPipeline
    import soundfile as sf
    import torch

    hits = glob.glob("/kaggle/input/**/jobs.json", recursive=True)
    if not hits:
        sys.exit("jobs.json not found under /kaggle/input: is the heritage-music-jobs dataset attached?")
    jobs = json.load(open(hits[0]))
    cfg = jobs["config"]
    gpu = torch.cuda.get_device_name(0)
    print(f"GPU {gpu}, {len(jobs['items'])} take(s)", flush=True)
    dtypes = {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}

    def load(name):
        p = AceStepPipeline.from_pretrained(cfg["model"], torch_dtype=dtypes[name])
        try:
            p.enable_model_cpu_offload()
        except Exception:
            p = p.to("cuda")
        return p

    def generate(p, job, seconds=None, steps=None):
        gen = torch.Generator(device="cpu").manual_seed(job["seed"])
        return p(prompt=job["caption"], lyrics=job["lyrics"],
                 audio_duration=float(seconds or job["duration_s"]), bpm=job["bpm"],
                 keyscale=job["key_scale"], timesignature=job["time_signature"],
                 num_inference_steps=steps or job["steps"], generator=gen).audios[0]

    # --- probe: find a precision that produces real audio on this GPU
    t_load = time.time()
    pipe, chosen, probe_log = None, None, []
    for name in ORDER:
        try:
            print(f"probing {name} ...", flush=True)
            pipe = load(name)
            problem = audio_problem(generate(pipe, jobs["items"][0], seconds=10, steps=4))
            probe_log.append({"dtype": name, "result": problem or "ok"})
            if problem is None:
                chosen = name
                break
            print(f"  {name}: {problem}", flush=True)
        except Exception as e:  # out of memory or unsupported op
            probe_log.append({"dtype": name, "result": f"{type(e).__name__}: {str(e)[:200]}"})
            print(f"  {name} failed: {type(e).__name__}: {e}", flush=True)
        pipe = None
        gc.collect()
        torch.cuda.empty_cache()
    results = {"kind": "music", "gpu": gpu, "dtype": chosen, "probe": probe_log,
               "load_s": round(time.time() - t_load, 1), "items": []}

    def save():
        json.dump(results, open(os.path.join(WORK, "results.json"), "w"), indent=2)

    if chosen is None:
        for job in jobs["items"]:
            results["items"].append({"key": job["key"], "hash": job["hash"], "seed": job["seed"], "status": "error",
                                     "file": None, "latency_s": 0, "error": f"no working precision: {probe_log}"})
        save()
        sys.exit("No precision produced valid audio on this GPU; see results.json probe")
    print(f"using {chosen}", flush=True)

    for job in jobs["items"]:
        item = {"key": job["key"], "hash": job["hash"], "seed": job["seed"], "status": "error", "file": None, "error": None,
                "params": {"duration_s": job["duration_s"], "bpm": job["bpm"], "key": job["key_scale"], "dtype": chosen}}
        t0 = time.time()
        try:
            audio = generate(pipe, job)
            problem = audio_problem(audio)
            if problem:
                raise RuntimeError(f"invalid audio: {problem}")
            fname = f"{job['key']}.wav"
            arr = audio.detach().cpu().float().numpy() if hasattr(audio, "detach") else __import__("numpy").asarray(audio, dtype="float32")
            if arr.ndim == 2 and arr.shape[0] <= 2:  # (channels, samples) -> (samples, channels)
                arr = arr.T
            sf.write(os.path.join(WORK, fname), arr, pipe.sample_rate, subtype="PCM_16")
            item.update(status="ok", file=fname)
        except Exception as e:
            item["error"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        item["latency_s"] = round(time.time() - t0, 1)
        results["items"].append(item)
        save()
        print(f"{job['key']}: {item['status']} in {item['latency_s']}s {item['error'] or ''}", flush=True)
    save()


if __name__ == "__main__":
    main()
