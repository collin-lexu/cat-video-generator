"""All user facing settings, their defaults, validation and helpers.

The defaults are tuned for an ambush hunter: prey that stops, sits still,
twitches, hides and peeks, then darts away.
"""

from __future__ import annotations

import dataclasses
import random
import re
from dataclasses import dataclass, field
from datetime import datetime

from .backgrounds import BACKGROUND_NAMES, CUSTOM_COLOR
from .covers import COVER_NAMES
from .prey import PREY_NAMES
from .sounds import SOUND_NAMES

RESOLUTIONS = {"1080p": (1920, 1080), "720p": (1280, 720)}
FPS = 30
MIN_LENGTH_MIN = 1
MAX_LENGTH_MIN = 180
PREVIEW_SECONDS = 15


@dataclass
class Settings:
    # Video
    length_minutes: int = 60
    resolution: str = "1080p"

    # Prey
    prey_type: str = "Mice"
    prey_count: int = 3
    prey_size: float = 1.3
    speed: float = 1.0

    # Behaviour (0 to 100 percent sliders, plus seconds for stillness)
    pause_frequency: int = 70
    pause_duration: float = 4.0
    twitch: int = 60
    dart_frequency: int = 60

    # Hiding
    hiding: bool = True
    hide_objects: str = "Mixed"
    hide_spots: int = 4
    hide_frequency: int = 50

    # Background
    background: str = "Dark solid"
    custom_color: str = "#1b1f2e"

    # Sound
    sound: bool = True
    volume: int = 60
    sound_types: list = field(default_factory=lambda: ["Rustling", "Scratching", "Mouse squeaks"])

    # Randomness
    seed: int = 12345
    fixed_seed: bool = True

    # ---------------------------------------------------------------
    def validated(self) -> "Settings":
        """Return a copy with every value clamped into its legal range."""
        s = dataclasses.replace(self)
        s.length_minutes = int(_clamp(round(float(s.length_minutes)), MIN_LENGTH_MIN, MAX_LENGTH_MIN))
        if s.resolution not in RESOLUTIONS:
            s.resolution = "1080p"
        if s.prey_type not in PREY_NAMES:
            s.prey_type = "Mice"
        s.prey_count = int(_clamp(round(float(s.prey_count)), 1, 12))
        s.prey_size = float(_clamp(float(s.prey_size), 0.5, 2.5))
        s.speed = float(_clamp(float(s.speed), 0.25, 3.0))
        s.pause_frequency = int(_clamp(float(s.pause_frequency), 0, 100))
        s.pause_duration = float(_clamp(float(s.pause_duration), 0.5, 20.0))
        s.twitch = int(_clamp(float(s.twitch), 0, 100))
        s.dart_frequency = int(_clamp(float(s.dart_frequency), 0, 100))
        s.hiding = bool(s.hiding)
        if s.hide_objects not in COVER_NAMES:
            s.hide_objects = "Mixed"
        s.hide_spots = int(_clamp(round(float(s.hide_spots)), 1, 8))
        s.hide_frequency = int(_clamp(float(s.hide_frequency), 0, 100))
        if s.background not in BACKGROUND_NAMES:
            s.background = "Dark solid"
        s.custom_color = normalize_color(s.custom_color)
        s.sound = bool(s.sound)
        s.volume = int(_clamp(float(s.volume), 0, 100))
        s.sound_types = [t for t in (s.sound_types or []) if t in SOUND_NAMES]
        s.seed = int(abs(int(float(s.seed or 0)))) % (2**31)
        s.fixed_seed = bool(s.fixed_seed)
        return s

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in known}).validated()

    @property
    def size(self) -> tuple[int, int]:
        return RESOLUTIONS[self.resolution]


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
_RGB = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)")


def normalize_color(value) -> str:
    """Accept '#rrggbb', 'rrggbb' or 'rgb(a)(r, g, b, ...)' and return '#rrggbb'."""
    text = str(value or "").strip()
    m = _HEX.match(text)
    if m:
        return "#" + m.group(1).lower()
    m = _RGB.match(text)
    if m:
        r, g, b = (int(_clamp(round(float(x)), 0, 255)) for x in m.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#1b1f2e"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = normalize_color(value)[1:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def new_seed() -> int:
    return random.SystemRandom().randrange(1, 999_999)


def randomize(base: Settings | None = None, rng: random.Random | None = None) -> Settings:
    """Pick random visual, behaviour and sound settings.

    Length, resolution, sound on/off and volume are kept from ``base`` so a
    quick variety test never surprises you with a 3 hour render.
    """
    base = (base or Settings()).validated()
    r = rng or random.Random()
    s = dataclasses.replace(base)
    s.prey_type = r.choice(PREY_NAMES)
    s.prey_count = r.randint(1, 6)
    s.prey_size = round(r.uniform(0.7, 1.8), 1)
    s.speed = round(r.uniform(0.5, 1.8), 1)
    s.pause_frequency = r.randint(30, 95)
    s.pause_duration = round(r.uniform(1.0, 8.0), 1)
    s.twitch = r.randint(20, 95)
    s.dart_frequency = r.randint(20, 90)
    s.hiding = r.random() < 0.8
    s.hide_objects = r.choice(COVER_NAMES)
    s.hide_spots = r.randint(2, 6)
    s.hide_frequency = r.randint(20, 80)
    s.background = r.choice([b for b in BACKGROUND_NAMES if b != CUSTOM_COLOR])
    s.sound_types = r.sample(SOUND_NAMES, r.randint(1, len(SOUND_NAMES)))
    s.seed = r.randrange(1, 999_999)
    return s.validated()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def format_length(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    if minutes > 60:
        return f"{minutes // 60}h{minutes % 60:02d}m"
    return f"{minutes}min"


def build_filename(s: Settings, seconds: float, seed: int, when: datetime | None = None) -> str:
    """e.g. 'mice_dark-solid_1h_2026-11-03_1542_seed12345.mp4'"""
    when = when or datetime.now()
    return (
        f"{_slug(s.prey_type)}_{_slug(s.background)}_{format_length(seconds)}_"
        f"{when:%Y-%m-%d_%H%M}_seed{seed}.mp4"
    )
