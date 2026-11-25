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
