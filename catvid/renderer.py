"""Builds frames and streams them to ffmpeg.

Speed tricks:
* The background (with hiding objects baked in) is drawn once.
* Each frame only redraws small boxes around the prey ("dirty rectangles");
  everything else is reused, so 1080p renders much faster than real time.
* Frames go straight into ffmpeg's stdin and audio is synthesised in small
  chunks, so memory use stays flat even for 3 hour videos.
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw

from . import covers as cover_mod
from .backgrounds import CUSTOM_COLOR, make_background
from .behavior import Behavior, Cover, JumpAgent, PreyAgent, SimEvent
from .prey import MIXED as MIXED_PREY, PREY_KINDS, Pen
from .settings import FPS, Settings, build_filename, hex_to_rgb, new_seed
from .sounds import SAMPLE_RATE, pick_sound, stream_audio

SUPERSAMPLE = 2          # draw prey at 2x then shrink, for smooth edges
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

ProgressFn = Callable[[float, str], None]


class RenderCancelled(Exception):
    pass


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


# ----------------------------------------------------------------------------
# Scene
# ----------------------------------------------------------------------------

class Scene:
    """Holds the background, hiding spots and prey, and draws frames."""

    def __init__(self, settings: Settings, seed: int, size: tuple[int, int] | None = None):
        s = settings.validated()
        self.settings = s
        self.w, self.h = size or s.size
        self.aspect = self.w / self.h
        self.dt = 1.0 / FPS
        bg_seq, cover_seq, prey_seq, audio_seq, pick_seq = np.random.SeedSequence(seed).spawn(5)
        self.audio_rng = np.random.default_rng(audio_seq)
        self.pick_rng = np.random.default_rng(pick_seq)

        color = hex_to_rgb(s.custom_color) if s.background == CUSTOM_COLOR else None
        self.bg = make_background(s.background, self.w, self.h, np.random.default_rng(bg_seq), color)

        prey_rng = np.random.default_rng(prey_seq)
        if s.prey_type == MIXED_PREY:
            names = list(PREY_KINDS)
            order = [names[i] for i in prey_rng.permutation(len(names))]
            kinds = [PREY_KINDS[order[i % len(order)]] for i in range(s.prey_count)]
        else:
            kinds = [PREY_KINDS[s.prey_type]] * s.prey_count

        beh = Behavior(
            pause_frequency=s.pause_frequency / 100,
            pause_duration=s.pause_duration,
            twitch=s.twitch / 100,
            dart_frequency=s.dart_frequency / 100,
            hiding=s.hiding,
            hide_frequency=s.hide_frequency / 100,
            speed=s.speed,
            size=s.prey_size,
        )

        # hiding spots: big enough to hide the largest prey on screen
        self.covers: list[Cover] = []
        self.cover_layer: Image.Image | None = None
        cover_rng = np.random.default_rng(cover_seq)
        if s.hiding:
            biggest = max(k.length for k in kinds) * s.prey_size
            radius = max(0.07, biggest * 1.2)
            spots = cover_mod.place_covers(s.hide_spots, self.aspect, radius, cover_rng)
            self.covers = [Cover(x, y, radius) for x, y in spots]
            layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            for c in self.covers:
                drawer = cover_mod.cover_drawer(s.hide_objects, cover_rng)
                drawer(d, c.x * self.h, c.y * self.h, c.r * self.h, cover_rng)
            self.cover_layer = layer
            self.composite = Image.alpha_composite(self.bg.convert("RGBA"), layer).convert("RGB")
        else:
            self.composite = self.bg

        self.agents = [(JumpAgent if k.style == "jump" else PreyAgent)(i, k, beh, self.aspect, self.covers, prey_rng)
                       for i, k in enumerate(kinds)]
        self.comp_np = np.array(self.composite, dtype=np.uint8)
        self.frame = self.comp_np.copy()
        self._dirty: list[tuple[int, int, int, int]] = []
        self.time = 0.0

    # ---------------------------------------------------------------- sim
    def step(self) -> list[tuple[float, str, float, float]]:
        """Advance one frame. Returns sound events (time, sound, gain, pan)."""
        raw: list[SimEvent] = []
        sounds = []
        enabled = self.settings.sound_types if self.settings.sound else []
        for a in self.agents:
            before = len(raw)
            a.update(self.dt, raw)
            for ev in raw[before:]:
                chance = {"twitch": 0.55, "dart": 0.9, "step": 0.5, "rustle": 0.9}.get(ev.kind, 0.5)
                if not enabled or self.pick_rng.random() > chance:
                    continue
                if ev.kind == "rustle" and "Rustling" in enabled:
                    name = "Rustling"
                else:
                    name = pick_sound(a.kind.sounds, enabled, self.pick_rng)
                if name:
                    gain = {"twitch": 0.5, "dart": 0.8, "step": 0.3, "rustle": 0.8}[ev.kind] * ev.strength
                    sounds.append((self.time, name, gain, ev.x))
        self.time += self.dt
        return sounds

    # -------------------------------------------------------------- frames
    def _anchor(self, a: PreyAgent) -> tuple[float, float]:
        """Pixel position of the drawing origin (side view prey are lifted by their jump height)."""
        if a.kind.view == "side":
            return a.x * self.h, (a.y - a.z - a.kind.ground * a.length) * self.h
        return a.x * self.h, a.y * self.h

    def _box(self, a: PreyAgent):
        r = a.length * a.kind.extent * self.h + 4
        x, y = self._anchor(a)
        y_lo, y_hi = y - r, y + r
        if a.kind.view == "side":
            y_hi = max(y_hi, a.y * self.h + a.length * 0.2 * self.h + 4)   # include the ground shadow
        return (max(0, int(x - r)), max(0, int(y_lo)), min(self.w, int(math.ceil(x + r))),
                min(self.h, int(math.ceil(y_hi))))

    @staticmethod
    def _merge(boxes):
        boxes = [list(b) for b in boxes]
        merged = True
        while merged:
            merged = False
            out = []
            while boxes:
                b = boxes.pop()
                for o in out:
                    if b[0] < o[2] and o[0] < b[2] and b[1] < o[3] and o[1] < b[3]:
                        o[0], o[1] = min(o[0], b[0]), min(o[1], b[1])
                        o[2], o[3] = max(o[2], b[2]), max(o[3], b[3])
                        merged = True
                        break
                else:
                    out.append(b)
            boxes = out
        return [tuple(b) for b in boxes]

    def render(self) -> np.ndarray:
        """Draw the current state. Returns an (h, w, 3) uint8 array (reused buffer)."""
        frame = self.frame
        for x0, y0, x1, y1 in self._dirty:
            frame[y0:y1, x0:x1] = self.comp_np[y0:y1, x0:x1]
        groups: dict[tuple, list[PreyAgent]] = {}
        boxes = [self._box(a) for a in self.agents]
        clusters = self._merge([b for b in boxes if b[2] > b[0] and b[3] > b[1]])
        for a, b in zip(self.agents, boxes):
            for c in clusters:
                if b[0] >= c[0] and b[1] >= c[1] and b[2] <= c[2] and b[3] <= c[3]:
                    groups.setdefault(c, []).append(a)
                    break
        ss = SUPERSAMPLE
        for box, agents in groups.items():
            x0, y0, x1, y1 = box
            bw, bh = x1 - x0, y1 - y0
            layer = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            for a in sorted(agents, key=lambda ag: ag.y):   # nearer (lower) prey drawn on top
                ax, ay = self._anchor(a)
                k = a.length * self.h * ss
                if a.kind.view == "side":
                    # soft shadow on the ground, shrinking and fading as it jumps higher
                    gx, gy = (ax - x0) * ss, (a.y * self.h - y0) * ss
                    lift = min(1.0, a.z / max(a.length * 3, 1e-6))
                    rx, ry = k * 0.5 * (1 - 0.4 * lift), k * 0.07 * (1 - 0.4 * lift)
                    d.ellipse([gx - rx, gy - ry, gx + rx, gy + ry], fill=(0, 0, 0, int(80 * (1 - 0.6 * lift))))
                    pen = Pen(d, (ax - x0) * ss, (ay - y0) * ss, a.pitch, k, flip=a.facing < 0)
                else:
                    pen = Pen(d, (ax - x0) * ss, (ay - y0) * ss, a.heading, k)
                a.kind.draw(pen, a.anim)
            small = layer.convert("RGBa").reduce(ss).convert("RGBA")
            patch = self.bg.crop(box).convert("RGBA")
            patch.alpha_composite(small)
            if self.cover_layer is not None:
                patch.alpha_composite(self.cover_layer.crop(box))
            frame[y0:y1, x0:x1] = np.asarray(patch.convert("RGB"))
        self._dirty = list(groups)
        return frame


# ----------------------------------------------------------------------------
# Encoding
# ----------------------------------------------------------------------------

@dataclass
class RenderResult:
    path: Path
    seed: int
    seconds: float
    elapsed: float


def _video_cmd(w, h, out_path, crf=20):
    return [
        ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "animation", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-g", str(FPS * 2), "-movflags", "+faststart",
        str(out_path),
    ]


def _mux_cmd(video_path, out_path):
    return [
        ffmpeg_exe(), "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "2", "-i", "-",
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", str(out_path),
    ]


def _run_pipe(cmd, chunks, cancel: threading.Event | None):
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            for chunk in chunks:
                if cancel is not None and cancel.is_set():
                    raise RenderCancelled()
                proc.stdin.write(chunk)
            proc.stdin.close()
            code = proc.wait()
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if code != 0:
            err.seek(0)
            raise RuntimeError("ffmpeg failed: " + err.read().decode(errors="replace")[-2000:])


def render_video(settings: Settings, seconds: float | None = None, out_path: str | Path | None = None,
                 progress: ProgressFn | None = None, cancel: threading.Event | None = None,
                 seed: int | None = None) -> RenderResult:
    """Render a video to MP4. ``seconds`` overrides the length (used for previews)."""
    s = settings.validated()
    if seed is None:
        seed = s.seed if s.fixed_seed else new_seed()
    seconds = float(seconds if seconds is not None else s.length_minutes * 60)
    total_frames = int(round(seconds * FPS))
    progress = progress or (lambda f, m: None)
    started = time.time()

    if out_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / build_filename(s, seconds, seed)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    progress(0.0, "Drawing background...")
    scene = Scene(s, seed)
    with_sound = s.sound and bool(s.sound_types) and s.volume > 0
    video_target = out_path.with_name(out_path.stem + ".video-only.tmp.mp4") if with_sound else out_path
    events: list = []
    video_share = 0.92 if with_sound else 1.0

    def frames():
        last = 0.0
        for i in range(total_frames):
            events.extend(scene.step())
            yield memoryview(scene.render()).cast("B")
            now = time.time()
            if now - last > 0.25 or i == total_frames - 1:
                last = now
                done = (i + 1) / total_frames
                el = now - started
                eta = el / done * (1 - done) if done > 0 else 0
                speed = (i + 1) / FPS / max(el, 1e-6)
                progress(done * video_share,
                         f"Rendering frame {i + 1:,} of {total_frames:,} "
                         f"({speed:.1f}x real time, about {_fmt_eta(eta)} left)")

    try:
        _run_pipe(_video_cmd(scene.w, scene.h, video_target), frames(), cancel)
        if with_sound:
            progress(video_share, "Adding sound...")
            chunks = stream_audio(events, seconds, s.volume, scene.audio_rng)
            _run_pipe(_mux_cmd(video_target, out_path), chunks, cancel)
    except BaseException:
        for p in (video_target, out_path):
            try:
                p.unlink()
            except OSError:
                pass
        raise
    finally:
        if with_sound:
            try:
                os.remove(video_target)
            except OSError:
                pass

    progress(1.0, "Done")
    return RenderResult(out_path, seed, seconds, time.time() - started)


def _fmt_eta(sec: float) -> str:
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60:02d}s"
    return f"{sec // 3600}h {(sec % 3600) // 60:02d}m"


def render_still(settings: Settings, seed: int, seconds: float = 3.0, size=None) -> Image.Image:
    """Simulate ``seconds`` and return one frame as a Pillow image (handy for thumbnails)."""
    scene = Scene(settings, seed, size)
    for _ in range(int(seconds * FPS)):
        scene.step()
    return Image.fromarray(scene.render().copy())
