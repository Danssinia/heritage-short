# Your checklist to the deadline (Thursday 26 Nov, 23:59 EAT)

Tick each box. Times are targets; the Kaggle steps are the slow ones, so start them early.

## Wednesday evening: setup + radio cut + user test 1

- [ ] **1. Open the project.** Unzip, open the folder in Antigravity, open a terminal in it.
- [ ] **2. Install.** `sudo apt install -y ffmpeg python3-venv make` then `make setup`.
- [ ] **3. Keys.** Fill `.env` (instructions inside it). Then `make smoke`. Listen to `outputs/smoke/tts_amharic.wav`.
      Anything that fails → a line in `FAILURES.md`.
- [ ] **4. Git.** `git init && git add . && git commit -m "Pipeline skeleton"` and push to a new **public** GitHub repo.
      Check `.env` is NOT in `git status`.
- [ ] **5. Consent.** Talk to your father and mother. Read them the Amharic lines (especially Dad's line in s08).
      Fill `ETHICS.md` (consent-dad, consent-mom, consent-me). Commit.
- [ ] **6. Fix the story.** In `storyboard.json`, correct every Amharic line in your own words and make the
      English subtitles match. Edit the `me` character description so it looks like you (man/woman, hair, clothes),
      and the parents' descriptions if you want them closer to real life. `make validate`.
- [ ] **7. Radio cut.** `make radio` → `outputs/final/radio_cut.mp4`. Listen. Wrong pronunciation? Change the
      spelling of the word or the `style`, run `make radio` again (only that line regenerates).
- [ ] **8. User test 1.** Send the radio cut to at least 3 relatives (family WhatsApp). Write what they said in
      `DESIGN.md`, change `storyboard.json` because of it, commit with a message like "Radio cut feedback: ...".

## Wednesday night: pictures, then leave Kaggle running

- [ ] **9. References.** `make references` → open `outputs/references/contact_sheet.jpg`. For each of dad, mom, me,
      dining, wash_corner write the best candidate number into `approved_candidate`. If none is good, change the
      description or seed and rerun.
- [ ] **10. Keyframes.** `make keyframes` → open `outputs/keyframes/contact_sheet.jpg`. Set `chosen_candidate` per shot.
      Check faces and hands. Re-prompt bad shots (`.venv/bin/python -m pipeline.keyframes --only s03`).
- [ ] **11. Music first (quick test of the Kaggle route).** `make music`. It uploads jobs, runs ACE-Step on a T4 and
      downloads 9 takes. If it fails, read the Kaggle log link it prints, note it in `FAILURES.md`, try the manual
      route in the README.
- [ ] **12. Shots overnight.** `make shots`. This can take hours: leave the terminal open (or run it with
      `nohup make shots > shots.log 2>&1 &`). Before you sleep, check the first clip finished in the Kaggle log and
      note the minutes per clip.

## Thursday: the edit, user test 2, documents, release

- [ ] **13. Choose music.** Listen to `outputs/music/m01_c0..2.wav` etc. Set `chosen_candidate` per cue, write why in `EXPERIMENTS.md`.
- [ ] **14. Assemble.** `make film` (everything cached, so it only edits). Watch both files in `outputs/final/` on your phone.
      Shots without a Wan clip use Ken Burns automatically (listed at the end of the run).
- [ ] **15. User test 2 (by 16:00).** Send the vertical cut to 3+ people, record in `DESIGN.md`, make the changes, `make film`, commit.
- [ ] **16. Documents.** `make costs` → paste into `COSTS.md`. Fill `EXPERIMENTS.md` (aim for 10 with real results),
      `FAILURES.md`, the TODOs in `DESIGN.md`. Commit and push.
- [ ] **17. Clean-clone check.** `git clone <your repo> /tmp/check && cd /tmp/check && make setup && make film-offline`.
      No keys needed: it should rebuild the film from the committed outputs with "New model calls this run: 0".
- [ ] **18. Walkthrough video (≤ 5 min).** Show `storyboard.json` → architecture → one hard decision → change one
      narration line → `make film-offline` → show the run summary "New model calls this run: 1" and the new line in
      `runs.jsonl` → show the new film.
- [ ] **19. Post.** Upload the vertical MP4 with the AI label on; write the post yourself (story, why it matters, one thing learned).
- [ ] **20. Report + submit by ~22:00.** Report (PDF/Word): what you made and for whom, audience feedback, hardest problem,
      one suggested practice that helped and one that did not, ceiling work, what next. Submit both assignments.
