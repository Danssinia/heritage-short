"""Gemini API over REST: text (script/back-translation) and TTS (narration).

TTS request shape follows the Gemini 3.8 TTS schema: the transcript goes in
parts[].text (read verbatim), the delivery note in parts[].speech_metadata.style,
and the voice in speechConfig.voiceConfig.voice. The response is a WAV file
(RIFF header, 24 kHz mono 16-bit) at candidates[0].content.parts[0].inlineData.data.
"""
from __future__ import annotations

import base64
import io
import json
import math
import random
import wave

import requests

from ..config import env, mock
from ..retry import ProviderError, RetryableError

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TIMEOUT = 120


def _post(model: str, body: dict) -> dict:
    url = f"{BASE}/{model}:generateContent"
    headers = {"x-goog-api-key": env("GEMINI_API_KEY"), "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise RetryableError(f"network error: {e}") from e
    if r.status_code == 429 or r.status_code >= 500:
        ra = r.headers.get("Retry-After")
        raise RetryableError(f"HTTP {r.status_code}: {r.text[:300]}", float(ra) if ra and ra.isdigit() else None)
    if r.status_code != 200:
        raise ProviderError(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def _pcm_to_wav(pcm: bytes, sr: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def tts(text: str, voice: str, style: str, model: str) -> tuple[bytes, dict]:
    """Return (wav_bytes, usage_metadata)."""
    if mock():
        return _mock_tts(text), {"promptTokenCount": len(text), "candidatesTokenCount": 0}
    part = {"text": text}
    if style:
        part["speech_metadata"] = {"style": style}
    body = {
        "contents": [{"role": "user", "parts": [part]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"voice": voice}},
        },
    }
    data = _post(model, body)
    try:
        inline = data["candidates"][0]["content"]["parts"][0]["inlineData"]
    except (KeyError, IndexError) as e:
        reason = (data.get("candidates") or [{}])[0].get("finishReason") or data.get("promptFeedback")
        raise RetryableError(f"no audio in response (reason: {reason})") from e
    audio = base64.b64decode(inline["data"])
    if not audio.startswith(b"RIFF"):
        # Older TTS models returned headerless 16-bit PCM at 24 kHz.
        audio = _pcm_to_wav(audio)
    return audio, data.get("usageMetadata", {})


def generate_text(prompt: str, model: str, json_mode: bool = False, temperature: float = 0.4) -> tuple[str, dict]:
    if mock():
        return ("{}" if json_mode else "MOCK TEXT"), {}
    cfg: dict = {"temperature": temperature}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
    data = _post(model, body)
    try:
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError) as e:
        raise RetryableError(f"no text in response: {json.dumps(data)[:300]}") from e
    return text, data.get("usageMetadata", {})


def _mock_tts(text: str) -> bytes:
    """Speech-like placeholder: syllable-shaped noise bursts, about 7 syllables per second."""
    sr = 24000
    rng = random.Random(text)
    n_syll = max(3, len([c for c in text if not c.isspace()]))
    frames = bytearray()
    for i in range(n_syll):
        dur = rng.uniform(0.11, 0.17)
        n = int(sr * dur)
        f0 = rng.uniform(140, 220)
        for k in range(n):
            env_ = math.sin(math.pi * k / n)
            s = 0.25 * env_ * math.sin(2 * math.pi * f0 * k / sr) + 0.03 * env_ * rng.uniform(-1, 1)
            frames += int(max(-1, min(1, s)) * 32767).to_bytes(2, "little", signed=True)
        if text[min(i, len(text) - 1)] in "።፣,.":
            frames += b"\x00\x00" * int(sr * 0.25)
    return _pcm_to_wav(bytes(frames), sr)
