"""Backgrounds, drawn once per video with code (no image files).

To add a new background, write a function ``make_xxx(w, h, rng, color)`` that
returns an RGB ``PIL.Image`` of size (w, h) and add it to ``BACKGROUNDS``.
Keep backgrounds fairly dark so blue and yellow prey stand out for cats.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CUSTOM_COLOR = "Custom color"


def _vignette(img: Image.Image, strength: float = 0.35) -> Image.Image:
    """Darken the edges a little, which keeps attention in the middle."""
    w, h = img.size
    y, x = np.ogrid[0:h, 0:w]
    d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
    mask = 1.0 - strength * np.clip(d, 0, 1) ** 2
    arr = np.asarray(img, dtype=np.float32) * mask[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def _noise_texture(w, h, rng, scale, amount):
    """Soft low frequency noise in [-amount, amount], used for subtle texture."""
    sw, sh = max(2, w // scale), max(2, h // scale)
    small = rng.uniform(-1, 1, (sh, sw)).astype(np.float32)
    img = Image.fromarray(((small + 1) * 127.5).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return (np.asarray(img, dtype=np.float32) / 127.5 - 1.0) * amount


def _solid(w, h, rgb, rng, texture=6.0):
    base = np.empty((h, w, 3), dtype=np.float32)
    base[:] = rgb
    base += _noise_texture(w, h, rng, 60, texture)[..., None]
    return Image.fromarray(base.clip(0, 255).astype(np.uint8))


def make_dark_solid(w, h, rng, color=None):
    return _vignette(_solid(w, h, (24, 27, 38), rng))


def make_custom(w, h, rng, color=None):
    return _vignette(_solid(w, h, color or (27, 31, 46), rng, texture=3.0), 0.25)


def make_grass(w, h, rng, color=None):
    img = _solid(w, h, (22, 40, 22), rng, texture=10)
    d = ImageDraw.Draw(img)
    s = h / 1080
    n = int(9000 * (w * h) / (1920 * 1080))
    xs = rng.uniform(0, w, n)
    ys = rng.uniform(0, h + 40 * s, n)
    for x, y in zip(xs, ys):
        length = rng.uniform(18, 55) * s
        lean = rng.uniform(-0.6, 0.6)
        g = int(rng.uniform(45, 95))
        col = (int(g * 0.45), g, int(g * 0.35))
        x2 = x + lean * length
        y2 = y - length
        d.line([(x, y), ((x + x2) / 2 + lean * 3 * s, (y + y2) / 2), (x2, y2)], fill=col, width=max(1, int(2 * s)))
    img = img.filter(ImageFilter.GaussianBlur(0.6 * s))
    return _vignette(img, 0.45)


def make_wood_floor(w, h, rng, color=None):
    arr = np.zeros((h, w, 3), dtype=np.float32)
    plank_h = int(h / 7.5)
    y = 0
    row = 0
    while y < h:
        y2 = min(h, y + plank_h)
        offset = rng.uniform(0, w)
        seam_x = []
        x = -offset
        while x < w:
            plank_len = rng.uniform(0.35, 0.7) * w
            tone = rng.uniform(0.75, 1.15)
            base = np.array([62, 40, 24], dtype=np.float32) * tone
            x0, x1 = int(max(0, x)), int(min(w, x + plank_len))
            if x1 > x0:
                arr[y:y2, x0:x1] = base
                # wood grain: horizontal streaks
                rows = np.arange(y, y2)
                freq = rng.uniform(0.15, 0.35)
                phase = rng.uniform(0, 6.28)
                grain = (np.sin(rows * freq + phase) * 5 + np.sin(rows * freq * 3.1 + phase) * 3)
                arr[y:y2, x0:x1] += grain[:, None, None]
            seam_x.append(int(x + plank_len))
            x += plank_len
        arr[y:y + max(2, plank_h // 30)] *= 0.45  # gap between rows
        for sx in seam_x:
            if 0 <= sx < w:
                arr[y:y2, sx:sx + max(2, plank_h // 40)] *= 0.5
        y = y2
        row += 1
    arr += _noise_texture(w, h, rng, 8, 4)[..., None]
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7))
    return _vignette(img, 0.4)


def make_water(w, h, rng, color=None):
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    arr = np.zeros((h, w, 3), dtype=np.float32)
    arr[..., 0] = 8 + 6 * yy
    arr[..., 1] = 26 + 14 * yy
    arr[..., 2] = 48 + 22 * yy
    arr += _noise_texture(w, h, rng, 90, 7)[..., None] * np.array([0.4, 0.8, 1.2])
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    s = h / 1080
    # caustic like light ripples
    for _ in range(int(260 * w / 1920)):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        rx = rng.uniform(30, 140) * s
        ry = rx * rng.uniform(0.25, 0.5)
        a = int(rng.uniform(10, 28))
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=(120, 170, 220, a), width=max(1, int(2 * s)))
    # a few pebbles on the bottom
    for _ in range(int(60 * w / 1920)):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(4, 14) * s
        t = int(rng.uniform(25, 45))
        d.ellipse([cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], fill=(t, t + 8, t + 16, 160))
    layer = layer.filter(ImageFilter.GaussianBlur(1.5 * s))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return _vignette(img, 0.4)


def make_night_sky(w, h, rng, color=None):
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    arr = np.zeros((h, w, 3), dtype=np.float32)
    arr[..., 0] = 6 + 10 * yy
    arr[..., 1] = 8 + 12 * yy
    arr[..., 2] = 22 + 26 * yy
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    s = h / 1080
    for _ in range(int(700 * w / 1920)):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.choice([0.6, 0.8, 1.0, 1.4, 2.0], p=[0.35, 0.3, 0.2, 0.1, 0.05]) * s
        b = int(rng.uniform(90, 230))
        col = (b, b, min(255, b + 25)) if rng.random() < 0.7 else (min(255, b + 20), min(255, b + 15), b - 30)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    # moon glow in a corner
    mx, my, mr = w * 0.86, h * 0.16, 55 * s
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([mx - mr * 2.2, my - mr * 2.2, mx + mr * 2.2, my + mr * 2.2], fill=50)
    glow = glow.filter(ImageFilter.GaussianBlur(mr))
    img = Image.composite(Image.new("RGB", (w, h), (90, 100, 140)), img, glow)
    ImageDraw.Draw(img).ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(215, 212, 180))
    return _vignette(img, 0.3)


def make_black(w, h, rng, color=None):
    """Pure black. Best for projectors: black means no light, so only the prey shows up on the floor."""
    return Image.new("RGB", (w, h), (0, 0, 0))


# name -> function(w, h, rng, color) -> PIL RGB image
BACKGROUNDS = {
    "Dark solid": make_dark_solid,
    "Black (projector)": make_black,
    "Grass": make_grass,
    "Wooden floor": make_wood_floor,
    "Water": make_water,
    "Night sky": make_night_sky,
    CUSTOM_COLOR: make_custom,
}
BACKGROUND_NAMES = list(BACKGROUNDS)


def make_background(name: str, w: int, h: int, rng: np.random.Generator, color=None) -> Image.Image:
    fn = BACKGROUNDS.get(name, make_dark_solid)
    img = fn(w, h, rng, color)
    return img.convert("RGB")
