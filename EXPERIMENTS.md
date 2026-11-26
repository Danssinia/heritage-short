# Experiments

Format for every entry: **hypothesis → change → result → decision**, with evidence (a `runs.jsonl`
run_id or cache key, a file in `outputs/`, a measurement). Aim for ten. Keep failed hypotheses:
"I expected X and got Y" is the most useful kind of entry.

## Log

### E1: Narrator voice Kore vs Puck
- **Hypothesis:** the narrator is a young man, so a male voice (Puck) fits better than Kore, which the
  pipeline started with.
- **Change:** `defaults.narration.voices.narrator` Kore → Puck (commit 73dfe95); Dad stays Charon.
- **Result (evidence):** the smoke test spoke an Amharic line with Kore (pipeline/smoke_test.py,
  outputs/smoke/tts_amharic.wav, smoke run 20261125T194219Z-c2718f; force-added to the repository although
  outputs/smoke/ is gitignored). I chose Puck because the narrator is a young man; every logged narration call uses Puck or
  Charon (runs.jsonl run_ids 20261125T171948Z-80c48e, 20261125T173524Z-35dc46). In user test 1 (DESIGN.md)
  brother 1 later praised the voice as natural: "it sounds so natural and human-like".
- **Decision:** keep Puck for the narrator and Charon for Dad.

### E2: Character references from text only vs from real family photos
- **Hypothesis:** a private reference photo makes each illustrated character look like the real person,
  which text alone cannot.
- **Change:** text-only references (runs.jsonl run_id 20261125T180328Z-227b6a: 15 images, `refs: 0`) vs
  photo references for dad, mom and me (run_id 20261125T185620Z-4f8a78: 9 images, `refs: 1`,
  `from_photo: true`), with consent recorded in ETHICS.md (commit 5d803e1).
- **Result (evidence):** both sets in git history (outputs/references/ at commits 5d803e1 and ed9f9be).
  The photo-based drawings looked somewhat more like my family than the text-only ones. They are not a
  close likeness, but they are clearly better, so I kept them.
- **Decision:** approved photo-based references dad 2, mom 1, me 0 (commit 7811312).

### E3: Music precision on the T4
- **Hypothesis:** ACE-Step runs in float16 on a T4.
- **Change:** float16 (runs.jsonl run_id 20261125T194717Z-2bce89) vs a precision probe (run_id
  20261125T202014Z-bbbcb3).
- **Result (evidence):** the float16 takes were all logged "ok" but were stuck at full scale, no music
  (FAILURES.md F4). The probe in outputs/_kaggle/music_out/results.json: float32 out of memory,
  bfloat16 ok; 9/9 takes in bfloat16.
- **Decision:** probe first, validate every take (commit 8117dd2).

### E4: Wan clip size on the T4
- **Hypothesis:** 832x480, 117 frames, 30 steps fits on a T4.
- **Change:** 832x480x117 frames (runs.jsonl run_id 20261125T203208Z-15b86e) vs 640x352x93 frames,
  25 steps, kernel v3 (run_id 20261125T210033Z-45dcd0).
- **Result (evidence):** the first run: 0/9 ok, CUDA out of memory (tried to allocate 12.24 GiB). The
  second: 9/9 ok in float16 on 2x T4, 478–481 s per clip (8.0 min), outputs/_kaggle/shots_out/results.json.
- **Decision:** 640x352x93 frames (commit b2a1dcc); see FAILURES.md F5.

### E5: Music takes (3 takes per cue, chosen by listening)
- **Hypothesis:** with 3 takes per cue, one will match each part of the story.
- **Change:** 9 takes from run_id 20261125T202014Z-bbbcb3, chosen by listening.
- **Result (evidence):** chosen in storyboard.json `music.cues[].chosen_candidate`; used in
  outputs/final/assembly_report.json `mix.music_sources`:
  - m01_c2: the most light and playful; it fits the teasing at breakfast.
  - m02_c1: the quietest and softest; it doesn't distract from Dad leaving the table.
  - m03_c2: the warmest and happiest; it carries the laugh and the dedication to my dad.
- **Decision:** m01=2, m02=1, m03=2 (commit c55c0fa).

### E6: Wan clip vs Ken Burns
- **Hypothesis:** Ken Burns on the clean keyframes removes the Wan face artifacts in s01, s02, s06, s08, s09.
- **Change:** `motion.mode` i2v → ken_burns on those five shots (commit 4cec5a3).
- **Result (evidence):** assembly_report.json listed the five as "ken_burns" (0 new model calls); the face
  artifacts were gone, but the shots lost their motion (my review).
- **Decision:** rejected; regenerate with Wan instead (E7).

### E7: Gentle motion prompts, static camera, new seeds
- **Hypothesis:** small, calm motion with a static camera keeps faces stable in Wan.
- **Change:** s01, s02, s06, s08, s09: new motion prompts ending "faces stay steady, static camera", seeds
  +1000, `camera` static for s01 and s09; old clips backed up in outputs/shots_v1/ (not in git).
- **Result (evidence):** TODO (pending: Kaggle shots run in progress).
- **Decision:** TODO.

### E8: Vertical framing for s06 and s07
- **Hypothesis:** a center crop can keep the people in a 9:16 frame.
- **Change:** the center crop (focus_x 0.5) cut people out; s06 now center_crop focus_x 0.87 (Dad
  stands at about 855–1065 px of 1280; the crop is 405 px wide); s07 blur_fill because the two faces are
  about 780 px apart.
- **Result (evidence):** TODO (pending).
- **Decision:** TODO.

### E9: True-peak headroom for AAC
- **Hypothesis:** normalising to -1 dBTP before encoding keeps the MP4 below -1 dBTP.
- **Change:** `mix.true_peak_db` -1 → -2 (commit c55c0fa).
- **Result (evidence):** at -1, the pre-encode WAV measured -1.00 dBTP but the AAC MP4 measured -0.3
  dBTP (ffmpeg ebur128, from terminal output). At -2, the MP4s measure -1.55 dBTP and -14.23 LUFS
  (outputs/final/assembly_report.json `final_measured`, which now measures the MP4s themselves).
- **Decision:** keep -2 dBTP before encoding.

### E10: End card dedication
- **Hypothesis:** dedicating the film to our dad makes it more personal for the family.
- **Change:** end-card subtext "In loving memory of our dad, Abbaye. ..." (commit 33058f7), from my
  brother's suggestion in user test 2 (DESIGN.md).
- **Result (evidence):** checked on the last frame of both MP4s. TODO: family reaction.
- **Decision:** keep.
