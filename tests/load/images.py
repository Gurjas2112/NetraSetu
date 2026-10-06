"""Perturb a fixture PNG so each Locust request misses the inference cache."""

from __future__ import annotations

import io

from PIL import Image


def unique_png(base: bytes, nonce: int) -> bytes:
    """Change one pixel so sha256 (and the cache key) is unique without a new capture."""
    image = Image.open(io.BytesIO(base)).convert("RGB")
    pixels = image.load()
    x = nonce % image.size[0]
    r, g, b = pixels[x, 0]
    pixels[x, 0] = ((r + 1) % 256, g, b)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()
