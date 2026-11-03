"""Hiding objects (grass tufts, leaf piles, rocks) that prey can hide behind.

Each cover function draws onto an RGBA layer centred at (cx, cy) with a
radius ``r`` in pixels. Prey within roughly ``0.55 * r`` of the centre is
fully hidden, and peeks out near the edge.

To add a new cover type, write ``draw_xxx(draw, cx, cy, r, rng)`` and add it
to ``COVERS``.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import ImageDraw


def _blob(cx, cy, rx, ry, rng, n=18, rough=0.18, rot=0.0):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + rng.uniform(-rough, rough)
        x, y = math.cos(a) * rx * k, math.sin(a) * ry * k
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
    return pts


def draw_grass_tuft(d: ImageDraw.ImageDraw, cx, cy, r, rng):
    # dense base so prey is fully covered
    d.polygon(_blob(cx, cy + r * 0.15, r * 0.95, r * 0.7, rng, rough=0.12), fill=(20, 48, 20, 255))
    for _ in range(int(150 + r)):
        a = rng.uniform(-math.pi, 0)  # blades point mostly upwards
        bx = cx + rng.normal(0, r * 0.35)
        by = cy + r * 0.45 + rng.normal(0, r * 0.12)
        length = r * rng.uniform(0.6, 1.25)
        tip = (bx + math.cos(a) * length * 0.6, by + math.sin(a) * length)
        mid = ((bx + tip[0]) / 2 + rng.uniform(-4, 4), (by + tip[1]) / 2)
        g = int(rng.uniform(60, 140))
        d.line([(bx, by), mid, tip], fill=(int(g * 0.5), g, int(g * 0.3), 255), width=max(2, int(r / 28)))


def draw_leaf_pile(d: ImageDraw.ImageDraw, cx, cy, r, rng):
    d.polygon(_blob(cx, cy, r * 0.85, r * 0.7, rng, rough=0.1), fill=(52, 38, 18, 255))
    for _ in range(26):
        lx = cx + rng.normal(0, r * 0.32)
        ly = cy + rng.normal(0, r * 0.26)
        size = r * rng.uniform(0.28, 0.45)
        rot = rng.uniform(0, math.pi)
        tone = rng.uniform(0.7, 1.2)
        col = rng.choice([(150, 105, 35), (120, 80, 30), (165, 130, 50), (95, 70, 30)])
        col = tuple(int(min(255, c * tone)) for c in col) + (255,)
        pts = []
        for i in range(16):
            a = 2 * math.pi * i / 16
            x = math.cos(a) * size
            y = math.sin(a) * size * 0.42 * (1 - 0.3 * math.cos(a))
            pts.append((lx + x * math.cos(rot) - y * math.sin(rot), ly + x * math.sin(rot) + y * math.cos(rot)))
        d.polygon(pts, fill=col, outline=(60, 40, 15, 255))
        vx, vy = math.cos(rot) * size, math.sin(rot) * size
        d.line([(lx - vx, ly - vy), (lx + vx, ly + vy)], fill=(70, 48, 18, 255), width=max(1, int(r / 60)))


def draw_rock(d: ImageDraw.ImageDraw, cx, cy, r, rng):
    rot = rng.uniform(0, math.pi)
    base = int(rng.uniform(70, 95))
    d.polygon(_blob(cx + r * 0.06, cy + r * 0.1, r * 0.95, r * 0.75, rng, n=11, rough=0.08, rot=rot),
              fill=(10, 10, 12, 140))  # shadow
    d.polygon(_blob(cx, cy, r * 0.9, r * 0.72, rng, n=11, rough=0.1, rot=rot),
              fill=(base, base, base + 6, 255))
    # lighter top facet and a few cracks
    d.polygon(_blob(cx - r * 0.18, cy - r * 0.18, r * 0.5, r * 0.36, rng, n=9, rough=0.15, rot=rot),
              fill=(base + 25, base + 25, base + 32, 255))
    for _ in range(3):
        x0, y0 = cx + rng.uniform(-r * 0.4, r * 0.4), cy + rng.uniform(-r * 0.3, r * 0.3)
        d.line([(x0, y0), (x0 + rng.uniform(-r * 0.3, r * 0.3), y0 + rng.uniform(-r * 0.2, r * 0.2))],
               fill=(base - 30, base - 30, base - 25, 255), width=max(1, int(r / 50)))


COVERS = {
    "Grass": draw_grass_tuft,
    "Leaves": draw_leaf_pile,
    "Rocks": draw_rock,
}
MIXED = "Mixed"
COVER_NAMES = list(COVERS) + [MIXED]


def place_covers(count: int, aspect: float, radius: float, rng: np.random.Generator):
    """Choose non overlapping cover centres in normalised units (height = 1)."""
    spots = []
    margin = radius * 1.3
    attempts = 0
    while len(spots) < count and attempts < 2000:
        attempts += 1
        x = rng.uniform(margin, aspect - margin)
        y = rng.uniform(margin, 1 - margin)
        if all(math.hypot(x - sx, y - sy) > radius * 3.0 for sx, sy in spots):
            spots.append((x, y))
    return spots


def cover_drawer(kind: str, rng: np.random.Generator):
    if kind in COVERS:
        return COVERS[kind]
    return COVERS[rng.choice(list(COVERS))]
