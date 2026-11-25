# Architecture

## One contract, six stages

```
                 storyboard.json  ──validate (schema + cross-field rules)──┐
                                                                            │
 narration ──► timings.json ──┐                                             │
 references ─► approved refs ─┼─► keyframes ─► shots (Kaggle) ─┐            │
                              │                               ├─► assemble ─► 16:9 + 9:16 MP4, SRT
                              └──────────── music (Kaggle) ───┘
```

- **storyboard.json** is the only input a human edits. It holds every prompt, seed, line of
  narration, music cue, choice of candidate, transition and export setting. The pipeline never
  writes to it, so the contract stays human-approved.
- **schema/storyboard.schema.json** (JSON Schema 2020-12) fixes structure and ranges; for
  example, a real person must have a `consent_ref`, the end card must contain "AI", and an `i2v` shot
  must have a motion prompt, seed and clip length. **pipeline/validate.py** adds what a schema
  cannot express: IDs resolve, every speaker has a voice, shots are s01..sNN in order, music cues
  do not overlap, planned runtime is 60–90 s. `make film` stops before any model call if it fails.

| Stage | Reads | Writes | Model call |
|---|---|---|---|
| narration | lines, voices, style | `narration/<shot>_l<i>.wav`, `<shot>.wav`, `timings.json` | Gemini TTS, one per line |
| references | characters, locations, style block | `references/<id>_c<k>.png`, contact sheet | FLUX.2 klein, `reference_candidates` per subject |
| keyframes | shot prompt + subject descriptions + style block, approved refs | `keyframes/<shot>_c<k>.png`, `<shot>.png` | FLUX.2 klein with up to 4 reference images |
| shots | chosen keyframe, motion prompt, seed, Wan settings | `shots/<shot>.mp4` | Wan 2.2 TI2V-5B on Kaggle, one batch |
| music | cues, planned cue lengths | `music/<cue>_c<k>.wav` | ACE-Step 1.5 on Kaggle, one batch |
| assemble | all of the above + timeline | `cuts/*`, `final/*` | none (FFmpeg) |

## Timeline

Narration sets the pace. Each shot lasts `max(duration_s, offset_s + measured speech + tail_s)`,
snapped to 24 fps frames; subtitles use the measured line times. Music cue lengths are taken from
the **planned** durations plus 8 s headroom (rounded up to 5 s), so re-recording a line never
invalidates the score; the edit trims each take to the real cue length.

## Caching

`pipeline/common/cache.py`: each artifact has a key (for example `keyframe:s03:c1`) and a hash of
exactly the inputs that shape it (canonical JSON, SHA-256). `outputs/manifest.json` stores
key → hash + paths. A stage skips work when the stored hash matches and the files exist.
Downstream hashes include upstream **file** hashes (a shot's hash includes its chosen keyframe's
bytes), so a change flows forward only along its own path:

| You change | Model calls | Local work |
|---|---|---|
| one narration line | 1 TTS | that shot's segment if its length changed, re-mix, re-join |
| one keyframe prompt | `candidates` images for that shot, then 1 Wan job | that shot's segments |
| `style_block` | every reference, keyframe and shot (correctly) | everything |
| a music caption | that cue's takes | re-mix |
| ducking or loudness | none | re-mix, re-mux |

The final join and mux are cached too, so an unchanged re-run finishes in about a second.

## Failure handling

- **Retries** (`common/retry.py`): exponential backoff with jitter on network errors, HTTP 429 and
  5xx, honouring `Retry-After`. 4xx errors other than 429 fail fast (`ProviderError`).
- **Logging**: every attempt, failed or not, is a line in `runs.jsonl` with model, parameters,
  seed, latency, GPU minutes, estimated list-price cost, cache key and error.
- **GPU stages**: jobs are sent as one Kaggle batch (dataset upload → script kernel on a T4 →
  poll → download). The kernel rewrites `results.json` after every job, so a timeout keeps
  finished shots. Results are imported only when key **and** hash match the current storyboard.
  A job that fails `max_attempts` times is no longer sent.
- **Fallbacks**: a shot without a clip uses its `fallback` (Ken Burns or still) over its keyframe;
  a shot without a keyframe becomes a labelled placeholder; a cue without a take uses placeholder
  music. The film always assembles end to end, and `assembly_report.json` lists what fell back.
- **Manual route**: `make bundle-shots` / `bundle-music` zip the jobs and kernel for running on
  kaggle.com by hand; `--import` brings the results back through the same hash check.
- **Secrets** live only in `.env` (git-ignored); `.env.example` documents them.
- **Mock mode** (`make mock`, used by the tests) swaps every provider for a local stand-in and
  writes to `outputs_mock/` and `runs_mock.jsonl`, so test runs never pollute the real log.

## Sound

Narration lines are placed on the timeline, and the voice track is normalised as a whole (two-pass,
linear) to `mix.voice_lufs`. Each music take is normalised to `mix.music_lufs`, trimmed to its cue,
faded, then ducked under the voice with `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms,
release 1500 ms). The sum goes through two-pass `loudnorm` to −14 LUFS integrated, −1 dBTP.

## Picture

Every shot is rendered as a 16:9 master (clip trimmed by `trim_head_s`, slowed at most 1.25×,
then held with a gentle drift if the narration needs longer). The 9:16 export reframes each
master per shot: `center_crop` at `focus_x`, or `blur_fill` (full frame over a blurred copy).
Transitions are cuts or crossfades (`xfade`); the AI end card is drawn by FFmpeg. Subtitles are
ASS files sized per export so they stay in the vertical safe area; an SRT is exported for upload.
