"""Named presets stored in a JSON file next to app.py."""

from __future__ import annotations

import json
from pathlib import Path

from .settings import Settings

PRESETS_FILE = Path(__file__).resolve().parent.parent / "presets.json"

# Shipped presets, always available. Your own presets are saved alongside them.
BUILTIN_PRESETS = {
    "Ambush hunter (default)": Settings().to_dict(),
    "Busy bugs": Settings(prey_type="Bugs", prey_count=6, prey_size=1.6, speed=1.2, pause_frequency=60,
                          pause_duration=2.5, twitch=80, dart_frequency=70, hide_objects="Leaves",
                          background="Wooden floor", sound_types=["Scratching", "Rustling"]).to_dict(),
    "Birds in the grass": Settings(prey_type="Birds", prey_count=3, prey_size=1.4, background="Grass",
                                   hide_objects="Grass", sound_types=["Bird chirps", "Rustling"]).to_dict(),
    "Pond fish": Settings(prey_type="Fish", prey_count=4, prey_size=1.3, speed=0.8, pause_frequency=45,
                          background="Water", hide_objects="Rocks", sound_types=["Rustling"],
                          volume=35).to_dict(),
    "Grasshopper (projector)": Settings(prey_type="Grasshopper", prey_count=1, prey_size=1.6, speed=1.4,
                                        pause_frequency=30, pause_duration=1.5, twitch=60, dart_frequency=75,
                                        hiding=False, background="Black (projector)",
                                        sound_types=["Grasshopper clicks", "Rustling"]).to_dict(),
    "Laser chase": Settings(prey_type="Laser dot", prey_count=1, prey_size=1.5, speed=1.4, pause_frequency=60,
                            pause_duration=2.0, dart_frequency=85, hiding=False,
                            sound=False).to_dict(),
}


def load_presets(path: Path = PRESETS_FILE) -> dict[str, dict]:
    presets = dict(BUILTIN_PRESETS)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            presets.update({str(k): v for k, v in data.items() if isinstance(v, dict)})
    except (OSError, ValueError):
        pass
    return presets


def _user_presets(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_preset(name: str, settings: Settings, path: Path = PRESETS_FILE) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Please type a name for the preset.")
    data = _user_presets(path)
    data[name] = settings.validated().to_dict()
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def delete_preset(name: str, path: Path = PRESETS_FILE) -> bool:
    data = _user_presets(path)
    if name in data:
        del data[name]
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return True
    return False


def get_preset(name: str, path: Path = PRESETS_FILE) -> Settings | None:
    data = load_presets(path).get(name)
    return Settings.from_dict(data) if data is not None else None
