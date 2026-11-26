# Costs and measurements

We paid **$0**. Every number below comes from `runs.jsonl` (`make costs` prints the table).
List-price equivalents use the prices in `pipeline/common/prices.py`, with their sources.

## Measured GPU runs (Kaggle)

| Stage | Hardware / precision | Work | Time | Cost |
|---|---|---|---|---|
| Wan 2.2 TI2V-5B (shots) | Kaggle 2x T4, float16 | 9 clips, 640x352, 93 frames, 25 steps | 8.0 min per clip, 72 GPU-min + ~8 min setup (80 min total) | ~$0.42 list-price equivalent at $0.35/T4-hour, $0 paid |
| Wan 2.2 TI2V-5B (shots), rerun of 5 (run 20261126T113645Z-6552a8) | Kaggle 2x T4, float16 | 5 clips (s01, s02, s06, s08, s09), 640x352, 93 frames, 25 steps | 7.8-7.9 min per clip, 39.3 GPU-min, 45.9 min kernel time | ~$0.23 list-price equivalent at $0.35/T4-hour, $0 paid |
| ACE-Step 1.5 (music), run 1 | Kaggle T4, float16 | 9 takes (3 cues x 3) | 5.5 min from kernel push to complete (terminal log of make music); 133 s of generation in runs.jsonl | $0 paid; output unusable (see FAILURES.md F4) |
| ACE-Step 1.5 (music), run 2 | Kaggle T4, bfloat16 (chosen by probe; float32 ran out of memory) | 9 takes | 3.4 min generation (202 s) + 2.2 min load and probe | $0 paid |

## Per stage (`make costs`, all runs in runs.jsonl, 26 Nov after the final build)

| Stage | Model | Calls (ok / failed) | Median latency (s) | Total latency (min) | GPU minutes | List-price equivalent (USD) |
|---|---|---|---|---|---|---|
| keyframes | @cf/black-forest-labs/flux-2-klein-4b | 18 / 0 | 10.33 | 3.8 | 0.0 | 0.0337 |
| music | ACE-Step/acestep-v15-xl-turbo-diffusers | 18 / 0 | 19.55 | 5.6 | 5.6 | 0.0326 |
| narration | gemini-3.8-flash-tts | 10 / 5 | 5.21 | 1.7 | 0.0 | 0.0116 |
| references | @cf/black-forest-labs/flux-2-klein-4b | 24 / 0 | 14.81 | 5.7 | 0.0 | 0.0281 |
| shots | Wan-AI/Wan2.2-TI2V-5B-Diffusers | 14 / 9 | 479.20 | 111.2 | 111.7 | 0.6515 |
| smoke | @cf/black-forest-labs/flux-2-klein-4b | 4 / 0 | 5.77 | 0.4 | 0.0 | 0.0000 |
| smoke | gemini-3.8-flash-tts | 4 / 0 | 2.80 | 0.3 | 0.0 | 0.0000 |

Total: 106 calls, 117.3 GPU minutes, $0.7575 list-price equivalent (we paid $0).

Failed calls: narration 5 = the Gemini 429 quota errors (FAILURES.md F2); shots 9 = the out-of-memory run
(FAILURES.md F5). Shots include all three Wan runs: 9 failed, 9 ok, then 5 regenerated (FAILURES.md F7).

## Free tiers as actually found (fill in when you hit them)

| Provider | What the docs said | What I actually got | Date checked |
|---|---|---|---|
| Gemini API (TTS, text) | free tier | TODO (requests before a 429?) | TODO |
| Cloudflare Workers AI | daily free allowance | TODO (images per day) | TODO |
| Kaggle | about 30 GPU hours a week | 2x T4 GPUs; Wan clip 8.0 min each at 640x352; ACE-Step 9 takes in minutes | 2026-11-26 |

## Prices used for the list-price equivalent

| Item | Price | Source |
|---|---|---|
| Gemini 3.8 Flash TTS | $0.50 / 1M input tokens, $9.00 / 1M output tokens | Vercel AI Gateway model page, checked 2026-11-25 |
| FLUX.2 [klein] 4B on Workers AI | $0.000059 per input 512² tile, $0.000287 per output 512² tile | Cloudflare model page |
| Kaggle T4 GPU time | assumed $0.35 per T4-hour (cloud on-demand equivalent) | TODO: verify on a cloud price page |
| FFmpeg assembly | local CPU, not priced | n/a |

## Frontier comparison

TODO if you had access to Omni Flash / Nano Banana / Lyria 3.5; otherwise say you did not.
