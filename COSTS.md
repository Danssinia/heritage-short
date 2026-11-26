# Costs and measurements

We paid **$0**. Every number below comes from `runs.jsonl` (`make costs` prints the table).
List-price equivalents use the prices in `pipeline/common/prices.py`, with their sources.

## Per stage (paste the output of `make costs` here)

## Measured GPU runs (Kaggle)

| Stage | Hardware / precision | Work | Time | Cost |
|---|---|---|---|---|
| Wan 2.2 TI2V-5B (shots) | Kaggle 2x T4, float16 | 9 clips, 640x352, 93 frames, 25 steps | 8.0 min per clip, 72 GPU-min + ~8 min setup (80 min total) | ~$0.42 list-price equivalent at $0.35/T4-hour, $0 paid |
| ACE-Step 1.5 (music), run 1 | Kaggle T4, float16 | 9 takes (3 cues x 3) | 2.2 min generation (133 s) | $0 paid; output unusable (see FAILURES.md F4) |
| ACE-Step 1.5 (music), run 2 | Kaggle T4, bfloat16 (chosen by probe; float32 ran out of memory) | 9 takes | 3.4 min generation (202 s) + 2.2 min load and probe | $0 paid |

Run `make costs` after the final build for the full per-stage table from runs.jsonl.

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
