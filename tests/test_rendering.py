import subprocess

import numpy as np
import pytest

from catvid.prey import PREY_NAMES
from catvid.backgrounds import BACKGROUND_NAMES
from catvid.renderer import Scene, ffmpeg_exe, render_video
from catvid.settings import Settings
from catvid.sounds import SOUNDS, stream_audio

SMALL = (320, 180)


@pytest.mark.parametrize("prey", PREY_NAMES)
def test_every_prey_type_draws(prey):
    scene = Scene(Settings(prey_type=prey, prey_count=3), seed=1, size=SMALL)
    first = scene.render().copy()
    for _ in range(60):
        scene.step()
    frame = scene.render()
    assert frame.shape == (180, 320, 3)
    assert not np.array_equal(first, frame), "prey should move or animate"


@pytest.mark.parametrize("bg", BACKGROUND_NAMES)
def test_every_background_draws(bg):
    scene = Scene(Settings(background=bg, custom_color="#203040"), seed=2, size=SMALL)
    assert scene.bg.size == SMALL


def test_same_seed_same_video():
    a = Scene(Settings(), seed=7, size=SMALL)
    b = Scene(Settings(), seed=7, size=SMALL)
    for _ in range(90):
        a.step()
        b.step()
    assert np.array_equal(a.render(), b.render())


def test_sounds_are_finite_and_short():
    rng = np.random.default_rng(0)
    for fn in SOUNDS.values():
        snd = fn(rng)
        assert 0 < len(snd) <= 2 * 44100
        assert np.isfinite(snd).all() and np.abs(snd).max() <= 1.0


def test_audio_stream_has_exact_length():
    events = [(0.5, "Rustling", 1.0, 0.2), (6.0, "Mouse squeaks", 1.0, 0.8)]
    data = b"".join(stream_audio(events, 7.0, 80, np.random.default_rng(0)))
    assert len(data) == 7 * 44100 * 2 * 2


def test_render_short_video_with_sound(tmp_path):
    out = tmp_path / "clip.mp4"
    s = Settings(resolution="720p", sound=True, sound_types=["Rustling", "Scratching"])
    result = render_video(s, seconds=2, out_path=out)
    assert out.exists() and out.stat().st_size > 1000
    assert result.seed == s.seed
    info = subprocess.run([ffmpeg_exe(), "-i", str(out)], capture_output=True, text=True).stderr
    assert "1280x720" in info and "Audio" in info
    assert not list(tmp_path.glob("*.tmp.mp4")), "temporary files are cleaned up"
