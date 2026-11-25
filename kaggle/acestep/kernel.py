"""Kaggle kernel: ACE-Step 1.5 (diffusers AceStepPipeline) for every take in jobs.json.

Writes <cue>_c<k>.wav and results.json to /kaggle/working. Instrumental only.
"""
import glob
import json
import os
import subprocess
import sys
import time
import traceback

WORK = "/kaggle/working"


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


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
    major = torch.cuda.get_device_capability(0)[0]
    dtype = torch.bfloat16 if major >= 8 else torch.float16
    print(f"GPU {gpu}, dtype {dtype}, {len(jobs['items'])} take(s)", flush=True)

    t_load = time.time()
    pipe = AceStepPipeline.from_pretrained(cfg["model"], torch_dtype=dtype)
    try:
        pipe.enable_model_cpu_offload()
    except Exception:
        pipe = pipe.to("cuda")
    results = {"kind": "music", "gpu": gpu, "dtype": str(dtype).replace("torch.", ""),
               "load_s": round(time.time() - t_load, 1), "items": []}

    def save():
        json.dump(results, open(os.path.join(WORK, "results.json"), "w"), indent=2)

    for job in jobs["items"]:
        item = {"key": job["key"], "hash": job["hash"], "seed": job["seed"], "status": "error", "file": None, "error": None,
                "params": {"duration_s": job["duration_s"], "bpm": job["bpm"], "key": job["key_scale"]}}
        t0 = time.time()
        try:
            gen = torch.Generator(device="cpu").manual_seed(job["seed"])
            audio = pipe(
                prompt=job["caption"], lyrics=job["lyrics"], audio_duration=float(job["duration_s"]),
                bpm=job["bpm"], keyscale=job["key_scale"], timesignature=job["time_signature"],
                num_inference_steps=job["steps"], generator=gen,
            ).audios
            fname = f"{job['key']}.wav"
            sf.write(os.path.join(WORK, fname), audio[0].T.cpu().float().numpy(), pipe.sample_rate)
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
