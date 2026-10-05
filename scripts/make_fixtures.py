"""Generate deterministic synthetic fundus fixtures for tests.

These images are drawn from scratch. They contain no pixels from APTOS, IDRiD, DRIVE or
Messidor-2, whose licences forbid redistribution.

Usage: python scripts/make_fixtures.py [--out tests/fixtures]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
SEED = 26038
CENTRE = SIZE / 2
FOV_RADIUS = 470
DISC_CENTRE = (CENTRE + 210, CENTRE - 20)
DISC_RADIUS = 60
FOVEA_CENTRE = (CENTRE - 60, CENTRE + 10)


def _fov_mask() -> np.ndarray:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    return (xx - CENTRE) ** 2 + (yy - CENTRE) ** 2 <= FOV_RADIUS**2


def _background() -> np.ndarray:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    r = np.sqrt((xx - CENTRE) ** 2 + (yy - CENTRE) ** 2) / FOV_RADIUS
    falloff = np.clip(1.0 - 0.45 * r**2, 0.0, 1.0)
    fovea = np.exp(-((xx - FOVEA_CENTRE[0]) ** 2 + (yy - FOVEA_CENTRE[1]) ** 2) / (2 * 45.0**2))
    rgb = np.empty((SIZE, SIZE, 3), dtype=np.float64)
    rgb[..., 0] = 205 * falloff - 40 * fovea
    rgb[..., 1] = 92 * falloff - 25 * fovea
    rgb[..., 2] = 38 * falloff - 10 * fovea
    return rgb


def _branch(
    draw: ImageDraw.ImageDraw,
    rng: np.random.Generator,
    x: float,
    y: float,
    angle: float,
    length: float,
    width: float,
    depth: int,
) -> None:
    if depth == 0 or width < 1:
        return
    steps = 12
    for _ in range(steps):
        angle += rng.normal(0.0, 0.08)
        nx = x + math.cos(angle) * length / steps
        ny = y + math.sin(angle) * length / steps
        draw.line([(x, y), (nx, ny)], fill=(110, 28, 18), width=max(1, round(width)))
        x, y = nx, ny
    for turn in (-0.45, 0.45):
        _branch(
            draw, rng, x, y, angle + turn + rng.normal(0, 0.1), length * 0.7, width * 0.7, depth - 1
        )


def _vessels(img: Image.Image, rng: np.random.Generator) -> None:
    draw = ImageDraw.Draw(img)
    dx, dy = DISC_CENTRE
    temporal = (math.pi - 0.75, math.pi + 0.75, math.pi - 1.25, math.pi + 1.25)
    nasal = (-0.5, 0.5)
    for angle in temporal + nasal:
        _branch(draw, rng, dx, dy, angle, 170, 9, 4)


def _optic_disc(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    dx, dy = DISC_CENTRE
    draw.ellipse(
        [dx - DISC_RADIUS, dy - DISC_RADIUS, dx + DISC_RADIUS, dy + DISC_RADIUS],
        fill=(246, 214, 160),
    )
    cup = DISC_RADIUS * 0.4
    draw.ellipse([dx - cup, dy - cup, dx + cup, dy + cup], fill=(252, 236, 200))


def _random_point_in_fov(rng: np.random.Generator, margin: float = 60) -> tuple[float, float]:
    while True:
        r = math.sqrt(rng.uniform(0, 1)) * (FOV_RADIUS - margin)
        theta = rng.uniform(0, 2 * math.pi)
        x, y = CENTRE + r * math.cos(theta), CENTRE + r * math.sin(theta)
        if math.hypot(x - DISC_CENTRE[0], y - DISC_CENTRE[1]) > DISC_RADIUS + 30:
            return x, y


def _dots(img: Image.Image, rng: np.random.Generator, n: int, radius: tuple[float, float], fill):
    draw = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = _random_point_in_fov(rng)
        r = rng.uniform(*radius)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def _blots(img: Image.Image, rng: np.random.Generator, n: int) -> None:
    draw = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = _random_point_in_fov(rng)
        rx, ry = rng.uniform(7, 16), rng.uniform(6, 13)
        draw.ellipse([x - rx, y - ry, x + rx, y + ry], fill=(95, 16, 20))


def _exudates(img: Image.Image, rng: np.random.Generator, n: int) -> None:
    draw = ImageDraw.Draw(img)
    for _ in range(n):
        cx, cy = _random_point_in_fov(rng, margin=120)
        for _ in range(int(rng.integers(3, 7))):
            x, y = cx + rng.normal(0, 14), cy + rng.normal(0, 14)
            r = rng.uniform(3, 7)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(232, 195, 58))


def _neovascular_tuft(img: Image.Image, rng: np.random.Generator) -> None:
    draw = ImageDraw.Draw(img)
    dx, dy = DISC_CENTRE
    for _ in range(40):
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.uniform(15, 55)
        x0, y0 = dx + rng.normal(0, 20), dy + rng.normal(0, 20)
        pts = [(x0, y0)]
        for _ in range(5):
            angle += rng.normal(0, 0.9)
            x0 += math.cos(angle) * length / 5
            y0 += math.sin(angle) * length / 5
            pts.append((x0, y0))
        draw.line(pts, fill=(130, 30, 30), width=2)


def _finish(img: Image.Image) -> Image.Image:
    arr = np.asarray(img, dtype=np.float64)
    arr[~_fov_mask()] = 0
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _base(rng: np.random.Generator) -> Image.Image:
    img = Image.fromarray(np.clip(_background(), 0, 255).astype(np.uint8), "RGB")
    _vessels(img, rng)
    _optic_disc(img)
    return img


def grade0_clean() -> Image.Image:
    rng = np.random.default_rng(SEED)
    return _finish(_base(rng))


def grade2_haem() -> Image.Image:
    rng = np.random.default_rng(SEED + 2)
    img = _base(rng)
    _dots(img, rng, 18, (1.5, 3.0), (85, 14, 16))
    _blots(img, rng, 12)
    _exudates(img, rng, 4)
    return _finish(img)


def grade4_nv() -> Image.Image:
    rng = np.random.default_rng(SEED + 4)
    img = _base(rng)
    _dots(img, rng, 30, (1.5, 3.0), (85, 14, 16))
    _blots(img, rng, 25)
    _exudates(img, rng, 8)
    _neovascular_tuft(img, rng)
    return _finish(img)


def blur_s8() -> Image.Image:
    return grade0_clean().filter(ImageFilter.GaussianBlur(radius=8))


def underexposed() -> Image.Image:
    arr = np.asarray(grade0_clean(), dtype=np.float64) * 0.18
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def partial_fov() -> Image.Image:
    arr = np.asarray(grade0_clean()).copy()
    arr[:, int(SIZE * 0.55) :] = 0
    arr[: int(SIZE * 0.2), :] = 0
    return Image.fromarray(arr, "RGB")


FIXTURES = {
    "grade0_clean": grade0_clean,
    "grade2_haem": grade2_haem,
    "grade4_nv": grade4_nv,
    "blur_s8": blur_s8,
    "underexposed": underexposed,
    "partial_fov": partial_fov,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, build in FIXTURES.items():
        path = args.out / f"{name}.png"
        build().save(path, format="PNG", optimize=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
