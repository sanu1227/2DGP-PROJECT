"""모니터·스피커 없이 실제 게임 루프로 로고 순서, 페이드, 글자 등장과 종료를 검사한다."""

import argparse
import ctypes
from dataclasses import replace
import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_RENDER_DRIVER"] = "software"

import pico2d.pico2d as p

from game import view
from game.front_end import FrontEnd
from game.levels import load_levels
from game.logo_mode import LOGO_DURATIONS, fade_to_black, sample_letter
from tests.smoke_comic import interior, pixels
from tests.smoke_onboarding import capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--animation-dir", type=Path)
    args = parser.parse_args()
    menus, current, now = [], [None], [0.0]
    original_events, original_update = p.get_events, p.update_canvas
    total = sum(LOGO_DURATIONS)

    class ObservedFrontEnd(FrontEnd):
        def __init__(self, show_title=True):
            super().__init__(show_title)
            menus.append(self)

    def run(timeline, *, show_title=True, record=False):
        iterator = iter(timeline)
        current[0] = None

        def events():
            original_events()
            current[0] = next(iterator)
            now[0], keys, _, _ = current[0]
            result = []
            for key in keys:
                event = p.Event(p.SDL_QUIT if key == "close" else p.SDL_KEYDOWN)
                if key != "close":
                    event.key = key
                result.append(event)
            return result

        def update():
            assert p.SDL_GetCurrentVideoDriver() == b"dummy"
            assert p.SDL_GetCurrentAudioDriver() == b"dummy"
            if current[0] is None:
                original_update()
                return
            age, _, expected, name = current[0]
            menu = menus[-1]
            actual = f"logo:{menu.logos.index}" if menu.screen == "logo" else menu.screen
            assert actual == expected, (age, actual, expected)
            if record:
                frame = pixels()
                if age == 0:
                    assert not any(frame[0::4]) and not any(frame[1::4]) and not any(frame[2::4])
                if name == "university":
                    assert frame[:3] == b"\xff\xff\xff"
                    assert len(set(interior(frame, (450, 190, 1150, 770)))) > 100
                if name in ("2d-first", "2dgp-complete"):
                    index = 0 if name == "2d-first" else 1
                    if index == 0:
                        assert "logo_2d" in menu.images and "logo_gp" not in menu.images
                    def hidden(age, which):
                        pose = sample_letter(age, which)
                        return replace(pose, opacity=0) if which == index else pose
                    with patch("game.logo_mode.sample_letter", side_effect=hidden):
                        menu.draw(None)
                    without = pixels()
                    region = (350, 345, 800, 680) if index == 0 else (800, 345, 1250, 680)
                    assert sum(a != b for a, b in zip(interior(frame, region), interior(without, region))) > 10000
                    if index == 0:
                        assert interior(frame, (815, 345, 1250, 680)) == interior(without, (815, 345, 1250, 680))
                    menu.draw(None)
                    assert pixels() == frame, "Letter rendering changed hidden animation state"
                    for key in ("logo_2d", "logo_gp"):
                        if key in menu.images:
                            alpha = ctypes.c_ubyte()
                            p.SDL_GetTextureAlphaMod(menu.images[key].texture, ctypes.byref(alpha))
                            assert alpha.value == 255
                if args.capture_dir and name:
                    capture(args.capture_dir / f"{name}.png")
                if args.animation_dir:
                    capture(args.animation_dir / f"frame-{len(recorded):04d}.png")
                    recorded.append({"file": f"frame-{len(recorded):04d}.png", "duration_ms": 1000 / 24})
            original_update()

        with patch.object(view, "FrontEnd", ObservedFrontEnd), \
                patch.object(view, "perf_counter", side_effect=lambda: now[0]), \
                patch("game.front_end.perf_counter", side_effect=lambda: now[0]), \
                patch.object(p, "get_events", events), patch.object(p, "update_canvas", update):
            view.run(load_levels(), show_title=show_title)
        assert not menus[-1].images
        assert next(iterator, None) is None

    recorded = []
    if args.animation_dir:
        args.animation_dir.mkdir(parents=True, exist_ok=True)
        marks = {24: "university", 65: "2d-first", 77: "gp-arrival", 89: "2dgp-complete", 139: "title"}
        timeline = [(i / 24, ["close"] if i == 151 else [],
                     f"logo:{int(i / 24 >= LOGO_DURATIONS[0])}" if i / 24 < total else "title", marks.get(i))
                    for i in range(152)]
    else:
        timeline = [(0, [], "logo:0", None), (.175, [], "logo:0", "school-fade"),
                    (1, [], "logo:0", "university"), (2.2, [], "logo:1", None),
                    (2.7, [], "logo:1", "2d-first"), (3.2, [], "logo:1", "gp-arrival"),
                    (3.7, [], "logo:1", "2dgp-complete"), (total + .01, [], "title", None),
                    (5.8, ["close"], "title", "title")]
    run(timeline, record=True)
    if args.animation_dir:
        (args.animation_dir / "frames.json").write_text(json.dumps(recorded, indent=2), encoding="utf-8")
    # 같은 입력 묶음이 다음 로고나 게임 시작으로 연쇄 처리되지 않아야 한다.
    run([(0, [p.SDLK_RETURN, p.SDLK_RETURN], "logo:1", None),
         (.1, [p.SDLK_SPACE, p.SDLK_SPACE], "title", None),
         (.2, [p.SDLK_RETURN, "close"], "story", None)])
    run([(0, ["close"], "logo:0", None)])
    run([(0, [p.SDLK_SPACE, "close"], "logo:1", None)])
    run([(0, [p.SDLK_ESCAPE, "close"], "title", None)])
    run([(0, ["close"], "playing", None)], show_title=False)
    assert not any(key.startswith("logo_") for key in menus[-1].images)

    # 페이드 함수 자체의 SDL 상태 복구도 확인한다.
    p.open_canvas(view.WIDTH, view.HEIGHT)
    try:
        p.SDL_SetRenderDrawColor(p.renderer, 12, 34, 56, 78)
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_NONE)
        fade_to_black(.5)
        rgba, blend = [ctypes.c_ubyte() for _ in range(4)], ctypes.c_int()
        p.SDL_GetRenderDrawColor(p.renderer, *(ctypes.byref(value) for value in rgba))
        p.SDL_GetRenderDrawBlendMode(p.renderer, ctypes.byref(blend))
        assert [value.value for value in rgba] == [12, 34, 56, 78]
        assert blend.value == p.SDL_BLENDMODE_NONE
    finally:
        p.close_canvas()
    print("Native logo smoke OK: official logo, 2D then GP pixels, fades, automatic title, input isolation, close on both cards, stage bypass, SDL/texture state, cleanup.")


if __name__ == "__main__":
    main()
