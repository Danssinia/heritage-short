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

### F1: Gemini text model overloaded (smoke test, 25 Nov)
- What broke: gemini-3.8-flash returned HTTP 503 "model is currently experiencing high demand" twice
  (from terminal output; text-model calls are not logged in runs.jsonl).
- Impact: none on the film; the text model is only used for the optional back-translation.
- Workaround: left it; GEMINI_TEXT_MODEL can be switched to a lighter model.

### F2: Gemini TTS free-tier quota (narration, 25 Nov)
- What broke: make radio hit HTTP 429 "You exceeded your current quota" after 4 lines (s01-s04); s05 went
  through on a retry and s06 was ok, then s07 got three 429s with retries only 3 s and 5 s apart, and the
  fourth attempt failed with RemoteDisconnected (connection closed without response).
- Evidence: runs.jsonl run_id 20261125T171948Z-80c48e (5 error lines, 6 ok lines).
- Fix: pace Gemini calls (GEMINI_RPM, default 3/min), honour Google's retryDelay on 429, stop at once on a
  daily-quota error. Finished lines were cached, so no work was lost.

### F3: Kaggle CLI would not start (setup, 25 Nov)
- What broke: kaggle --version crashed: ModuleNotFoundError: No module named 'six' (Python 3.14 venv)
  (from terminal output).
- Fix: installed six and added it to requirements.txt (`six>=1.16`).

### F4: ACE-Step produced unusable audio on the T4 (music, 25 Nov)
- What broke: all 9 takes had the right length (30-45 s, runs.jsonl run_id 20261125T194717Z-2bce89, all
  logged "ok") but ffmpeg volumedetect measured mean_volume 0.0 dB and max_volume 0.0 dB: samples stuck at
  full scale, no audible music (from terminal output).
- Likely cause: float16 overflow (NaN/inf) on a T4, which has no native bfloat16.
- Fix: the kernel probes precisions with a 10 s test (float32 ran out of memory, bfloat16 worked: probe in
  outputs/_kaggle/music_out/results.json) and validates every take before saving. The broken WAVs were not
  committed.
- Lesson: "complete" on Kaggle does not mean "correct": check the output, not just the status.

### F5: Wan 2.2 out of GPU memory on the T4 (shots, 25 Nov)
- What broke: all 9 shots failed (runs.jsonl run_id 20261125T203208Z-15b86e, 832x480, 117 frames,
  30 steps). Probe, from the Kaggle log of version #1 and its results.json, which version #2 overwrote:
  float16 probe CUDA out of memory (108 MiB allocation failed, 14.54 GiB in use), bfloat16 probe ok.
  s01 (bfloat16) then tried to allocate 12.24 GiB (14.56 GiB GPU); s02-s09 failed in 0.3-1.1 s because
  memory was never released.
- Likely cause: the UMT5-XXL text encoder (roughly 11 GB in 16-bit, estimated) shared the GPU with the 5B
  transformer; bfloat16 on a T4 cannot use memory-efficient attention, so 832x480x117 frames needed a 12 GB
  attention buffer; offload hooks stayed on the GPU after the first error.
- Fix: kernel v3 encodes all prompts first with the text encoder alone (on the second T4), then frees it;
  clips reduced to 640x352, 93 frames (4 s), 25 steps; GPU cleaned after every failure.
- Trade-off: lower resolution, upscaled in the edit.
- Result after fix: 9/9 shots ok in float16, 8.0 min each (results.json, Kaggle version #2).

### F7: Wan 2.2 face artifacts and broken s09 (review of the first full build, 26 Nov)
- What broke: watching the first full build (commit c55c0fa) on my phone, s01, s02 and s08 had distorted
  faces, s06 was dark and muddy, and s09 broke into coloured blocks before the end card; the vertical
  center crop cut people out of s06/s07 (my phone review; not in the files).
- First fix: Ken Burns on the clean keyframes for s01, s02, s06, s08, s09 and blur_fill for s06/s07
  (commit 4cec5a3; assembly_report.json then listed those five shots as "ken_burns"). I rejected it
  because the shots lost their motion.
- Second fix: regenerate the 5 shots with new seeds (+1000: 311001, 311002, 311006, 311008, 311009) and
  gentle motion prompts with a static camera; s06 vertical framing changed to center_crop focus_x 0.87,
  s07 stays blur_fill.
- Result: TODO (pending: Kaggle shots run in progress).

### F8: End card showed an empty box at each line end (assemble, 26 Nov)
- What broke: every wrapped line of the end-card subtext ended in a box glyph (3 in the vertical film,
  1 in the horizontal), seen on the last frame of both MP4s (from terminal output).
- Cause: FFmpeg 8 drawtext renders the newline in a text file as a glyph.
- Fix: one drawtext per line, each centred (`render_end_card` in pipeline/assemble.py, commit 33058f7).

### F9: git push timed out with the rebuilt films (repository, 26 Nov)
- What broke: git push failed three times with "HTTP 408 ... the remote end hung up unexpectedly" while
  sending about 100 MB of rebuilt MP4s (53 MB + 47 MB) in one commit (from terminal output). The build
  before (commit c55c0fa) had already pushed a 50.85 MB file with a GitHub large-file warning.
- Fix: the final films (`outputs/final/heritage_*.mp4`) are gitignored (commit 33058f7) and rebuilt from
  the repository by `make film-offline` (cached clips, no Kaggle). Publishing them as a GitHub Release:
  TODO (not done yet).
