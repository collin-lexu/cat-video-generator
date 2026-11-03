"""Cat Video Generator control panel.

Run with:  python app.py
A control panel opens in your web browser.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import gradio as gr

from catvid import presets as preset_store
from catvid.backgrounds import BACKGROUND_NAMES
from catvid.covers import COVER_NAMES
from catvid.prey import PREY_NAMES
from catvid.renderer import OUTPUT_DIR, RenderCancelled, render_video
from catvid.settings import (MAX_LENGTH_MIN, MIN_LENGTH_MIN, PREVIEW_SECONDS, RESOLUTIONS, Settings,
                             randomize)
from catvid.sounds import SOUND_NAMES

PREVIEW_DIR = OUTPUT_DIR / "previews"
CANCEL = threading.Event()

# The order of these names matches the order of the input widgets below.
FIELDS = [
    "length_minutes", "resolution",
    "prey_type", "prey_count", "prey_size", "speed",
    "pause_frequency", "pause_duration", "twitch", "dart_frequency",
    "hiding", "hide_objects", "hide_spots", "hide_frequency",
    "background", "custom_color",
    "sound", "volume", "sound_types",
    "seed", "fixed_seed",
]


def to_settings(*values) -> Settings:
    return Settings.from_dict(dict(zip(FIELDS, values)))


def to_values(s: Settings) -> list:
    d = s.validated().to_dict()
    return [d[f] for f in FIELDS]


def _cleanup_previews(keep: int = 3):
    files = sorted(PREVIEW_DIR.glob("preview_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def _run(values, seconds, out_path, progress):
    CANCEL.clear()
    s = to_settings(*values)

    def report(frac, msg):
        progress(frac, desc=msg)

    try:
        result = render_video(s, seconds=seconds, out_path=out_path, progress=report, cancel=CANCEL)
    except RenderCancelled:
        return None, "Stopped. No video was saved.", gr.update()
    except Exception as exc:  # show the problem in the panel instead of crashing
        return None, f"Something went wrong: {exc}", gr.update()
    return result, None, gr.update(value=result.seed)


def do_preview(*values, progress=gr.Progress()):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_previews()
    out = PREVIEW_DIR / f"preview_{int(time.time())}.mp4"
    result, err, seed_update = _run(values, PREVIEW_SECONDS, out, progress)
    if err:
        return None, err, seed_update
    msg = (f"Preview ready ({PREVIEW_SECONDS} seconds, rendered in {result.elapsed:.1f}s). "
           f"Seed {result.seed}. The full video with the same seed starts exactly like this.")
    return str(result.path), msg, seed_update


def do_render(*values, progress=gr.Progress()):
    result, err, seed_update = _run(values, None, None, progress)
    if err:
        return None, err, seed_update
    minutes = result.elapsed / 60
    msg = (f"Saved: {result.path}\n"
           f"Length {result.seconds / 60:.0f} min, rendered in {minutes:.1f} min. Seed {result.seed} "
           f"(tick 'Use fixed seed' with this number to make the same video again).")
    return str(result.path), msg, seed_update


def do_stop():
    CANCEL.set()
    return "Stopping..."


def do_randomize(*values):
    return to_values(randomize(to_settings(*values))) + ["Randomized! Click Preview to see it."]


def do_load_preset(name):
    s = preset_store.get_preset(name) if name else None
    if s is None:
        return [gr.update() for _ in FIELDS] + ["Pick a preset from the list first."]
    return to_values(s) + [f"Loaded preset '{name}'."]


def do_save_preset(name, *values):
    try:
        preset_store.save_preset(name or "", to_settings(*values))
    except ValueError as exc:
        return gr.update(), str(exc)
    names = list(preset_store.load_presets())
    return gr.update(choices=names, value=name.strip()), f"Saved preset '{name.strip()}'."


def do_delete_preset(name):
    if name in preset_store.BUILTIN_PRESETS:
        return gr.update(), "Built in presets can't be deleted."
    ok = preset_store.delete_preset(name or "")
    names = list(preset_store.load_presets())
    return gr.update(choices=names, value=names[0]), (f"Deleted '{name}'." if ok else "Nothing to delete.")


def do_open_folder():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(OUTPUT_DIR)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(OUTPUT_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])
    except Exception:
        pass
    return f"Your videos are in: {OUTPUT_DIR}"


def build_ui() -> gr.Blocks:
    d = Settings()
    with gr.Blocks(title="Cat Video Generator", analytics_enabled=False) as ui:
        gr.Markdown("# 🐱 Cat Video Generator\nAdjust the settings, click **Preview** for a quick "
                    f"{PREVIEW_SECONDS} second clip, then **Render** the full video. "
                    "Defaults are tuned for ambush hunters: prey that freezes, twitches, hides, peeks and darts.")
        with gr.Row():
            with gr.Column(scale=3):
                with gr.Accordion("📹 Video", open=True):
                    length = gr.Slider(MIN_LENGTH_MIN, MAX_LENGTH_MIN, value=d.length_minutes, step=1,
                                       label="Video length (minutes)", info="1 minute up to 3 hours")
                    resolution = gr.Radio(list(RESOLUTIONS), value=d.resolution, label="Resolution (30 fps)")
                with gr.Accordion("🐭 Prey", open=True):
                    prey_type = gr.Dropdown(PREY_NAMES, value=d.prey_type, label="Prey type")
                    prey_count = gr.Slider(1, 12, value=d.prey_count, step=1, label="Number of prey on screen")
                    prey_size = gr.Slider(0.5, 2.5, value=d.prey_size, step=0.1, label="Prey size")
                    speed = gr.Slider(0.25, 3.0, value=d.speed, step=0.05, label="Movement speed")
                with gr.Accordion("🎯 Behaviour", open=True):
                    pause_frequency = gr.Slider(0, 100, value=d.pause_frequency, step=1,
                                                label="How often prey stops and sits still (%)")
                    pause_duration = gr.Slider(0.5, 20, value=d.pause_duration, step=0.5,
                                               label="How long it stays still (seconds)")
                    twitch = gr.Slider(0, 100, value=d.twitch, step=1,
                                       label="Twitching and wiggling while resting (%)")
                    dart_frequency = gr.Slider(0, 100, value=d.dart_frequency, step=1,
                                               label="How often it darts off quickly (%)")
                with gr.Accordion("🌿 Hiding", open=True):
                    hiding = gr.Checkbox(value=d.hiding, label="Prey can hide behind objects and peek out")
                    hide_objects = gr.Dropdown(COVER_NAMES, value=d.hide_objects, label="Hiding objects")
                    hide_spots = gr.Slider(1, 8, value=d.hide_spots, step=1, label="Number of hiding spots")
                    hide_frequency = gr.Slider(0, 100, value=d.hide_frequency, step=1,
                                               label="How often prey goes to hide (%)")
                with gr.Accordion("🖼 Background", open=True):
                    background = gr.Dropdown(BACKGROUND_NAMES, value=d.background, label="Background")
                    custom_color = gr.ColorPicker(value=d.custom_color,
                                                  label="Custom color (used when Background is 'Custom color')")
                with gr.Accordion("🔊 Sound", open=True):
                    sound = gr.Checkbox(value=d.sound, label="Sound on")
                    volume = gr.Slider(0, 100, value=d.volume, step=1, label="Volume")
                    sound_types = gr.CheckboxGroup(SOUND_NAMES, value=d.sound_types, label="Sound types")
                with gr.Accordion("🎲 Seed (recreate a video)", open=False):
                    gr.Markdown("With a fixed seed, the same settings always make exactly the same video.")
                    seed = gr.Number(value=d.seed, precision=0, label="Seed")
                    fixed_seed = gr.Checkbox(value=d.fixed_seed,
                                             label="Use fixed seed (untick for a new surprise each time)")

            with gr.Column(scale=4):
                video = gr.Video(label="Video", autoplay=True, loop=True, height=420)
                with gr.Row():
                    preview_btn = gr.Button("▶ Preview (15 s)", variant="secondary")
                    render_btn = gr.Button("🎬 Render full video", variant="primary")
                with gr.Row():
                    random_btn = gr.Button("🎲 Randomize")
                    stop_btn = gr.Button("⏹ Stop")
                    folder_btn = gr.Button("📂 Open output folder")
                status = gr.Textbox(label="Status", lines=3, interactive=False)
                with gr.Accordion("💾 Presets", open=True):
                    with gr.Row(equal_height=True):
                        preset_list = gr.Dropdown(list(preset_store.load_presets()),
                                                  value="Ambush hunter (default)", label="Saved presets", scale=3)
                        load_btn = gr.Button("Load", scale=1, min_width=80)
                        delete_btn = gr.Button("Delete", scale=1, min_width=80)
                    with gr.Row(equal_height=True):
                        preset_name = gr.Textbox(label="New preset name", placeholder="e.g. Luna's favourite",
                                                 scale=3)
                        save_btn = gr.Button("Save current settings", scale=2, min_width=80)

        inputs = [length, resolution, prey_type, prey_count, prey_size, speed,
                  pause_frequency, pause_duration, twitch, dart_frequency,
                  hiding, hide_objects, hide_spots, hide_frequency,
                  background, custom_color, sound, volume, sound_types, seed, fixed_seed]
        assert len(inputs) == len(FIELDS)

        preview_btn.click(do_preview, inputs, [video, status, seed], concurrency_id="render",
                          concurrency_limit=1)
        render_btn.click(do_render, inputs, [video, status, seed], concurrency_id="render",
                         concurrency_limit=1)
        stop_btn.click(do_stop, None, status)
        random_btn.click(do_randomize, inputs, inputs + [status])
        load_btn.click(do_load_preset, preset_list, inputs + [status])
        save_btn.click(do_save_preset, [preset_name] + inputs, [preset_list, status])
        delete_btn.click(do_delete_preset, preset_list, [preset_list, status])
        folder_btn.click(do_open_folder, None, status)
    return ui


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    build_ui().queue().launch(inbrowser=True, allowed_paths=[str(OUTPUT_DIR)])
