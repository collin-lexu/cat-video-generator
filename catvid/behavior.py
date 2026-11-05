"""Prey behaviour: a small state machine per prey.

Everything here works in normalised units (frame height = 1, width =
aspect ratio), so 720p and 1080p videos with the same seed move the same.

The cycle is designed for ambush hunters:

    wander -> stop and sit still (twitching now and then) -> dart away
    -> sneak into a hiding spot -> peek out, twitch, rustle -> dart off ...
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .prey import Anim, PreyKind

MOVE, PAUSE, DART, TO_COVER, HIDE, PEEK_OUT, PEEK, BACK_IN = (
    "move", "pause", "dart", "to_cover", "hide", "peek_out", "peek", "back_in")


@dataclass
class Behavior:
    """Behaviour knobs, all 0..1 except durations and multipliers."""

    pause_frequency: float = 0.7
    pause_duration: float = 4.0
    twitch: float = 0.6
    dart_frequency: float = 0.6
    hiding: bool = True
    hide_frequency: float = 0.5
    speed: float = 1.0
    size: float = 1.0


@dataclass
class Cover:
    x: float
    y: float
    r: float               # normalised radius
    occupant: int | None = None


@dataclass
class SimEvent:
    kind: str              # "twitch", "dart", "step", "rustle"
    x: float               # normalised x, for stereo panning
    strength: float


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


class PreyAgent:
    def __init__(self, idx: int, kind: PreyKind, beh: Behavior, aspect: float,
                 covers: list[Cover], rng: np.random.Generator):
        self.idx = idx
        self.kind = kind
        self.beh = beh
        self.aspect = aspect
        self.covers = covers
        self.rng = rng
        self.length = kind.length * beh.size
        self.cruise = kind.speed * beh.speed * math.sqrt(beh.size)
        self.margin = max(0.04, self.length * 0.9)
        self.x = rng.uniform(self.margin, aspect - self.margin)
        self.y = rng.uniform(self.margin, 1 - self.margin)
        self.heading = rng.uniform(-math.pi, math.pi)
        self.speed = 0.0
        self.anim = Anim(seed=float(rng.uniform(0, 100)))
        self.twitch_left = 0.0
        self.twitch_len = 0.25
        self.twitch_strength = 0.0
        self.twitch_turn = 0.0
        self.twitch_step = 0.0
        self.step_clock = 0.0
        self.cover: Cover | None = None
        self.backwards = False
        self.dart_to_cover = False
        self.t = 0.0
        self.state = MOVE
        self.timer = 0.0
        self.target = (self.x, self.y)
        # start most prey sitting still: ambush hunters love that
        if rng.random() < 0.6 and beh.pause_frequency > 0:
            self._enter_pause()
        else:
            self._enter_move()

    # ------------------------------------------------------------------ utils
    def _rand_point(self, near=None, dist=(0.15, 0.6)):
        for _ in range(20):
            if near is None:
                x = self.rng.uniform(self.margin, self.aspect - self.margin)
                y = self.rng.uniform(self.margin, 1 - self.margin)
            else:
                a = self.rng.uniform(-math.pi, math.pi)
                d = self.rng.uniform(*dist)
                x, y = near[0] + math.cos(a) * d, near[1] + math.sin(a) * d
            if self.margin <= x <= self.aspect - self.margin and self.margin <= y <= 1 - self.margin:
                return x, y
        return (self.rng.uniform(self.margin, self.aspect - self.margin),
                self.rng.uniform(self.margin, 1 - self.margin))

    def _free_cover(self):
        free = [c for c in self.covers if c.occupant is None]
        if not free:
            return None
        # prefer nearby covers, it looks more natural
        d = np.array([math.hypot(c.x - self.x, c.y - self.y) for c in free])
        w = 1 / (0.1 + d)
        return free[int(self.rng.choice(len(free), p=w / w.sum()))]

    def _leave_cover(self):
        if self.cover is not None and self.cover.occupant == self.idx:
            self.cover.occupant = None
        self.cover = None

    # ---------------------------------------------------------- transitions
    def _enter_move(self):
        self._leave_cover()
        self.state = MOVE
        self.target = self._rand_point()
        self.timer = self.rng.uniform(3, 10)
        self.backwards = False

    def _enter_pause(self):
        self.state = PAUSE
        b = self.beh
        self.timer = b.pause_duration * self.rng.uniform(0.5, 1.6)

    def _enter_dart(self, events):
        self._leave_cover()
        self.state = DART
        self.backwards = False
        self.target = self._rand_point(near=(self.x, self.y), dist=(0.25, 0.8))
        self.timer = 4.0
        events.append(SimEvent("dart", self.x / self.aspect, 1.0))

    def _go_hide(self, events, dart=False):
        cover = self._free_cover()
        if cover is None:
            return False
        self._leave_cover()
        cover.occupant = self.idx
        self.cover = cover
        self.state = TO_COVER
        self.target = (cover.x, cover.y)
        self.timer = 12.0
        self.dart_to_cover = dart
        if dart:
            events.append(SimEvent("dart", self.x / self.aspect, 1.0))
        return True

    def _after_pause(self, events):
        b = self.beh
        r = self.rng.random()
        if b.hiding and self.covers and self.rng.random() < b.hide_frequency:
            if self._go_hide(events, dart=self.rng.random() < b.dart_frequency):
                return
        if r < b.dart_frequency:
            self._enter_dart(events)
        else:
            self._enter_move()

    # ---------------------------------------------------------------- update
    def _start_twitch(self, events, strength_boost=1.0):
        self.twitch_len = self.rng.uniform(0.15, 0.45)
        self.twitch_left = self.twitch_len
        self.twitch_strength = min(1.0, self.rng.uniform(0.4, 1.0) * strength_boost)
        # sometimes a little shuffle: turn a bit and creep forward
        if self.rng.random() < 0.35 and self.state != HIDE:
            self.twitch_turn = self.rng.uniform(-0.7, 0.7)
            self.twitch_step = self.length * self.rng.uniform(0.05, 0.25)
        else:
            self.twitch_turn = 0.0
            self.twitch_step = 0.0
        events.append(SimEvent("twitch", self.x / self.aspect, self.twitch_strength))

    def _seek(self, dt, speed_mul, accel=4.0, turn_rate=6.0):
        tx, ty = self.target
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        style = self.kind.style
        want = math.atan2(dy, dx)
        if self.backwards:
            face_want = _wrap(want + math.pi)
            self.heading += max(-turn_rate * dt, min(turn_rate * dt, _wrap(face_want - self.heading)))
            move_dir = want
        else:
            if style == "laser":
                self.heading = want
            else:
                wobble = 0.0
                if self.state == MOVE:
                    wobble = 0.5 * math.sin(self.t * 1.7 + self.anim.seed)
                diff = _wrap(want + wobble * min(1.0, dist * 8) - self.heading)
                self.heading += max(-turn_rate * dt, min(turn_rate * dt, diff))
            move_dir = self.heading
        desired = self.cruise * speed_mul
        # slow down when arriving so it settles instead of overshooting
        desired = min(desired, max(dist * 4, self.cruise * 0.15))
        self.speed += (desired - self.speed) * min(1.0, accel * dt)
        v = self.speed
        if style == "hop" and self.state != DART and self.state != TO_COVER:
            v *= 2.2 * max(0.0, math.sin(self.anim.phase)) ** 2   # hop, hop, hop
        if style == "drift":
            sway = 0.6 * math.sin(self.t * 2.2 + self.anim.seed)
            move_dir += sway
        step = min(v * dt, dist)
        self.x += math.cos(move_dir) * step
        self.y += math.sin(move_dir) * step
        return dist - step, step

    def update(self, dt: float, events: list):
        self.t += dt
        b = self.beh
        self.timer -= dt
        moved = 0.0
        state = self.state
        twitch_rate = 0.15 + 2.2 * b.twitch if b.twitch > 0 else 0.0

        if state == MOVE:
            remaining, moved = self._seek(dt, 1.0)
            if b.pause_frequency > 0 and self.rng.random() < (0.05 + 0.9 * b.pause_frequency) * dt:
                self._enter_pause()
            elif remaining < self.length * 0.2 or self.timer <= 0:
                if b.hiding and self.covers and self.rng.random() < b.hide_frequency * 0.5:
                    if not self._go_hide(events):
                        self._enter_move()
                elif b.pause_frequency > 0:
                    self._enter_pause()
                else:
                    self._enter_move()

        elif state in (PAUSE, PEEK, HIDE):
            self.speed *= max(0.0, 1 - 10 * dt)
            boost = 1.3 if state == PEEK else 1.0
            rate = twitch_rate * (1.3 if state == PEEK else 0.6 if state == HIDE else 1.0)
            if self.twitch_left <= 0 and self.rng.random() < rate * dt:
                self._start_twitch(events, boost)
                if state != PAUSE:
                    events.append(SimEvent("rustle", self.x / self.aspect, 0.8))
            if state == PAUSE and self.timer <= 0:
                self._after_pause(events)
            elif state == HIDE:
                if self.timer <= 0:
                    self._exit_cover(events)
                elif self.rng.random() < 0.45 * dt:
                    self._start_peek()
            elif state == PEEK and self.timer <= 0:
                r = self.rng.random()
                if r < b.dart_frequency * 0.55:
                    self._enter_dart(events)
                elif r < 0.8:
                    self.state = BACK_IN
                    self.backwards = True
                    self.target = (self.cover.x, self.cover.y)
                    self.timer = 5.0
                else:
                    self._enter_pause()     # sits outside the cover for a while
                    self._leave_cover()

        elif state == DART:
            remaining, moved = self._seek(dt, 3.6, accel=10.0, turn_rate=12.0)
            if remaining < self.length * 0.2 or self.timer <= 0:
                if b.pause_frequency > 0 and self.rng.random() < 0.8:
                    self._enter_pause()     # dart, then freeze: classic prey
                else:
                    self._enter_move()

        elif state == TO_COVER:
            mul = 3.0 if self.dart_to_cover else 1.0
            remaining, moved = self._seek(dt, mul, accel=8.0 if self.dart_to_cover else 4.0, turn_rate=10.0)
            if remaining < self.length * 0.08 or self.timer <= 0:
                self.state = HIDE
                self.timer = self.rng.uniform(2.0, 6.0) + b.pause_duration * 0.6
                events.append(SimEvent("rustle", self.x / self.aspect, 1.0))

        elif state == PEEK_OUT:
            remaining, moved = self._seek(dt, 0.45, turn_rate=8.0)
            if remaining < self.length * 0.05 or self.timer <= 0:
                self.state = PEEK
                self.timer = self.rng.uniform(1.2, 3.5) + b.pause_duration * 0.3

        elif state == BACK_IN:
            remaining, moved = self._seek(dt, 0.5, turn_rate=3.0)
            if remaining < self.length * 0.05 or self.timer <= 0:
                self.state = HIDE
                self.backwards = False
                self.timer = max(self.timer, self.rng.uniform(1.0, 3.0))

        # twitch animation, including little shuffles
        if self.twitch_left > 0:
            self.twitch_left -= dt
            k = max(0.0, self.twitch_left / self.twitch_len)
            self.anim.twitch = self.twitch_strength * math.sin(math.pi * k)
            frac = dt / self.twitch_len
            self.heading += self.twitch_turn * frac
            if self.twitch_step:
                self.x += math.cos(self.heading) * self.twitch_step * frac
                self.y += math.sin(self.heading) * self.twitch_step * frac
                moved += self.twitch_step * frac
            self.anim.phase += dt * 25 * self.anim.twitch
        else:
            self.anim.twitch = 0.0

        # footsteps (scratching) while walking about in the open
        if moved > 0 and self.state in (MOVE, DART):
            self.step_clock += moved / max(self.length, 1e-6)
            if self.step_clock > 3.0:
                self.step_clock = 0.0
                events.append(SimEvent("step", self.x / self.aspect, 0.35 if self.state == MOVE else 0.6))

        self.anim.t = self.t
        self.anim.phase += moved / max(self.length, 1e-6) * 2 * math.pi * 0.9
        self.anim.moving = min(1.0, self.speed / max(self.cruise, 1e-6))
        if self.kind.style == "hop":
            self.anim.phase += dt * 9 * (self.state in (MOVE,))
            self.anim.flap = 1.0 if self.state in (DART, TO_COVER) and self.speed > self.cruise * 1.2 else 0.0
        m = self.margin
        self.x = min(max(self.x, m * 0.5), self.aspect - m * 0.5)
        self.y = min(max(self.y, m * 0.5), 1 - m * 0.5)

    def _start_peek(self):
        c = self.cover
        # peek towards the middle of the screen, give or take
        base = math.atan2(0.5 - c.y, self.aspect / 2 - c.x)
        a = base + self.rng.uniform(-1.4, 1.4)
        d = c.r * 0.72 + self.length * 0.15
        self.target = (c.x + math.cos(a) * d, c.y + math.sin(a) * d)
        self.heading = a  # turns around while hidden
        self.state = PEEK_OUT
        self.backwards = False
        self.timer = 4.0

    def _exit_cover(self, events):
        if self.rng.random() < 0.4 + 0.6 * self.beh.dart_frequency:
            self._enter_dart(events)
        else:
            self._enter_move()


SIT, CROUCH, AIR, LAND = "sit", "crouch", "air", "land"


class JumpAgent(PreyAgent):
    """A side view jumper (grasshopper): sits, crouches, then leaps in a fast arc.

    ``x, y`` is the spot on the ground, ``z`` the height above it (both in
    frame heights). ``facing`` is +1 (right) or -1 (left) and ``pitch`` tilts
    the body nose up on take off and nose down on landing.

    The behaviour sliders still apply: speed makes jumps faster and waits
    shorter, "sits still" adds longer freezes, "darts off" chains jumps into
    quick bursts and twitch flicks the antennae and legs while sitting.
    Jumpers ignore hiding spots (they just land in the grass).
    """

    def __init__(self, idx, kind, beh, aspect, covers, rng):
        self.z = 0.0
        self.pitch = 0.0
        self.facing = 1.0
        self.burst = 0
        self.jump_from = (0.0, 0.0)
        self.jump_to = (0.0, 0.0)
        self.jump_h = 0.0
        self.jump_t = 0.0
        self.jump_len = 0.3
        super().__init__(idx, kind, beh, aspect, [], rng)
        self.margin = max(0.05, self.length * 1.1)
        self.x = min(max(self.x, self.margin), aspect - self.margin)
        self.y = min(max(self.y, self.margin + self.length * 0.6), 1 - self.margin)
        self.facing = 1.0 if rng.random() < 0.5 else -1.0
        self.heading = 0.0
        self._sit(first=True)

    # replace the walking cycle from PreyAgent
    def _enter_move(self):
        self.state = SIT
        self.timer = 0.1

    def _enter_pause(self):
        self.state = SIT
        self.timer = 0.1

    def _sit(self, first=False):
        b = self.beh
        self.state = SIT
        quick = 1.0 / max(0.3, b.speed)
        if self.burst > 0:
            self.burst -= 1
            self.timer = self.rng.uniform(0.06, 0.2) * quick
        elif self.rng.random() < b.pause_frequency * 0.35:
            self.timer = b.pause_duration * self.rng.uniform(0.3, 0.8)    # a proper freeze
        else:
            self.timer = self.rng.uniform(0.2, 0.75) * quick
        if first:
            self.timer = self.rng.uniform(0.2, 1.0)

    def _pick_jump(self):
        b = self.beh
        top = self.margin + self.length * 0.6      # leave room above for the body
        for _ in range(12):
            d = self.rng.uniform(0.18, 0.6) * (0.8 + 0.2 * b.speed) * math.sqrt(b.size)
            # mostly sideways: that is what a side profile shows best
            ang = self.rng.normal(0.0, 0.45)
            dx = math.cos(ang) * d
            dy = math.sin(ang) * d * 0.7
            # head away from the nearest edge, otherwise go either way
            left, right = self.x - self.margin, self.aspect - self.margin - self.x
            if left < 0.25:
                sign = 1.0
            elif right < 0.25:
                sign = -1.0
            elif self.rng.random() < 0.7:
                sign = self.facing     # keeps going the way it faces, sometimes turns around
            else:
                sign = -self.facing
            tx, ty = self.x + sign * dx, self.y + dy
            if self.margin <= tx <= self.aspect - self.margin and top <= ty <= 1 - self.margin:
                return tx, ty
        return (self.rng.uniform(self.margin, self.aspect - self.margin),
                self.rng.uniform(top, 1 - self.margin))

    def update(self, dt: float, events: list):
        self.t += dt
        b = self.beh
        self.timer -= dt
        a = self.anim
        twitch_rate = 0.4 + 3.0 * b.twitch if b.twitch > 0 else 0.0

        if self.state == SIT:
            a.leg += (0.0 - a.leg) * min(1.0, 18 * dt)
            a.crouch += (0.0 - a.crouch) * min(1.0, 12 * dt)
            a.air = max(0.0, a.air - 8 * dt)
            self.pitch *= max(0.0, 1 - 14 * dt)
            if self.twitch_left <= 0 and self.rng.random() < twitch_rate * dt:
                self.twitch_len = self.rng.uniform(0.12, 0.35)
                self.twitch_left = self.twitch_len
                self.twitch_strength = self.rng.uniform(0.4, 1.0)
                events.append(SimEvent("twitch", self.x / self.aspect, self.twitch_strength * 0.6))
            if self.timer <= 0:
                self.jump_to = self._pick_jump()
                new_facing = 1.0 if self.jump_to[0] >= self.x else -1.0
                if new_facing != self.facing:
                    self.facing = new_facing
                self.state = CROUCH
                self.timer = self.rng.uniform(0.06, 0.12) / max(0.5, b.speed ** 0.5)
                self.crouch_len = self.timer

        elif self.state == CROUCH:
            k = 1 - max(0.0, self.timer) / self.crouch_len
            a.crouch = k
            a.leg = 0.0
            self.pitch = -0.12 * k              # nose up, ready to spring
            if self.timer <= 0:
                self.state = AIR
                self.jump_from = (self.x, self.y)
                d = math.hypot(self.jump_to[0] - self.x, self.jump_to[1] - self.y)
                self.jump_len = (0.18 + 0.38 * math.sqrt(d)) / max(0.4, b.speed ** 0.6)
                self.jump_h = d * self.rng.uniform(0.28, 0.5) + 0.03
                self.jump_t = 0.0
                if self.burst == 0 and self.rng.random() < b.dart_frequency * 0.5:
                    self.burst = int(self.rng.integers(1, 4))     # a burst of quick jumps
                events.append(SimEvent("dart", self.x / self.aspect, 0.9))

        elif self.state == AIR:
            self.jump_t += dt
            u = min(1.0, self.jump_t / self.jump_len)
            fx, fy = self.jump_from
            tx, ty = self.jump_to
            self.x = fx + (tx - fx) * u
            self.y = fy + (ty - fy) * u
            self.z = 4 * self.jump_h * u * (1 - u)
            # legs snap straight at take off, then slowly fold back in flight
            a.leg = 1.0 if u < 0.15 else max(0.72, 1.0 - (u - 0.15) * 0.5)
            a.crouch = max(0.0, 1.0 - u * 8)
            a.air = min(1.0, u * 6, (1 - u) * 5 + 0.2)
            # nose follows the arc: up going up, down coming down
            self.pitch = -0.55 * (1 - 2 * u) * min(1.0, self.jump_h / max(0.05, abs(tx - fx) + 1e-6))
            self.speed = math.hypot(tx - fx, ty - fy) / self.jump_len
            if u >= 1.0:
                self.z = 0.0
                self.state = LAND
                self.timer = 0.08
                a.crouch = 1.0
                events.append(SimEvent("step", self.x / self.aspect, 0.8))

        elif self.state == LAND:
            a.leg *= max(0.0, 1 - 30 * dt)
            a.air = max(0.0, a.air - 10 * dt)
            self.pitch *= max(0.0, 1 - 20 * dt)
            self.speed = 0.0
            if self.timer <= 0:
                self._sit()

        if self.twitch_left > 0:
            self.twitch_left -= dt
            k = max(0.0, self.twitch_left / self.twitch_len)
            a.twitch = self.twitch_strength * math.sin(math.pi * k)
        else:
            a.twitch = 0.0
        a.t = self.t
        a.moving = 1.0 if self.state == AIR else 0.0
