"""Regenerate the small preview GIFs used in the README.

Run from the project folder:  python scripts/make_readme_previews.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from catvid.renderer import Scene  # noqa: E402
from catvid.settings import FPS, Settings  # noqa: E402

PREVIEWS = {
    "preview_mice.gif": (Settings(prey_type="Mice", prey_count=3, background="Grass", hide_objects="Mixed"), 3, 2.0),
    "preview_mixed.gif": (Settings(prey_type="Mixed", prey_count=5, background="Night sky",
                                   hide_objects="Leaves", hide_spots=3), 11, 1.0),
}
SIZE = (1280, 720)      # rendered size
GIF_SIZE = (480, 270)   # saved size
SECONDS = 6
GIF_FPS = 12


def make(name, settings, seed, warmup):
    scene = Scene(settings, seed, SIZE)
    for _ in range(int(warmup * FPS)):
        scene.step()
    frames = []
    every = FPS // GIF_FPS
    for i in range(SECONDS * FPS):
        scene.step()
        if i % every == 0:
            img = Image.fromarray(scene.render().copy()).resize(GIF_SIZE, Image.LANCZOS)
            frames.append(img)
    # one shared palette for all frames keeps colours (and blues) stable
    sample = frames[:: max(1, len(frames) // 8)]
    sheet = Image.new("RGB", (GIF_SIZE[0], GIF_SIZE[1] * len(sample)))
    for k, f in enumerate(sample):
        sheet.paste(f, (0, GIF_SIZE[1] * k))
    palette = sheet.quantize(colors=200, method=Image.Quantize.FASTOCTREE)
    frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
    out = ROOT / "docs" / name
    out.parent.mkdir(exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=1000 // GIF_FPS, loop=0, optimize=True)
    print(f"{out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    for name, (s, seed, warm) in PREVIEWS.items():
        make(name, s, seed, warm)
