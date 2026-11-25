PY := .venv/bin/python
.DEFAULT_GOAL := help
.PHONY: help setup smoke validate test radio narration references keyframes shots music assemble film film-offline mock costs backtranslate bundle-shots bundle-music

help: ## list commands
	@grep -E '^[a-z-]+:.*## ' Makefile | awk 'BEGIN{FS=":.*## "}{printf "  make %-14s %s\n", $$1, $$2}'

setup: ## create .venv, install dependencies, create .env from the example
	python3 -m venv .venv
	.venv/bin/pip install -q -U pip
	.venv/bin/pip install -q -r requirements.txt
	@test -f .env || (cp .env.example .env && echo "created .env: fill in your keys")
	@command -v ffmpeg >/dev/null || echo "!! ffmpeg missing: sudo apt install -y ffmpeg"

smoke: ## call each provider once and log latency
	$(PY) -m pipeline.smoke_test

validate: ## check storyboard.json against the schema and list open choices
	$(PY) -m pipeline.validate

test: ## offline unit tests
	$(PY) -m pytest -q tests

radio: ## radio cut: narration + placeholder music + subtitles on black
	$(PY) -m pipeline.run --radio

narration: ## TTS only
	$(PY) -m pipeline.narration

references: ## character/location reference sheets
	$(PY) -m pipeline.references

keyframes: ## one still per shot, conditioned on the approved references
	$(PY) -m pipeline.keyframes

shots: ## Wan 2.2 image-to-video on Kaggle (waits for the kernel)
	$(PY) -m pipeline.shots

music: ## ACE-Step score cues on Kaggle
	$(PY) -m pipeline.music

assemble: ## edit, mix, subtitles, end card, both exports
	$(PY) -m pipeline.assemble

film: ## THE ONE COMMAND: whole pipeline, regenerating only what changed
	$(PY) -m pipeline.run

film-offline: ## whole pipeline without contacting Kaggle (cached clips + fallbacks)
	$(PY) -m pipeline.run --no-remote

mock: ## dry run with stand-in models (no keys needed; writes outputs_mock/)
	$(PY) -m pipeline.run --mock

costs: ## Markdown tables for COSTS.md from runs.jsonl
	$(PY) -m pipeline.costs

backtranslate: ## Gemini back-translation of the Amharic lines (meaning check)
	$(PY) -m pipeline.script --backtranslate

bundle-shots: ## zip the Wan jobs for running by hand on kaggle.com
	$(PY) -m pipeline.shots --no-remote

bundle-music: ## zip the ACE-Step jobs for running by hand on kaggle.com
	$(PY) -m pipeline.music --no-remote
