"""Kaggle kernel: Wan 2.2 TI2V-5B image-to-video for every job in jobs.json.

Runs on a Kaggle T4 (16 GB). Reads jobs.json and keyframes from the attached dataset,
writes <shot>.mp4 and results.json to /kaggle/working (downloaded by the pipeline).
results.json is rewritten after every job, so a timeout still leaves finished shots.

Memory plan for a T4 (learned from an out-of-memory run, see FAILURES.md):
1. Phase A: load ONLY the UMT5 text encoder (about 11 GB), encode every prompt and
   negative prompt, keep the embeddings on the CPU, then free the GPU completely.
   (Uses the second T4 if Kaggle gave us two.)
2. Phase B: load the transformer + VAE without the text encoder, with model CPU offload
   and VAE tiling, and pass the saved embeddings.
3. Precision: a T4 has no native bfloat16, and float16 can overflow, so a tiny probe clip
   picks float16 or bfloat16; every shot is checked for NaN/black frames.
4. After any failure the GPU is cleaned (offload hooks reset, cache emptied), so one bad
   shot cannot make the following shots fail.
"""
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import gc  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

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

    def free(*objs):
        for o in objs:
            try:
                o.maybe_free_model_hooks()
            except Exception:
                pass
        gc.collect()
        for i in range(torch.cuda.device_count()):
            with torch.cuda.device(i):
                torch.cuda.empty_cache()

    job_dir = find_jobs()
    jobs = json.load(open(os.path.join(job_dir, "jobs.json")))
    cfg = jobs["config"]
    n_gpu = torch.cuda.device_count()
    gpu = torch.cuda.get_device_name(0)
    major = torch.cuda.get_device_capability(0)[0]
    want = cfg.get("dtype", "auto")
    order = (["bfloat16"] if major >= 8 else ["float16", "bfloat16"]) if want == "auto" else [want]
    dtypes = {"float16": torch.float16, "bfloat16": torch.bfloat16}
    print(f"{n_gpu} x {gpu} (sm{major}x), precision order {order}, {len(jobs['items'])} job(s)", flush=True)

    # ---------------- Phase A: text embeddings with the text encoder alone
    t0 = time.time()
    text_dev = "cuda:1" if n_gpu > 1 else "cuda:0"
    tp = WanImageToVideoPipeline.from_pretrained(cfg["model"], transformer=None, vae=None, torch_dtype=torch.bfloat16)
    tp.text_encoder.to(text_dev)
    embeds = {}
    with torch.no_grad():
        for job in jobs["items"]:
            kwargs = dict(prompt=job["prompt"], negative_prompt=job["negative_prompt"],
                          do_classifier_free_guidance=True, device=torch.device(text_dev))
            try:
                pe, ne = tp.encode_prompt(max_sequence_length=512, **kwargs)
            except TypeError:
                pe, ne = tp.encode_prompt(**kwargs)
            if not (torch.isfinite(pe).all() and torch.isfinite(ne).all()):
                sys.exit(f"text embeddings for {job['key']} are not finite")
            embeds[job["key"]] = (pe.float().cpu(), ne.float().cpu())
    tp.text_encoder.to("cpu")
    del tp
    free()
    print(f"phase A: encoded {len(embeds)} prompts on {text_dev} in {time.time() - t0:.0f}s", flush=True)

    # ---------------- Phase B: video model without the text encoder
    def load(name):
        vae = AutoencoderKLWan.from_pretrained(cfg["model"], subfolder="vae", torch_dtype=torch.float32)
        p = WanImageToVideoPipeline.from_pretrained(cfg["model"], vae=vae, text_encoder=None, tokenizer=None,
                                                    torch_dtype=dtypes[name])
        p.enable_model_cpu_offload()
        try:
            p.vae.enable_tiling()
        except Exception as e:
            print("VAE tiling unavailable:", e)
        return p

    def run(p, name, job, image, width=None, height=None, frames=None, steps=None):
        gen = torch.Generator(device="cpu").manual_seed(job["seed"])
        w, h = width or job["width"], height or job["height"]
        pe, ne = embeds[job["key"]]
        with torch.no_grad():
            dev = torch.device("cuda:0")  # execution device under model CPU offload
            return p(image=image.resize((w, h)), prompt_embeds=pe.to(dev, dtypes[name]),
                     negative_prompt_embeds=ne.to(dev, dtypes[name]),
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
            problem = frames_problem(run(pipe, name, first, first_img, width=320, height=192, frames=9, steps=4))
            probe_log.append({"dtype": name, "result": problem or "ok"})
            if problem is None:
                chosen = name
                break
            print(f"  {name}: {problem}", flush=True)
        except Exception as e:
            probe_log.append({"dtype": name, "result": f"{type(e).__name__}: {str(e)[:200]}"})
            print(f"  {name} failed: {type(e).__name__}: {e}", flush=True)
        free(pipe)
        pipe = None
        free()

    results = {"kind": "shots", "gpu": f"{n_gpu}x {gpu}", "dtype": chosen, "probe": probe_log,
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
            frames = run(pipe, chosen, job, image)
            problem = frames_problem(frames)
            if problem and chosen == "float16" and "bfloat16" in order:
                print(f"{key}: {problem} in float16; reloading in bfloat16 and retrying", flush=True)
                free(pipe)
                pipe = None
                free()
                chosen = "bfloat16"
                results["dtype"] = chosen
                pipe = load(chosen)
                item["params"]["dtype"] = chosen
                frames = run(pipe, chosen, job, image)
                problem = frames_problem(frames)
            if problem:
                raise RuntimeError(f"invalid video: {problem}")
            fname = f"{key}.mp4"
            export_to_video(frames, os.path.join(WORK, fname), fps=24)
            item.update(status="ok", file=fname)
        except Exception as e:
            item["error"] = f"{type(e).__name__}: {str(e)[:500]}"
            traceback.print_exc()
        frames = None
        free(pipe)
        item["latency_s"] = round(time.time() - t0, 1)
        results["items"].append(item)
        save()
        print(f"{key}: {item['status']} in {item['latency_s']}s {item['error'] or ''}", flush=True)
    save()


if __name__ == "__main__":
    main()
