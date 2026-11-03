"""Prey types, drawn with simple shapes (top down view, facing right).

Every prey type is a ``PreyKind``: its size, speed, motion style, preferred
sounds and a ``draw(pen, anim)`` function. Coordinates inside ``draw`` are in
body lengths: +x is forward, +y is the prey's right side, (0, 0) is the body
centre. ``Pen`` handles rotation, scaling and placement on the frame.

Colours follow cat vision: cats see blues and yellows best, so prey is mostly
yellow, cream and blue, which pops against the dark backgrounds.

To add a new prey type: write a ``draw_xxx`` function, create a ``PreyKind``
and add it to ``PREY_KINDS``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from PIL import ImageDraw


@dataclass
class Anim:
    """Animation inputs for one frame of one prey."""

    t: float = 0.0          # seconds since start
    phase: float = 0.0      # gait phase in radians, advances with movement
    twitch: float = 0.0     # 0..1, how strongly it is twitching right now
    moving: float = 0.0     # 0..1, current speed relative to cruising speed
    flap: float = 0.0       # 0..1, wing spread (birds in flight)
    seed: float = 0.0       # per prey random offset so they don't sync up


class Pen:
    """Draws shapes in prey local coordinates onto a Pillow RGBA image."""

    def __init__(self, draw: ImageDraw.ImageDraw, ox: float, oy: float, angle: float, scale: float):
        self.d = draw
        self.ox, self.oy = ox, oy
        self.c, self.s = math.cos(angle), math.sin(angle)
        self.k = scale  # pixels per body length

    def pt(self, x, y):
        k = self.k
        return (self.ox + (x * self.c - y * self.s) * k, self.oy + (x * self.s + y * self.c) * k)

    def ellipse(self, cx, cy, rx, ry, fill, rot=0.0, n=22, outline=None):
        cr, sr = math.cos(rot), math.sin(rot)
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = math.cos(a) * rx, math.sin(a) * ry
            pts.append(self.pt(cx + x * cr - y * sr, cy + x * sr + y * cr))
        self.d.polygon(pts, fill=fill, outline=outline)

    def circle(self, cx, cy, r, fill):
        x, y = self.pt(cx, cy)
        rr = r * self.k
        self.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=fill)

    def poly(self, points, fill, outline=None):
        self.d.polygon([self.pt(x, y) for x, y in points], fill=fill, outline=outline)

    def line(self, points, fill, width):
        self.d.line([self.pt(x, y) for x, y in points], fill=fill, width=max(1, int(round(width * self.k))),
                    joint="curve")


SHADOW = (0, 0, 0, 70)


# ----------------------------------------------------------------------------
# Drawers
# ----------------------------------------------------------------------------

def draw_bug(p: Pen, a: Anim):
    p.ellipse(0.04, 0.05, 0.56, 0.36, SHADOW)
    leg_col = (35, 45, 80, 255)
    for i, lx in enumerate((0.18, 0.0, -0.18)):
        for side in (-1, 1):
            # tripod gait: legs alternate with phase, plus twitch jitter
            sw = math.sin(a.phase + (i + (side > 0)) * math.pi) * 0.12
            sw += a.twitch * 0.08 * math.sin(a.t * 40 + i * 2 + side)
            knee = (lx + sw * 0.5, side * 0.32)
            foot = (lx + 0.08 * (1 - i) + sw, side * 0.5)
            p.line([(lx, side * 0.12), knee, foot], leg_col, 0.035)
    ant = 0.10 * math.sin(a.t * 3 + a.seed) + a.twitch * 0.25 * math.sin(a.t * 30)
    for side in (-1, 1):
        p.line([(0.42, side * 0.05), (0.62, side * (0.14 + ant)), (0.72, side * (0.22 + ant * 1.4))], leg_col, 0.025)
    p.ellipse(-0.05, 0, 0.4, 0.27, (240, 205, 55, 255))               # shell
    p.line([(0.25, 0), (-0.43, 0)], (40, 60, 120, 255), 0.03)          # wing seam
    for sx, sy in ((-0.05, 0.13), (-0.05, -0.13), (-0.25, 0.1), (-0.25, -0.1), (0.1, 0.12), (0.1, -0.12)):
        p.circle(sx, sy, 0.045, (45, 75, 170, 255))
    p.ellipse(0.36, 0, 0.12, 0.17, (45, 75, 170, 255))                # head
    p.circle(0.43, 0.08, 0.025, (250, 250, 240, 255))
    p.circle(0.43, -0.08, 0.025, (250, 250, 240, 255))


def draw_mouse(p: Pen, a: Anim):
    # tail: long wavy line, waves faster when moving, flicks when twitching
    amp = 0.06 + 0.06 * a.moving + 0.15 * a.twitch
    pts = []
    for i in range(14):
        u = i / 13
        x = -0.42 - u * 0.75
        y = amp * math.sin(u * 5 - a.t * (3 + 6 * a.moving) - a.seed) * u
        pts.append((x, y))
    p.ellipse(0.0, 0.05, 0.52, 0.25, SHADOW)
    p.line(pts, (205, 180, 140, 255), 0.035)
    bob = 0.02 * math.sin(a.phase * 2) * a.moving
    p.ellipse(-0.08, bob, 0.4, 0.21, (175, 170, 160, 255))           # body (soft grey)
    p.ellipse(-0.05, bob, 0.3, 0.14, (200, 195, 180, 255))           # lighter back
    # feet peek out when running
    for side in (-1, 1):
        f = math.sin(a.phase + (side > 0) * math.pi) * 0.08 * a.moving
        p.ellipse(0.12 + f, side * 0.18, 0.04, 0.025, (200, 175, 150, 255))
        p.ellipse(-0.3 - f, side * 0.18, 0.05, 0.03, (200, 175, 150, 255))
    head_turn = 0.25 * a.twitch * math.sin(a.t * 18 + a.seed)
    hx = 0.32
    p.poly([(hx - 0.05, -0.15), (hx + 0.27, -0.02 + head_turn * 0.3), (hx + 0.27, 0.02 + head_turn * 0.3),
            (hx - 0.05, 0.15)], (185, 178, 165, 255))
    p.ellipse(hx + 0.02, 0, 0.13, 0.14, (185, 178, 165, 255))
    for side in (-1, 1):
        p.ellipse(hx - 0.04, side * 0.15, 0.08, 0.075, (150, 145, 140, 255))   # ears
        p.ellipse(hx - 0.035, side * 0.15, 0.05, 0.045, (235, 205, 165, 255))
        p.circle(hx + 0.12, side * 0.065, 0.028, (20, 20, 30, 255))            # eyes
    nose = (hx + 0.29, head_turn * 0.3)
    p.circle(nose[0], nose[1], 0.025, (240, 190, 170, 255))
    wh = 0.04 * math.sin(a.t * 25 + a.seed) * (0.3 + a.twitch)
    for side in (-1, 1):
        for k in (0.08, 0.16):
            p.line([(nose[0] - 0.03, nose[1] + side * 0.03), (nose[0] + 0.05, nose[1] + side * (0.17 + k + wh))],
                   (230, 230, 210, 200), 0.008)


def draw_bird(p: Pen, a: Anim):
    p.ellipse(0.0, 0.07, 0.42, 0.24, SHADOW)
    blue, light, dark = (60, 115, 215, 255), (130, 175, 240, 255), (30, 60, 140, 255)
    # tail
    fan = 0.06 + 0.05 * a.twitch * abs(math.sin(a.t * 20))
    p.poly([(-0.25, -0.06), (-0.62, -0.1 - fan), (-0.62, 0.1 + fan), (-0.25, 0.06)], dark)
    # wings: folded along the body, spread when flapping
    spread = a.flap * (0.5 + 0.5 * math.sin(a.t * 28))
    for side in (-1, 1):
        if spread > 0.05:
            tip_y = side * (0.2 + 0.55 * spread)
            p.poly([(0.12, side * 0.1), (-0.05, tip_y), (-0.3, tip_y * 0.8), (-0.2, side * 0.1)], light)
        else:
            flick = a.twitch * 0.05 * math.sin(a.t * 30)
            p.ellipse(-0.08, side * (0.12 + flick), 0.26, 0.08, light, rot=side * 0.15)
    p.ellipse(0.0, 0, 0.3, 0.19, blue)                                  # body
    head_turn = 0.3 * a.twitch * math.sin(a.t * 12 + a.seed) + 0.15 * math.sin(a.t * 1.3 + a.seed)
    hx, hy = 0.28, head_turn * 0.1
    p.circle(hx, hy, 0.13, dark)                                         # head
    bx = math.cos(head_turn)
    by = math.sin(head_turn)
    p.poly([(hx + 0.1 * bx - 0.04 * by, hy + 0.1 * by + 0.04 * bx),
            (hx + 0.27 * bx, hy + 0.27 * by),
            (hx + 0.1 * bx + 0.04 * by, hy + 0.1 * by - 0.04 * bx)], (250, 205, 45, 255))  # beak
    for side in (-1, 1):
        p.circle(hx + 0.05, hy + side * 0.08, 0.025, (250, 240, 200, 255))
    p.ellipse(0.02, 0, 0.12, 0.07, (250, 215, 80, 255))                  # yellow chest patch


def draw_fish(p: Pen, a: Anim):
    swim = 0.04 + 0.06 * a.moving + 0.05 * a.twitch
    freq = 2.5 + 7 * a.moving + 8 * a.twitch
    n = 12
    spine = []
    for i in range(n + 1):
        u = i / n                       # 0 = nose, 1 = tail root
        x = 0.5 - u * 0.85
        y = swim * u * u * math.sin(a.t * freq - u * 3 + a.seed)
        w = 0.17 * math.sin(math.pi * min(1.0, 0.12 + u * 0.95)) + 0.02
        spine.append((x, y, w))
    top = [(x, y - w) for x, y, w in spine]
    bot = [(x, y + w) for x, y, w in reversed(spine)]
    tx, ty, _ = spine[-1]
    tail_sw = swim * 2.2 * math.sin(a.t * freq - 3.4 + a.seed)
    p.poly([(x + 0.03, y + 0.05) for x, y in top + bot], SHADOW)
    p.poly([(tx + 0.02, ty), (tx - 0.25, ty - 0.17 + tail_sw), (tx - 0.18, ty + tail_sw),
            (tx - 0.25, ty + 0.17 + tail_sw)], (80, 130, 230, 255))               # tail fin
    for side in (-1, 1):                                                           # pectoral fins
        fl = 0.04 * math.sin(a.t * (6 + 10 * a.twitch) + side)
        p.ellipse(0.15, side * (0.2 + fl), 0.09, 0.04, (80, 130, 230, 230), rot=side * 0.6)
    p.poly(top + bot, (245, 195, 45, 255))                                         # body
    for i, (x, y, w) in enumerate(spine[2:-2:2]):
        p.ellipse(x, y + (0.04 if i % 2 else -0.05), 0.06, 0.045, (55, 95, 200, 255))  # blue spots
    p.circle(spine[1][0], spine[1][1] - 0.08, 0.03, (20, 20, 40, 255))
    p.circle(spine[1][0], spine[1][1] + 0.08, 0.03, (20, 20, 40, 255))


def draw_feather(p: Pen, a: Anim):
    bend = 0.08 * math.sin(a.t * 2 + a.seed) + 0.15 * a.twitch * math.sin(a.t * 25)
    n = 12
    shaft = []
    for i in range(n + 1):
        u = i / n
        x = 0.5 - u
        y = bend * math.sin(u * math.pi) + 0.05 * u * u
        shaft.append((x, y))
    p.ellipse(0.0, 0.08, 0.5, 0.12, SHADOW)
    left, right = [], []
    for i, (x, y) in enumerate(shaft):
        u = i / n
        w = 0.17 * math.sin(math.pi * min(1, u * 1.1 + 0.05)) * (1 - 0.6 * u * u)
        left.append((x - 0.03, y - w))
        right.append((x - 0.03, y + w))
    p.poly(left + list(reversed(right)), (245, 225, 120, 255))
    # blue tip band
    tip = [pt for pt in left[:4]] + list(reversed(right[:4]))
    p.poly(tip, (70, 120, 225, 255))
    for i in range(1, n, 1):      # barbs
        x, y = shaft[i]
        p.line([(x, y), left[i]], (205, 180, 80, 255), 0.01)
        p.line([(x, y), right[i]], (205, 180, 80, 255), 0.01)
    p.line(shaft + [(-0.65, 0.07)], (250, 245, 225, 255), 0.022)


def draw_laser(p: Pen, a: Anim):
    flick = 1.0 + 0.08 * math.sin(a.t * 37 + a.seed) + 0.1 * a.twitch
    p.circle(0, 0, 1.0 * flick, (170, 255, 90, 45))
    p.circle(0, 0, 0.7 * flick, (190, 255, 110, 90))
    p.circle(0, 0, 0.45 * flick, (215, 255, 140, 200))
    p.circle(0, 0, 0.28, (250, 255, 230, 255))


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class PreyKind:
    name: str
    draw: Callable[[Pen, Anim], None]
    length: float          # body length as a fraction of the frame height
    speed: float           # cruising speed in frame heights per second
    style: str             # walk, hop, swim, drift, laser
    extent: float = 0.8    # drawing radius in body lengths (for clipping boxes)
    sounds: tuple = field(default=("Rustling",))
    shadow: bool = True


PREY_KINDS = {
    "Bugs": PreyKind("Bugs", draw_bug, 0.06, 0.10, "walk", 0.85, ("Scratching", "Rustling")),
    "Mice": PreyKind("Mice", draw_mouse, 0.10, 0.22, "walk", 1.25, ("Mouse squeaks", "Scratching", "Rustling")),
    "Birds": PreyKind("Birds", draw_bird, 0.09, 0.13, "hop", 0.95, ("Bird chirps", "Rustling")),
    "Fish": PreyKind("Fish", draw_fish, 0.12, 0.14, "swim", 0.85, ("Rustling",)),
    "Feathers": PreyKind("Feathers", draw_feather, 0.13, 0.09, "drift", 0.8, ("Rustling",)),
    "Laser dot": PreyKind("Laser dot", draw_laser, 0.022, 0.35, "laser", 1.15, ("Scratching", "Rustling")),
}
MIXED = "Mixed"
PREY_NAMES = list(PREY_KINDS) + [MIXED]
