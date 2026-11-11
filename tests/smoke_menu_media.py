"""물리 모니터·스피커 없이 타이틀 레이어와 실제 SDL 효과음을 검사한다."""

import argparse
from array import array
import ctypes
import json
import os
from pathlib import Path
import warnings
import wave
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_RENDER_DRIVER"] = "software"

import pico2d.pico2d as p

from game.front_end import FrontEnd
from game.layout import WIDTH, HEIGHT
from game.story_audio import AUDIO_ROOT, CUES, SDLStorySounds
from game.view import View
from tests.smoke_comic import interior, pixels
from tests.smoke_onboarding import capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--animation-dir", type=Path)
    args = parser.parse_args()
    for name in {name for cues in CUES for _, name in cues}:
        with wave.open(str(AUDIO_ROOT / f"{name}.wav")) as sound:
            assert (sound.getnchannels(), sound.getsampwidth(), sound.getframerate()) == (2, 2, 44100)
            samples = array('h', sound.readframes(sound.getnframes()))
            assert 1000 < max(map(abs, samples)) < 22000
            assert max(map(abs, samples[:2] + samples[-2:])) < 40
    p.open_canvas(WIDTH, HEIGHT)
    menu = display = None
    try:
        assert p.SDL_GetCurrentVideoDriver() == b"dummy"
        assert p.SDL_GetCurrentAudioDriver() == b"dummy"
        display, menu = View(), FrontEnd()
        backend = menu.audio.backend
        with patch.object(backend, "play", wraps=backend.play) as played:
            with patch("game.front_end.perf_counter", return_value=0):
                menu.activate("story")
            menu.update(.43)
            assert [call.args[0] for call in played.call_args_list] == ["hero_arrival"]
            channels = backend.active_channels()
            assert channels and all(p.Mix_Playing(channel) for channel in channels)
            with patch("game.front_end.perf_counter", return_value=.43):
                menu.activate("story_play")
            assert all(p.Mix_Paused(channel) for channel in channels)
            menu.update(10)
            assert menu.comic.elapsed == .43 and played.call_count == 1
            with patch("game.front_end.perf_counter", return_value=10):
                menu.activate("story_play")
            assert all(not p.Mix_Paused(channel) for channel in channels)
            menu.update(10.04)
            assert played.call_count == 1
            with patch("game.front_end.perf_counter", return_value=20):
                menu.activate("story_next")
                assert not backend.active_channels()
                menu.activate("story_next")
            for time, _ in CUES[2]:
                menu.update(20 + time + .01)
            assert [call.args[0] for call in played.call_args_list][1:] == [name for _, name in CUES[2]]
            with patch("game.front_end.perf_counter", return_value=30):
                menu.activate("story_next")
            for time, _ in CUES[3]:
                menu.update(30 + time + .01)
            assert len(backend.sounds) == 5 and not backend.disabled
            with patch("game.front_end.perf_counter", return_value=40):
                menu.activate("controls")
            assert not backend.active_channels()
            assert menu.audio.index is None

        unavailable = SDLStorySounds()
        with patch.object(p, "Mix_QuerySpec", return_value=0), warnings.catch_warnings(record=True) as reported:
            warnings.simplefilter("always")
            unavailable.play("hero_arrival")
            unavailable.play("hero_arrival")
            assert unavailable.disabled and len(reported) == 1
        unavailable.close()

        with patch("game.front_end.perf_counter", return_value=0):
            menu.activate("title")
        rendered = []
        button_bounds = [button.bounds for button in menu.buttons]
        for age in (0, .6, 2.0, 3.75, 4.2):
            menu.update(age)
            menu.draw(display)
            frame = pixels()
            if rendered:
                assert frame != rendered[-1]
                for bounds in button_bounds:
                    assert interior(frame, bounds) == interior(rendered[-1], bounds), "Title animation moved a button"
            rendered.append(frame)
            if args.capture_dir:
                capture(args.capture_dir / f"title-{age:.2f}.png")
        menu.draw(display)
        assert pixels() == rendered[-1], "Title rendering uses a hidden wall clock"
        with patch("game.front_end.perf_counter", return_value=10):
            menu.activate("story")
            menu.activate("title")
        menu.draw(display)
        assert pixels() == rendered[0], "Title replay did not reset"
        assert all(button.contains(((button.bounds[0] + button.bounds[2]) / 2,
                                    (button.bounds[1] + button.bounds[3]) / 2)) for button in menu.buttons)

        if args.animation_dir:
            args.animation_dir.mkdir(parents=True, exist_ok=True)
            frames = []
            for step in range(144):
                menu.title_elapsed = step / 24
                menu.draw(display)
                filename = f"title-{step:03d}.png"
                capture(args.animation_dir / filename)
                duration = round((step + 1) * 1000 / 24) - round(step * 1000 / 24)
                frames.append({"file": filename, "duration_ms": duration})
            (args.animation_dir / "frames.json").write_text(json.dumps(frames), encoding="utf-8")
        print("Menu media smoke OK: dummy video/audio, five PCM files, real mixer playback/pause/resume/stop, "
              "single timed cues, skip cleanup, silent device fallback, animated title layers, fixed buttons, replay reset.")
    finally:
        if menu:
            menu.close()
            assert not menu.audio.backend.sounds and not menu.images
        if display:
            display.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
