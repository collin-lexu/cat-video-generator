"""Sounds generated with code (no audio files), plus a streaming audio track.

Each sound is a function ``make_xxx(rng, sr) -> np.ndarray`` (mono float32,
roughly -1..1, at most ``MAX_EVENT_SECONDS`` long). To add a new sound, write
the function and add it to ``SOUNDS``; prey types list the sounds they like in
``prey.PREY_KINDS``.

The audio track is synthesised a few seconds at a time and streamed to
ffmpeg, so a 3 hour video never needs the whole soundtrack in memory.
"""

from __future__ import annotations

import math
from typing import Iterator

import numpy as np

SAMPLE_RATE = 44100
MAX_EVENT_SECONDS = 2.0


def _bandpass(x: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    # smooth edges so it does not ring
    gain = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(spec * gain, len(x)).astype(np.float32)


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return (x / m * peak).astype(np.float32) if m > 0 else x.astype(np.float32)


def _fade(x: np.ndarray, sr: int, ms: float = 8) -> np.ndarray:
    n = min(len(x) // 2, int(sr * ms / 1000))
    if n > 0:
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


def make_rustle(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Leaves or grass rustling: crackly filtered noise made of tiny grains."""
    dur = rng.uniform(0.25, 0.8)
    n = int(dur * sr)
    noise = _bandpass(rng.standard_normal(n).astype(np.float32), sr, 1200, rng.uniform(5000, 9000))
    env = np.zeros(n, dtype=np.float32)
    grains = int(dur * rng.uniform(25, 60))
    decay = np.exp(-np.arange(int(0.03 * sr)) / (0.006 * sr)).astype(np.float32)
    for start in rng.integers(0, max(1, n - len(decay)), grains):
        env[start:start + len(decay)] += decay[: n - start] * rng.uniform(0.3, 1.0)
    shape = np.sin(np.linspace(0, math.pi, n)) ** 0.6
    return _fade(_norm(noise * env * shape, 0.8), sr)


def make_scratch(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Little claws scratching: a quick rhythm of short scrapes."""
    count = int(rng.integers(3, 9))
    gap = rng.uniform(0.045, 0.085)
    n = int((count * gap + 0.08) * sr)
    out = np.zeros(n, dtype=np.float32)
    for i in range(count):
        ln = int(rng.uniform(0.012, 0.035) * sr)
        burst = _bandpass(rng.standard_normal(ln).astype(np.float32), sr, 2500, 10000)
        burst *= np.exp(-np.linspace(0, 5, ln)).astype(np.float32) * rng.uniform(0.5, 1.0)
        s = int((i * gap + rng.uniform(0, 0.012)) * sr)
        out[s:s + ln] += burst[: n - s]
    return _fade(_norm(out, 0.8), sr, 3)


def make_chirp(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Small bird chirps: two to five quick whistled notes."""
    notes = int(rng.integers(2, 6))
    base = rng.uniform(2600, 4200)
    parts = []
    for _ in range(notes):
        dur = rng.uniform(0.04, 0.11)
        t = np.arange(int(dur * sr)) / sr
        f0 = base * rng.uniform(0.9, 1.1)
        f1 = f0 * rng.choice([0.7, 1.35, 1.6])
        freq = f0 + (f1 - f0) * (t / dur)
        ph = 2 * np.pi * np.cumsum(freq) / sr
        tone = np.sin(ph) + 0.25 * np.sin(2 * ph)
        env = np.sin(np.pi * t / dur) ** 2
        parts.append((tone * env).astype(np.float32))
        parts.append(np.zeros(int(rng.uniform(0.03, 0.08) * sr), dtype=np.float32))
    return _fade(_norm(np.concatenate(parts), 0.7), sr, 3)


def make_squeak(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Mouse squeaks: high, short tones with a fast wobble."""
    count = int(rng.integers(1, 4))
    parts = []
    for _ in range(count):
        dur = rng.uniform(0.05, 0.16)
        t = np.arange(int(dur * sr)) / sr
        f = rng.uniform(3200, 5600)
        vib = 1 + 0.04 * np.sin(2 * np.pi * rng.uniform(35, 70) * t)
        bend = 1 + rng.uniform(-0.15, 0.15) * (t / dur)
        ph = 2 * np.pi * np.cumsum(f * vib * bend) / sr
        tone = np.sin(ph) + 0.15 * np.sin(3 * ph)
        env = np.minimum(1, t / 0.01) * np.exp(-t / (dur * 0.6))
        parts.append((tone * env).astype(np.float32))
        parts.append(np.zeros(int(rng.uniform(0.04, 0.12) * sr), dtype=np.float32))
    return _fade(_norm(np.concatenate(parts), 0.55), sr, 3)


def make_clicks(rng: np.random.Generator, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Grasshopper wing snaps: a fast, dry crackle of sharp clicks, like a grasshopper taking off."""
    count = int(rng.integers(4, 12))
    gap = rng.uniform(0.018, 0.04)
    n = int((count * gap + 0.05) * sr)
    out = np.zeros(n, dtype=np.float32)
    for i in range(count):
        ln = int(rng.uniform(0.003, 0.007) * sr)
        burst = _bandpass(rng.standard_normal(ln * 4).astype(np.float32), sr, 3500, 12000)[:ln]
        burst *= np.exp(-np.linspace(0, 6, ln)).astype(np.float32) * rng.uniform(0.4, 1.0)
        s = int((i * gap + rng.uniform(0, gap * 0.4)) * sr)
        out[s:s + ln] += burst[: n - s]
    return _fade(_norm(out, 0.75), sr, 2)


SOUNDS = {
    "Rustling": make_rustle,
    "Scratching": make_scratch,
    "Bird chirps": make_chirp,
    "Mouse squeaks": make_squeak,
    "Grasshopper clicks": make_clicks,
}
SOUND_NAMES = list(SOUNDS)


def pick_sound(preferred, enabled, rng: np.random.Generator) -> str | None:
    """Choose a sound the prey likes that is switched on, else any switched on sound."""
    enabled = [s for s in enabled if s in SOUNDS]
    if not enabled:
        return None
    liked = [s for s in preferred if s in enabled]
    pool = liked or enabled
    return pool[int(rng.integers(0, len(pool)))]


def volume_gain(volume: int) -> float:
    return (max(0, min(100, volume)) / 100.0) ** 1.2 * 1.8


def stream_audio(events, duration: float, volume: int, rng: np.random.Generator,
                 sr: int = SAMPLE_RATE, chunk_seconds: float = 5.0) -> Iterator[bytes]:
    """Yield 16 bit stereo PCM chunks for the whole video.

    ``events`` is an iterable of ``(time_seconds, sound_name, gain, pan)``
    sorted by time, where pan is 0 (left) to 1 (right).
    """
    total = int(round(duration * sr))
    chunk = int(chunk_seconds * sr)
    tail = int(MAX_EVENT_SECONDS * sr)
    gain = volume_gain(volume)
    carry = np.zeros((tail, 2), dtype=np.float32)
    events = iter(events)
    pending = next(events, None)
    pos = 0
    while pos < total:
        n = min(chunk, total - pos)
        buf = np.zeros((n + tail, 2), dtype=np.float32)
        buf[:tail] += carry
        end_t = (pos + n) / sr
        while pending is not None and pending[0] < end_t:
            t, name, g, pan = pending
            pending = next(events, None)
            fn = SOUNDS.get(name)
            if fn is None:
                continue
            snd = fn(rng, sr)[:tail]
            start = max(0, int(t * sr) - pos)
            seg = buf[start:start + len(snd)]
            m = len(seg)
            pan = min(1.0, max(0.0, pan))
            seg[:, 0] += snd[:m] * g * math.cos(pan * math.pi / 2)
            seg[:, 1] += snd[:m] * g * math.sin(pan * math.pi / 2)
        carry = buf[n:n + tail].copy()
        out = np.tanh(buf[:n] * gain * 1.2)  # soft limiter, never clips harshly
        yield (out * 32000).astype("<i2").tobytes()
        pos += n
