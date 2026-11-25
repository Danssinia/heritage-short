# I'm Only Eating for You: a Heritage Short pipeline

A 60–90 second film about a real breakfast in my family, narrated in **Amharic** with
English subtitles and an original score, made entirely by a code pipeline from one
contract file, [`storyboard.json`](storyboard.json).

```bash
make setup     # once: virtualenv, dependencies, .env
make film      # the whole pipeline: regenerates only what changed
```

`make film` runs: **validate → narration → references → keyframes → shots → music → assemble**,
and writes `outputs/final/heritage_horizontal_16x9.mp4`, `heritage_vertical_9x16.mp4`
and `heritage.en.srt`. Every model call is logged in [`runs.jsonl`](runs.jsonl).

## What each stage does

| Stage | Model / tool | Where it runs | Output |
|---|---|---|---|
| validate | JSON Schema + cross-field checks | local | stops the run if the contract is broken |
| narration | Gemini 3.8 Flash TTS (`gemini-3.8-flash-tts`), Amharic | Gemini API (free tier) | `outputs/narration/<shot>.wav`, `timings.json` |
| references | FLUX.2 [klein] 4B | Cloudflare Workers AI (free daily allowance) | `outputs/references/*` + contact sheet |
| keyframes | FLUX.2 [klein] 4B, conditioned on the approved references | Cloudflare Workers AI | `outputs/keyframes/<shot>.png` + contact sheet |
| shots | Wan 2.2 TI2V-5B (diffusers), image-to-video, 832×480, 24 fps | Kaggle T4 via the `kaggle` CLI | `outputs/shots/<shot>.mp4` |
| music | ACE-Step 1.5 (diffusers `AceStepPipeline`), instrumental | Kaggle T4 | `outputs/music/<cue>_c<k>.wav` |
| assemble | FFmpeg: cut, crossfades, ducking, loudnorm, subtitles, end card | local | `outputs/final/*` |

Costs: **$0 paid**. List-price equivalents and measured latency are in [COSTS.md](COSTS.md)
(`make costs` builds the tables from `runs.jsonl`).

## Setup (Ubuntu)

1. `sudo apt install -y ffmpeg python3-venv make`
2. `make setup`, then fill in `.env` (the file explains where each key comes from):
   - `GEMINI_API_KEY` from Google AI Studio
   - `CF_ACCOUNT_ID`, `CF_API_TOKEN` (Workers AI template) from Cloudflare
   - `KAGGLE_USERNAME`, `KAGGLE_KEY` from Kaggle → Settings → API (phone-verified account, so the kernel gets a GPU and internet)
3. `make smoke`: one call per provider. Listen to `outputs/smoke/tts_amharic.wav`.
4. `make test`: offline tests. `make mock`: full dry run with stand-in models, no keys needed.

## The working loop

```
make radio                      # narration + placeholder music + subtitles on black -> user test 1
make references                 # look at outputs/references/contact_sheet.jpg -> set approved_candidate
make keyframes                  # look at outputs/keyframes/contact_sheet.jpg -> set chosen_candidate
make shots                      # Wan 2.2 on Kaggle (long; leave it running)
make music                      # ACE-Step on Kaggle -> listen, set chosen_candidate per cue
make assemble                   # both exports -> user test 2
```

Every choice (approved reference, chosen keyframe, chosen music take) is an index in
`storyboard.json`, so the film can be regenerated exactly from the contract.

### Regenerating one shot (the walkthrough demo)

1. Edit one narration line (or one `keyframe.prompt`) in `storyboard.json`.
2. `make film` (or `make film-offline` to skip Kaggle).
3. The summary line and `runs.jsonl` show exactly one new model call (one TTS line, or the
   shot's keyframe candidates); every other stage prints "cached". The edit re-renders
   only that shot's segment, re-joins and re-mixes.

### Running Kaggle by hand (fallback)

If the CLI route fails (queue, auth, quota), `make bundle-shots` writes
`outputs/_kaggle/shots_bundle.zip`. On kaggle.com: **Datasets → New dataset**, upload the
`heritage-shots-jobs` folder from the zip; **Code → New notebook**, Accelerator **GPU T4 x2**,
Internet **on**, attach the dataset, paste `kernel.py` into a cell and run it. Download the
output (results.json + mp4s), then:

```bash
.venv/bin/python -m pipeline.shots --import ~/Downloads/output.zip
```

Same for music with `make bundle-music` and `python -m pipeline.music --import ...`.
Imports are matched by shot id **and** input hash, so results from an old storyboard are ignored.

### When a stage fails

- Retries with exponential backoff on network errors, HTTP 429 and 5xx (honouring `Retry-After`).
- A Wan shot that fails `max_attempts` times stops being sent; the edit uses its `fallback`
  (Ken Burns over the keyframe, or a still). A missing keyframe becomes a labelled placeholder,
  so the film always assembles end to end.

## Repository map

```
storyboard.json              the contract
schema/storyboard.schema.json
pipeline/                    one module per stage + run.py orchestrator
  common/                    config, cache, retry, runlog, timeline, providers (gemini, cloudflare, kaggle)
kaggle/wan22_i2v/kernel.py   the only code that runs on the GPU (shots)
kaggle/acestep/kernel.py     (music)
tests/                       offline tests (make test)
outputs/                     generated media + manifest.json (input hash -> artifact)
runs.jsonl                   one line per model call
DESIGN.md ARCHITECTURE.md EXPERIMENTS.md FAILURES.md COSTS.md ETHICS.md
```

## Licences and labelling

Code: MIT. Model and output licences, consent records and the labelling plan are in
[ETHICS.md](ETHICS.md). The film ends with an AI end card and is posted with the platform's
AI-content label switched on.
