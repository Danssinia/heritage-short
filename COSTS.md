# Costs and measurements

We paid **$0**. Every number below comes from `runs.jsonl` (`make costs` prints the table).
List-price equivalents use the prices in `pipeline/common/prices.py`, with their sources.

## Per stage (paste the output of `make costs` here)

TODO: paste the table after your final run.

## Free tiers as actually found (fill in when you hit them)

| Provider | What the docs said | What I actually got | Date checked |
|---|---|---|---|
| Gemini API (TTS, text) | free tier | TODO (requests before a 429?) | TODO |
| Cloudflare Workers AI | daily free allowance | TODO (images per day) | TODO |
| Kaggle | about 30 GPU hours a week | TODO (queue time, minutes per Wan clip) | TODO |

## Prices used for the list-price equivalent

| Item | Price | Source |
|---|---|---|
| Gemini 3.8 Flash TTS | $0.50 / 1M input tokens, $9.00 / 1M output tokens | Vercel AI Gateway model page, checked 2026-11-25 |
| FLUX.2 [klein] 4B on Workers AI | $0.000059 per input 512² tile, $0.000287 per output 512² tile | Cloudflare model page |
| Kaggle T4 GPU time | assumed $0.35 per T4-hour (cloud on-demand equivalent) | TODO: verify on a cloud price page |
| FFmpeg assembly | local CPU, not priced | n/a |

## Frontier comparison

TODO if you had access to Omni Flash / Nano Banana / Lyria 3.5; otherwise say you did not.
