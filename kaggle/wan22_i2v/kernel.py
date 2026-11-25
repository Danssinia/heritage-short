"""Kaggle kernel: Wan 2.2 TI2V-5B image-to-video for every job in jobs.json.

Runs on a Kaggle T4 (16 GB). Reads jobs.json and keyframes from the attached dataset,
writes <shot>.mp4 and results.json to /kaggle/working (downloaded by the pipeline).
results.json is rewritten after every job, so a timeout still leaves finished shots.

Precision: a T4 has no native bfloat16, and float16 can overflow (NaN or black frames).
The kernel probes with a tiny clip first (float16, then bfloat16), checks every shot,
and if a float16 shot comes out invalid it reloads in bfloat16 and retries that shot once.
Memory: VAE in float32, model CPU offload, VAE tiling.
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


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def find_jobs() -> str:
    hits = glob.glob("/kaggle/input/**/jobs.json", recursive=True)
    if not hits:
        sys.exit("jobs.json not found under /kaggle/input: is the heritage-shots-jobs dataset attached?")
    return os.path.dirname(hits[0])


def frames_problem(frames) -> str | None:
    import numpy as np
    arr = np.asarray([np.asarray(f, dtype=np.float32) for f in (frames[0], frames[len(frames) // 2], frames[-1])])
    if not np.isfinite(arr).all():
        return "non-finite pixels (NaN/inf)"
    scale = 1.0 if arr.max() <= 1.0 else 255.0
    if arr.mean() / scale < 0.02:
        return "black frames"
    if arr.std() / scale < 0.01:
        return "flat frames"
    return None


def main() -> None:
    sh("pip install -q -U diffusers transformers accelerate ftfy imageio imageio-ffmpeg")
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    job_dir = find_jobs()
    jobs = json.load(open(os.path.join(job_dir, "jobs.json")))
    cfg = jobs["config"]
    gpu = torch.cuda.get_device_name(0)
    major = torch.cuda.get_device_capability(0)[0]
    want = cfg.get("dtype", "auto")
    if want == "auto":
        order = ["bfloat16"] if major >= 8 else ["float16", "bfloat16"]
    else:
        order = [want]
    dtypes = {"float16": torch.float16, "bfloat16": torch.bfloat16}
    print(f"GPU {gpu} (sm{major}x), precision order {order}, {len(jobs['items'])} job(s)", flush=True)

    def load(name):
        vae = AutoencoderKLWan.from_pretrained(cfg["model"], subfolder="vae", torch_dtype=torch.float32)
        p = WanImageToVideoPipeline.from_pretrained(cfg["model"], vae=vae, torch_dtype=dtypes[name])
        p.enable_model_cpu_offload()
        try:
            p.vae.enable_tiling()
        except Exception as e:
            print("VAE tiling unavailable:", e)
        return p

    def run(p, job, image, width=None, height=None, frames=None, steps=None):
        gen = torch.Generator(device="cpu").manual_seed(job["seed"])
        w, h = width or job["width"], height or job["height"]
        return p(image=image.resize((w, h)), prompt=job["prompt"], negative_prompt=job["negative_prompt"],
                 height=h, width=w, num_frames=frames or job["num_frames"], guidance_scale=job["guidance"],
                 num_inference_steps=steps or job["steps"], generator=gen).frames[0]

    first = jobs["items"][0]
    first_img = load_image(os.path.join(job_dir, first["image"])).convert("RGB")

    t_load = time.time()
    pipe, chosen, probe_log = None, None, []
    for name in order:
        try:
            print(f"probing {name} with a tiny clip ...", flush=True)
            pipe = load(name)
            problem = frames_problem(run(pipe, first, first_img, width=320, height=192, frames=9, steps=4))
            probe_log.append({"dtype": name, "result": problem or "ok"})
            if problem is None:
                chosen = name
                break
            print(f"  {name}: {problem}", flush=True)
        except Exception as e:
            probe_log.append({"dtype": name, "result": f"{type(e).__name__}: {str(e)[:200]}"})
            print(f"  {name} failed: {type(e).__name__}: {e}", flush=True)
        pipe = None
        gc.collect()
        torch.cuda.empty_cache()

    results = {"kind": "shots", "gpu": gpu, "dtype": chosen, "probe": probe_log,
               "load_s": round(time.time() - t_load, 1), "items": []}

    def save():
        json.dump(results, open(os.path.join(WORK, "results.json"), "w"), indent=2)

    if chosen is None:
        for job in jobs["items"]:
            results["items"].append({"key": job["key"], "hash": job["hash"], "seed": job["seed"], "status": "error",
                                     "file": None, "latency_s": 0, "error": f"no working precision: {probe_log}"})
        save()
        sys.exit("No precision produced valid video on this GPU; see results.json probe")
    print(f"using {chosen}", flush=True)

    for job in jobs["items"]:
        key = job["key"]
        item = {"key": key, "hash": job["hash"], "seed": job["seed"], "status": "error", "file": None, "error": None,
                "params": {"num_frames": job["num_frames"], "steps": job["steps"], "width": job["width"],
                           "height": job["height"], "dtype": chosen}}
        t0 = time.time()
        try:
            image = load_image(os.path.join(job_dir, job["image"])).convert("RGB")
            frames = run(pipe, job, image)
            problem = frames_problem(frames)
            if problem and chosen == "float16" and "bfloat16" in order:
                print(f"{key}: {problem} in float16; reloading in bfloat16 and retrying", flush=True)
                pipe = None
                gc.collect()
                torch.cuda.empty_cache()
                chosen = "bfloat16"
                results["dtype"] = chosen
                pipe = load(chosen)
                item["params"]["dtype"] = chosen
                frames = run(pipe, job, image)
                problem = frames_problem(frames)
            if problem:
                raise RuntimeError(f"invalid video: {problem}")
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
