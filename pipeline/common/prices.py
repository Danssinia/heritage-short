"""List-price equivalents used for est_cost_usd in runs.jsonl.

We pay nothing (free tiers), but COSTS.md reports what the same calls would cost
at list price. Update these if the providers change their prices, and say so in COSTS.md.
"""
from __future__ import annotations

import math

# Gemini 3.8 Flash TTS: $0.50 per 1M input tokens, $9.00 per 1M output (audio) tokens.
# Source: Vercel AI Gateway model page for google/gemini-3.8-flash-tts (checked 2026-11-25).
GEMINI_TTS_IN_PER_M = 0.50
GEMINI_TTS_OUT_PER_M = 9.00

# Gemini text model: set from the Gemini API pricing page when you check it.
GEMINI_TEXT_IN_PER_M = 0.0
GEMINI_TEXT_OUT_PER_M = 0.0

# Cloudflare Workers AI, FLUX.2 [klein] 4B: $0.000059 per input 512x512 tile,
# $0.000287 per output 512x512 tile. Source: developers.cloudflare.com/workers-ai/models/flux-2-klein-4b
KLEIN4B_IN_TILE = 0.000059
KLEIN4B_OUT_TILE = 0.000287

# Kaggle T4 GPU time is free. List-price equivalent ASSUMPTION: one NVIDIA T4 on-demand
# at about $0.35/hour on a major cloud. Verify against a current cloud price page.
T4_PER_HOUR = 0.35


def tts_cost(usage: dict) -> float:
    tin = usage.get("promptTokenCount", 0) or 0
    tout = usage.get("candidatesTokenCount", 0) or 0
    return tin / 1e6 * GEMINI_TTS_IN_PER_M + tout / 1e6 * GEMINI_TTS_OUT_PER_M


def text_cost(usage: dict) -> float:
    tin = usage.get("promptTokenCount", 0) or 0
    tout = usage.get("candidatesTokenCount", 0) or 0
    return tin / 1e6 * GEMINI_TEXT_IN_PER_M + tout / 1e6 * GEMINI_TEXT_OUT_PER_M


def tiles(width: int, height: int) -> int:
    return math.ceil(width / 512) * math.ceil(height / 512)


def klein_cost(width: int, height: int, n_refs: int) -> float:
    return tiles(width, height) * KLEIN4B_OUT_TILE + n_refs * KLEIN4B_IN_TILE


def gpu_cost(gpu_minutes: float) -> float:
    return gpu_minutes / 60.0 * T4_PER_HOUR
