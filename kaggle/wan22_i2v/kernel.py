"""Kaggle kernel: Wan 2.2 TI2V-5B image-to-video for every job in jobs.json.

Runs on a Kaggle T4 (16 GB). Reads jobs.json and keyframes from the attached dataset,
writes <shot>.mp4 and results.json to /kaggle/working (downloaded by the pipeline).
results.json is rewritten after every job, so a timeout still leaves finished shots.

Memory plan for a T4: transformer in float16 (T4 has no native bfloat16), VAE in
float32, model CPU offload so only the active component sits on the GPU, VAE tiling.
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


def find_jobs() -> str:
    hits = glob.glob("/kaggle/input/**/jobs.json", recursive=True)
    if not hits:
        sys.exit("jobs.json not found under /kaggle/input: is the heritage-shots-jobs dataset attached?")
    return os.path.dirname(hits[0])


def main() -> None:
    sh("pip install -q -U diffusers transformers accelerate ftfy imageio imageio-ffmpeg")
    import numpy as np
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    job_dir = find_jobs()
    jobs = json.load(open(os.path.join(job_dir, "jobs.json")))
    cfg = jobs["config"]
    gpu = torch.cuda.get_device_name(0)
    major = torch.cuda.get_device_capability(0)[0]
    want = cfg.get("dtype", "auto")
    dtype = torch.bfloat16 if want == "bfloat16" or (want == "auto" and major >= 8) else torch.float16
    print(f"GPU {gpu} (sm{major}x), dtype {dtype}, {len(jobs['items'])} job(s)", flush=True)

    t_load = time.time()
    vae = AutoencoderKLWan.from_pretrained(cfg["model"], subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(cfg["model"], vae=vae, torch_dtype=dtype)
    pipe.enable_model_cpu_offload()
    try:
        pipe.vae.enable_tiling()
    except Exception as e:  # older diffusers
        print("VAE tiling unavailable:", e)
    load_s = time.time() - t_load
    print(f"model loaded in {load_s:.0f}s", flush=True)

    results = {"kind": "shots", "gpu": gpu, "dtype": str(dtype).replace("torch.", ""), "load_s": round(load_s, 1), "items": []}

    def save():
        json.dump(results, open(os.path.join(WORK, "results.json"), "w"), indent=2)

    for job in jobs["items"]:
        key = job["key"]
        item = {"key": key, "hash": job["hash"], "seed": job["seed"], "status": "error", "file": None, "error": None,
                "params": {"num_frames": job["num_frames"], "steps": job["steps"], "width": job["width"], "height": job["height"]}}
        t0 = time.time()
        try:
            image = load_image(os.path.join(job_dir, job["image"])).convert("RGB").resize((job["width"], job["height"]))
            gen = torch.Generator(device="cpu").manual_seed(job["seed"])
            frames = pipe(
                image=image, prompt=job["prompt"], negative_prompt=job["negative_prompt"],
                height=job["height"], width=job["width"], num_frames=job["num_frames"],
                guidance_scale=job["guidance"], num_inference_steps=job["steps"], generator=gen,
            ).frames[0]
            first = np.asarray(frames[0], dtype=np.float32)
            scale = 1.0 if first.max() <= 1.0 else 255.0
            if np.isnan(first).any() or first.mean() / scale < 0.02:
                raise RuntimeError("black or NaN frames (float16 overflow?) - try dtype bfloat16 in storyboard defaults.shot")
            fname = f"{key}.mp4"
            export_to_video(frames, os.path.join(WORK, fname), fps=24)
            item.update(status="ok", file=fname)
        except Exception as e:
            item["error"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        item["latency_s"] = round(time.time() - t0, 1)
        results["items"].append(item)
        save()
        print(f"{key}: {item['status']} in {item['latency_s']}s {item['error'] or ''}", flush=True)
        torch.cuda.empty_cache()
    save()


if __name__ == "__main__":
    main()
