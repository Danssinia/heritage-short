"""Cloudflare Workers AI image generation (FLUX.2 klein or FLUX.1 schnell).

FLUX.2 models take multipart form data (prompt, width, height, seed, guidance and
up to four reference images input_image_0..3, each under 512x512).
FLUX.1 schnell takes JSON (prompt, steps, seed). Both return a base64 image.
"""
from __future__ import annotations

import base64
import io

import requests
from PIL import Image, ImageDraw, ImageOps

from ..config import env, mock
from ..retry import ProviderError, RetryableError

TIMEOUT = 180


def _ref_png(data: bytes, max_side: int = 496) -> bytes:
    """Downscale a reference image so both sides are under 512 px, as FLUX.2 klein requires."""
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def generate_image(
    model: str,
    prompt: str,
    width: int,
    height: int,
    seed: int,
    refs: list[bytes] | None = None,
    steps: int | None = None,
    guidance: float | None = None,
) -> bytes:
    """Return PNG/JPEG bytes."""
    refs = refs or []
    if mock():
        return _mock_image(prompt, width, height, seed, len(refs))
    account = env("CF_ACCOUNT_ID")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {env('CF_API_TOKEN')}"}
    try:
        if "flux-2" in model:
            fields = {"prompt": (None, prompt), "width": (None, str(width)), "height": (None, str(height)), "seed": (None, str(seed))}
            if guidance is not None:
                fields["guidance"] = (None, str(guidance))
            for i, ref in enumerate(refs[:4]):
                fields[f"input_image_{i}"] = (f"ref{i}.png", _ref_png(ref), "image/png")
            r = requests.post(url, headers=headers, files=fields, timeout=TIMEOUT)
        else:
            body = {"prompt": prompt, "seed": seed}
            if steps is not None:
                body["steps"] = steps
            r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise RetryableError(f"network error: {e}") from e

    if r.status_code == 429 or r.status_code >= 500:
        raise RetryableError(f"HTTP {r.status_code}: {r.text[:300]}")
    if r.status_code != 200:
        raise ProviderError(f"HTTP {r.status_code}: {r.text[:500]}")
    if r.headers.get("content-type", "").startswith("image/"):
        return r.content
    payload = r.json()
    image = (payload.get("result") or {}).get("image")
    if not image:
        raise RetryableError(f"no image in response: {str(payload)[:300]}")
    return base64.b64decode(image)


def _mock_image(prompt: str, width: int, height: int, seed: int, n_refs: int) -> bytes:
    hue = seed % 360
    im = Image.new("HSV", (width, height), (int(hue / 360 * 255), 90, 200)).convert("RGB")
    d = ImageDraw.Draw(im)
    d.ellipse([width * 0.35, height * 0.2, width * 0.65, height * 0.8], outline=(255, 255, 255), width=6)
    words, line, lines = prompt.split()[:40], "", []
    for w in words:
        if len(line) + len(w) > 60:
            lines.append(line)
            line = ""
        line += w + " "
    lines.append(line)
    d.multiline_text((20, 20), f"MOCK seed={seed} refs={n_refs}\n" + "\n".join(lines[:6]), fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
