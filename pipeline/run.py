"""Run the pipeline end to end from storyboard.json.

  python -m pipeline.run                 validate -> narration -> references -> keyframes -> shots -> music -> assemble
  python -m pipeline.run --radio         validate -> narration -> radio cut (no pictures, placeholder music)
  python -m pipeline.run --no-remote     never contact Kaggle: use cached clips/music, fall back for the rest
  python -m pipeline.run --from shots    start at a stage
  python -m pipeline.run --mock          offline dry run with stand-in models (writes outputs_mock/, runs_mock.jsonl)

Each stage skips work whose inputs have not changed, so a re-run after editing one
shot regenerates only that shot. Check runs.jsonl to see exactly which calls were made.
"""
from __future__ import annotations

import argparse
import json
import os
import time

STAGES = ["narration", "references", "keyframes", "shots", "music", "assemble"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--radio", action="store_true", help="make only the radio cut")
    ap.add_argument("--no-remote", action="store_true", help="do not send jobs to Kaggle")
    ap.add_argument("--from", dest="start", choices=STAGES, help="start at this stage")
    ap.add_argument("--only", choices=STAGES, help="run a single stage")
    ap.add_argument("--mock", action="store_true", help="offline dry run with stand-in models")
    a = ap.parse_args()
    if a.mock:
        os.environ["HERITAGE_MOCK"] = "1"

    # Import after setting HERITAGE_MOCK so every module sees it.
    from . import assemble, keyframes, music, narration, references, shots
    from .common import story
    from .common.config import ROOT, runlog_path
    from .common.runlog import RUN_ID
    from .validate import warnings

    sb = story.load()
    print(f"storyboard OK: {len(sb['shots'])} shots. run_id={RUN_ID}")
    notes = warnings(sb)
    if notes:
        print(f"  {len(notes)} choice(s) still open (candidate 0 is used meanwhile); run `make validate` to list them")

    log = runlog_path()
    before = sum(1 for _ in log.open()) if log.exists() else 0
    t0 = time.time()

    if a.radio:
        print("\n== narration"); narration.run()
        print("\n== radio cut"); assemble.run_radio()
    else:
        todo = [a.only] if a.only else STAGES[STAGES.index(a.start):] if a.start else STAGES
        for stage in todo:
            print(f"\n== {stage}")
            if stage == "narration":
                narration.run()
            elif stage == "references":
                references.run()
            elif stage == "keyframes":
                keyframes.run()
            elif stage == "shots":
                shots.run(no_remote=a.no_remote)
            elif stage == "music":
                music.run(no_remote=a.no_remote)
            elif stage == "assemble":
                assemble.run()

    new = []
    if log.exists():
        with log.open() as f:
            new = [json.loads(line) for i, line in enumerate(f) if i >= before]
    by_stage: dict[str, int] = {}
    for r in new:
        by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
    print(f"\nDone in {time.time() - t0:.0f}s. New model calls this run: {len(new)} "
          f"{json.dumps(by_stage) if by_stage else ''} (logged in {log.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
