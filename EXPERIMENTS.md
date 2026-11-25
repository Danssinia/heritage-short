# Experiments

Format for every entry: **hypothesis → change → result → decision**, with evidence (a `runs.jsonl`
run_id or cache key, a file in `outputs/`, a measurement). Aim for ten. Keep failed hypotheses:
"I expected X and got Y" is the most useful kind of entry.

The list below is a plan of experiments this pipeline is set up to run cheaply. Delete the ones
you do not run; move the ones you do into the log section with real results.

## Planned

| # | Hypothesis | Change (one variable) | How to measure |
|---|---|---|---|
| E1 | Reference images keep the father recognisable across shots | `use_references: false` vs `true` on s03, s06, s08 (same seeds) | contact sheets side by side; ask 3 people "is this the same man?" |
| E2 | A per-line style note improves the punchline more than changing the voice | s08 dad line: style text vs voice `Charon` → another voice | blind listen with 3 relatives |
| E3 | Gemini TTS pronounces family words (እናቴ, አባቴ, ማዕድ) correctly | listen to every line; `make backtranslate` | count lines needing respelling |
| E4 | Back-translation catches meaning drift in the Amharic lines | compare Gemini back-translation vs `subtitle_en` | number of lines rewritten |
| E5 | `blur_fill` beats `center_crop` for wide shots in 9:16 | s01/s09 in both modes | 3 people pick on a phone |
| E6 | Wan in float16 on a T4 works without black frames | `dtype: auto` (fp16) vs `bfloat16` on one shot | results.json status + latency |
| E7 | 20 steps are almost as good as 30 at 480p and much faster | `steps` 20 vs 30 on two shots | latency in runs.jsonl + side-by-side |
| E8 | Wan clips beat Ken Burns for emotional shots (s03, s08) | set `mode: ken_burns` on one of them | blind preference, 3+ people |
| E9 | Playful-tension-playful cue structure follows the story better than one cue | 3 cues vs one 80 s cue | testers' comments |
| E10 | Ducking 0.02/6/300/1500 keeps the voice clear on a phone speaker | vs ratio 3 and release 800 | phone listen, notes |
| E11 | FLUX.2 klein 4B keeps style and faces better than FLUX.1 schnell | `defaults.keyframe.model` swap on 3 shots | contact sheets, latency, cost |

## Log

### E1: TODO title
- **Hypothesis:** TODO
- **Change:** TODO
- **Result (evidence):** TODO (run_id …, files …)
- **Decision:** TODO
