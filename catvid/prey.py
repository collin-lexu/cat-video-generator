"""Prey types, drawn with simple shapes (top down view, facing right).

Side view prey (the grasshopper) are drawn in profile instead: +x is forward,
+y is down on screen, and their feet stand on the line ``y = kind.ground``.

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
    leg: float = 0.0        # 0..1, jumping legs folded (0) or kicked straight out (1)
    crouch: float = 0.0     # 0..1, body pressed down before a jump or after landing
    air: float = 0.0        # 0..1, how airborne it is (legs dangle, antennae sweep back)


class Pen:
    """Draws shapes in prey local coordinates onto a Pillow RGBA image."""

    def __init__(self, draw: ImageDraw.ImageDraw, ox: float, oy: float, angle: float, scale: float,
                 flip: bool = False):
        self.d = draw
        self.ox, self.oy = ox, oy
        self.c, self.s = math.cos(angle), math.sin(angle)
        self.k = scale  # pixels per body length
        self.fx = -1.0 if flip else 1.0  # mirror left/right (side view prey facing left)

    def pt(self, x, y):
        k = self.k
        return (self.ox + self.fx * (x * self.c - y * self.s) * k, self.oy + (x * self.s + y * self.c) * k)

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


# Grasshopper (side view) ------------------------------------------------------

GH_GROUND = 0.2   # feet stand on y = 0.2 (body centre is 0, 0)


def _lerp(a, b, u):
    return a + (b - a) * u


def _seg(p0, ang, length):
    return (p0[0] + math.cos(ang) * length, p0[1] + math.sin(ang) * length)


def _shade(col, f, alpha=255):
    return (int(min(255, col[0] * f)), int(min(255, col[1] * f)), int(min(255, col[2] * f)), alpha)


def _tapered(p: Pen, a, b, w0, w1, fill, bulge=0.0, n=10):
    """A limb segment from a to b, w0 wide at a and w1 at b, optionally bulging (a muscly femur)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / ln, dx / ln
    left, right = [], []
    for i in range(n + 1):
        u = i / n
        w = _lerp(w0, w1, u) + bulge * math.sin(math.pi * min(1.0, u * 1.25))
        cx, cy = a[0] + dx * u, a[1] + dy * u
        left.append((cx + nx * w, cy + ny * w))
        right.append((cx - nx * w * 0.8, cy - ny * w * 0.8))
    p.poly(left + right[::-1], fill)
    return left, right


def _hind_leg(p: Pen, a: Anim, hip, far: bool):
    """The big jumping leg: muscly femur with a herringbone pattern, spiny tibia, foot."""
    dim = 0.62 if far else 1.0
    green = (96, 158, 52)
    leg = a.leg
    # folded: femur angled up and back, tibia tucked under it reaching the ground
    f_ang = _lerp(math.radians(195), math.radians(168), leg)
    knee = _seg(hip, f_ang, 0.46)
    if leg < 0.02:
        # put the foot on the ground under the knee, tibia tucked forward
        dy = (GH_GROUND + 0.005) - knee[1]
        dy = max(-0.4, min(0.4, dy))
        t_ang = math.atan2(dy, math.sqrt(max(1e-6, 0.42 ** 2 - dy * dy)))
    else:
        dy = (GH_GROUND + 0.005) - knee[1]
        dy = max(-0.4, min(0.4, dy))
        rest = math.atan2(dy, math.sqrt(max(1e-6, 0.42 ** 2 - dy * dy)))
        t_ang = _lerp(rest, math.radians(152), leg)
    t_ang += (0.08 if far else 0.0) * a.air
    foot = _seg(knee, t_ang, 0.42)
    tar_ang = _lerp(0.0, t_ang + 0.35, min(1.0, leg * 1.4))
    toe = _seg(foot, tar_ang, 0.11)
    tib_col = _shade((120, 150, 60), dim)
    # tibia with little spines on its back edge
    p.line([knee, foot], tib_col, 0.026)
    for i in range(1, 8):
        u = i / 8
        sx, sy = _lerp(knee[0], foot[0], u), _lerp(knee[1], foot[1], u)
        sa = t_ang + math.pi / 2 + 0.5
        p.line([(sx, sy), _seg((sx, sy), sa, 0.03)], _shade((70, 60, 40), dim), 0.008)
    p.line([foot, toe], _shade((105, 120, 55), dim), 0.02)
    p.circle(toe[0], toe[1], 0.012, _shade((70, 60, 40), dim))
    # femur: thick near the hip, bulging muscle, slim at the knee
    _tapered(p, (hip[0] + 0.004, hip[1] + 0.008), (knee[0] + 0.004, knee[1] + 0.008), 0.064, 0.025,
             _shade((40, 70, 22), dim), bulge=0.052)                                       # dark rim
    left, right = _tapered(p, hip, knee, 0.06, 0.022, _shade((104, 166, 56), dim), bulge=0.05)
    _tapered(p, hip, knee, -0.02, -0.035, _shade((170, 196, 96), dim), bulge=-0.015)         # pale underside
    _tapered(p, hip, knee, 0.032, 0.012, _shade((132, 190, 78), dim), bulge=0.028)   # sheen on the top side
    # herringbone chevrons
    n = len(left)
    for i in range(2, n - 2):
        mx, my = _lerp(hip[0], knee[0], i / (n - 1)), _lerp(hip[1], knee[1], i / (n - 1))
        p.line([left[i], (mx, my), right[i]], _shade((62, 108, 34), dim, 200), 0.008)
    # dark knee crescent
    p.circle(knee[0], knee[1], 0.026, _shade((40, 52, 26), dim))


def _small_leg(p: Pen, a: Anim, hip, reach, far: bool, phase: float):
    """Front and middle legs: femur forward/down, tibia down to the ground."""
    dim = 0.62 if far else 1.0
    col = _shade((104, 160, 58), dim)
    lift = a.air
    sway = 0.03 * a.twitch * math.sin(a.t * 40 + phase)
    # when airborne the legs reach forward ready to land
    knee = (hip[0] + reach * 0.5 + 0.05 * lift + sway, hip[1] + 0.08 - 0.03 * lift)
    ground = GH_GROUND + 0.005 - 0.07 * lift
    foot = (hip[0] + reach + 0.1 * lift + sway, ground)
    toe = (foot[0] + 0.05 * (1 if reach >= 0 else -1), ground)
    p.line([hip, knee], col, 0.03)
    p.line([knee, foot], col, 0.022)
    p.line([foot, toe], _shade((90, 110, 50), dim), 0.016)


def draw_grasshopper(p: Pen, a: Anim):
    green = (92, 156, 50)
    dark = (52, 100, 30)
    light = (150, 205, 88)
    belly = (178, 196, 92)
    crouch = a.crouch * 0.06
    # the body lowers when crouching; everything below is drawn relative to that
    by = crouch

    # far side legs (behind the body, a bit darker)
    _hind_leg(p, a, (0.03, 0.04 + by), far=True)
    _small_leg(p, a, (0.15 - 0.02, 0.07 + by), 0.05, far=True, phase=1.0)
    _small_leg(p, a, (0.27 - 0.02, 0.07 + by), 0.12, far=True, phase=2.0)

    # abdomen: long, tapering, slightly upturned, with a rounded tip and segment rings
    top, bot = [], []
    n = 12
    for i in range(n + 1):
        u = i / n                      # 0 at the waist, 1 at the tip
        x = 0.12 - u * 0.6
        h = 0.088 * (1 - 0.62 * u ** 1.3) + 0.01
        cy = by + 0.012 - 0.015 * u
        top.append((x, cy - h))
        bot.append((x, cy + h * 1.05))
    tx, ty = top[-1][0], (top[-1][1] + bot[-1][1]) / 2
    tr = (bot[-1][1] - top[-1][1]) / 2
    tip = [(tx - math.sin(k * math.pi / 6) * tr * 0.9, ty - math.cos(k * math.pi / 6) * tr) for k in range(1, 6)]
    outline = top + tip + bot[::-1]
    p.poly([(x + 0.004, y + 0.006) for x, y in outline], _shade(dark, 0.7))           # dark rim
    p.poly(outline, green)
    # soft top to bottom shading: sheen on top, darker flank, yellowish belly
    p.poly([(x, y + 0.012) for x, y in top] + [(x, y + 0.045) for x, y in top[::-1]], light)
    p.poly([(x, _lerp(y, b[1], 0.55)) for (x, y), b in zip(top, bot)] +
           [(x, y - 0.03) for x, y in bot[::-1]], _shade(green, 0.85))
    p.poly([(x, y - 0.035 * (1 - 0.5 * i / n)) for i, (x, y) in enumerate(bot)] + bot[::-1], belly)
    p.line(bot, _shade(dark, 0.8), 0.01)
    for i in range(1, n):
        p.line([(top[i][0] - 0.01, top[i][1] + 0.01), (bot[i][0] + 0.012, bot[i][1])], _shade(dark, 1.0, 140), 0.007)
    # tympanum (ear) on the first segment
    p.ellipse(0.08, by + 0.0, 0.018, 0.024, (70, 110, 40, 255))

    # folded wings (tegmina) along the back, slightly lifted while airborne
    lift = 0.05 * a.air
    wing = [(0.17, by - 0.105), (-0.1, by - 0.115 - lift * 0.5), (-0.55, by - 0.075 - lift),
            (-0.62, by - 0.045 - lift), (-0.55, by - 0.02 - lift * 0.6), (-0.1, by - 0.045), (0.15, by - 0.05)]
    p.poly([(x + 0.005, y + 0.01) for x, y in wing], (40, 70, 25, 160))       # soft edge shadow
    p.poly(wing, (108, 150, 62, 240))
    for k in (0.0, 0.3, 0.6):
        p.line([(0.12, by - 0.08 + k * 0.02), (-0.2, by - 0.085 + k * 0.03 - lift * 0.3),
                (-0.56, by - 0.06 + k * 0.025 - lift)], (70, 105, 40, 200), 0.007)
    p.line([(0.16, by - 0.1), (-0.58, by - 0.065 - lift)], (165, 200, 110, 200), 0.008)   # pale leading edge

    # pronotum: the saddle shaped shield over the thorax
    pro = [(0.13, by - 0.11), (0.32, by - 0.125), (0.345, by - 0.08), (0.34, by + 0.06), (0.28, by + 0.085),
           (0.12, by + 0.07), (0.10, by - 0.02)]
    p.poly(pro, green)
    p.poly([(0.14, by - 0.105), (0.32, by - 0.12), (0.33, by - 0.09), (0.15, by - 0.075)], light)
    p.line([(0.13, by - 0.04), (0.33, by - 0.05)], (205, 220, 130, 220), 0.012)        # pale lateral keel
    p.line([(0.235, by - 0.12), (0.225, by + 0.07)], _shade(dark, 1.0, 170), 0.007)     # groove
    p.line(pro[3:6], _shade(dark, 1.0, 200), 0.01)

    # head: tall, with a sloping face, big compound eye, short antennae
    head_tilt = 0.04 * a.twitch * math.sin(a.t * 22 + a.seed)
    hy = by + head_tilt
    head = [(0.32, hy - 0.12), (0.39, hy - 0.14), (0.45, hy - 0.12), (0.5, hy - 0.05), (0.52, hy + 0.04),
            (0.5, hy + 0.11), (0.43, hy + 0.13), (0.36, hy + 0.1), (0.32, hy + 0.03)]
    p.poly(head, green)
    p.poly([(0.4, hy - 0.13), (0.45, hy - 0.115), (0.49, hy - 0.06), (0.44, hy - 0.08)], light)
    p.poly([(0.36, hy + 0.06), (0.5, hy + 0.08), (0.49, hy + 0.11), (0.43, hy + 0.125), (0.37, hy + 0.1)], belly)
    # mouthparts and palps
    palp = 0.012 * math.sin(a.t * 9 + a.seed)
    p.line([(0.48, hy + 0.11), (0.5, hy + 0.15 + palp), (0.485, hy + 0.17)], (110, 130, 60, 255), 0.012)
    p.ellipse(0.495, hy + 0.12, 0.022, 0.018, (85, 95, 45, 255))
    # compound eye
    p.ellipse(0.425, hy - 0.055, 0.038, 0.052, (125, 100, 52, 255), rot=0.3)
    p.ellipse(0.43, hy - 0.05, 0.022, 0.032, (75, 58, 30, 255), rot=0.3)
    p.circle(0.437, hy - 0.072, 0.009, (240, 240, 220, 230))
    # antennae: short and sweeping back in flight, flicking when twitching
    sweep = -0.5 * a.air + 0.12 * math.sin(a.t * 2.5 + a.seed) + 0.35 * a.twitch * math.sin(a.t * 35)
    for k, off in enumerate((0.0, 0.12)):
        base = (0.455, hy - 0.11)
        ang = math.radians(-40) + sweep * (1 + 0.3 * k) + off
        mid = _seg(base, ang, 0.16)
        tip = _seg(mid, ang - 0.25 - 0.3 * a.air, 0.17)
        col = (88, 110, 48, 255) if k == 0 else (70, 90, 40, 200)
        p.line([base, mid, tip], col, 0.011)

    # near side legs (in front of the body)
    _small_leg(p, a, (0.15, 0.075 + by), 0.05, far=False, phase=3.0)
    _small_leg(p, a, (0.28, 0.08 + by), 0.12, far=False, phase=4.0)
    _hind_leg(p, a, (0.05, 0.03 + by), far=False)


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
    view: str = "top"      # "top" (rotates to face where it goes) or "side" (profile, mirrors left/right)
    ground: float = 0.0    # side view: where the feet are, in body lengths below the body centre


PREY_KINDS = {
    "Bugs": PreyKind("Bugs", draw_bug, 0.06, 0.10, "walk", 0.85, ("Scratching", "Rustling")),
    "Mice": PreyKind("Mice", draw_mouse, 0.10, 0.22, "walk", 1.25, ("Mouse squeaks", "Scratching", "Rustling")),
    "Birds": PreyKind("Birds", draw_bird, 0.09, 0.13, "hop", 0.95, ("Bird chirps", "Rustling")),
    "Fish": PreyKind("Fish", draw_fish, 0.12, 0.14, "swim", 0.85, ("Rustling",)),
    "Feathers": PreyKind("Feathers", draw_feather, 0.13, 0.09, "drift", 0.8, ("Rustling",)),
    "Grasshopper": PreyKind("Grasshopper", draw_grasshopper, 0.10, 0.9, "jump", 1.05,
                            ("Grasshopper clicks", "Rustling"), view="side", ground=GH_GROUND),
    "Laser dot": PreyKind("Laser dot", draw_laser, 0.022, 0.35, "laser", 1.15, ("Scratching", "Rustling")),
}
MIXED = "Mixed"
PREY_NAMES = list(PREY_KINDS) + [MIXED]
