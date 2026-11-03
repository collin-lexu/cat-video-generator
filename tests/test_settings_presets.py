import random
from datetime import datetime

from catvid import presets
from catvid.settings import Settings, build_filename, normalize_color, randomize


def test_defaults_suit_an_ambush_hunter():
    s = Settings()
    assert s.resolution == "1080p"
    assert s.hiding and s.pause_frequency >= 50 and s.twitch >= 40 and s.dart_frequency >= 40


def test_validation_clamps_out_of_range_values():
    s = Settings(length_minutes=999, prey_count=0, prey_size=10, volume=-5, prey_type="Dragons",
                 sound_types=["Rustling", "Bogus"]).validated()
    assert s.length_minutes == 180
    assert s.prey_count == 1
    assert s.prey_size == 2.5
    assert s.volume == 0
    assert s.prey_type == "Mice"
    assert s.sound_types == ["Rustling"]


def test_color_formats():
    assert normalize_color("#AABBCC") == "#aabbcc"
    assert normalize_color("rgba(255, 0, 16.4, 1)") == "#ff0010"
    assert normalize_color("not a color") == "#1b1f2e"


def test_filename_is_descriptive():
    s = Settings(prey_type="Laser dot", background="Night sky")
    name = build_filename(s, 3600, 42, datetime(2026, 1, 2, 3, 4))
    assert name == "laser-dot_night-sky_1h_2026-01-02_0304_seed42.mp4"
    assert "_90min_" not in build_filename(s, 5400, 1)
    assert "_1h30m_" in build_filename(s, 5400, 1)


def test_randomize_keeps_length_and_resolution():
    base = Settings(length_minutes=7, resolution="720p")
    r = randomize(base, random.Random(1))
    assert r.length_minutes == 7 and r.resolution == "720p"
    assert r == r.validated()


def test_presets_round_trip(tmp_path):
    path = tmp_path / "presets.json"
    s = Settings(prey_type="Fish", background="Water", prey_count=5)
    presets.save_preset("Pond", s, path)
    assert "Pond" in presets.load_presets(path)
    assert presets.get_preset("Pond", path) == s.validated()
    assert presets.delete_preset("Pond", path)
    assert "Pond" not in presets.load_presets(path)
    # built in presets are always there and valid
    for name in presets.BUILTIN_PRESETS:
        assert presets.get_preset(name, path) is not None
