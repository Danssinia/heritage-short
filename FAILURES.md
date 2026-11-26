# Failures

Every real blocker, in the order it happened: what broke, what you tried, what fixed it (or how
you worked around it). Quota, memory, consistency and language problems are exactly what this
file is for. Link the evidence: `runs.jsonl` run_id, error text, Kaggle log.

Template:

### F1: TODO short title (stage, date)
- **What broke:** TODO (exact error or symptom)
- **Evidence:** TODO (`runs.jsonl` run_id / error line / screenshot path)
- **What I tried:** TODO
- **What fixed it / workaround:** TODO
- **What I would do differently:** TODO

Things worth recording if they happen:
- Gemini TTS: a word or name pronounced wrongly in Amharic, a line read with the wrong emotion, a rate limit (HTTP 429).
- Cloudflare: daily image allowance used up (note how many images you got), reference images too large.
- Kaggle: phone verification, queue time, the GPU session cut off, out-of-memory on the T4, black frames in float16.
- Consistency: the father's face drifting between shots, and what fixed it.
- Tools that moved: anything in the challenge brief that was out of date, and what replaced it.

### F5: Wan 2.2 out of GPU memory on the T4 (shots, 25 Nov)
- What broke: all 9 shots failed. float16 probe: CUDA out of memory; s01 tried to allocate 12.24 GiB
  (14.56 GiB GPU); s02-s09 then failed in 0.3-1.1 s because memory was never released.
- Cause: the 11 GB UMT5 text encoder shared the GPU with the 5B transformer; bfloat16 on a T4 cannot use
  memory-efficient attention, so 832x480x117 frames needed a 12 GB attention buffer; offload hooks stayed
  on the GPU after the first error.
- Fix: kernel v3 encodes all prompts first with the text encoder alone (on the second T4), then frees it;
  clips reduced to 640x352, 93 frames (4 s), 25 steps; GPU cleaned after every failure.
- Trade-off: lower resolution, upscaled in the edit.
- Result after fix: 9/9 shots ok in float16, 8.0 min each (results.json, Kaggle version #2).
