"""물리 창 없이 실제 SDL 렌더러로 네 컷 등장·입력·그림 보존을 검사한다."""

import argparse
import ctypes
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# 모니터를 건드리지 않는 캡처 전용 진입점이다. SDL 초기화 전에 지정한다.
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_RENDER_DRIVER"] = "software"

import pico2d.pico2d as p

from game.comic import PANEL_BOUNDS
from game.front_end import FrontEnd
from game.layout import WIDTH, HEIGHT
from game.story import PANEL_SECONDS
from game.view import View
from tests.smoke_onboarding import capture


def pixels():
    buffer = (ctypes.c_ubyte * (WIDTH * HEIGHT * 4))()
    assert p.SDL_RenderReadPixels(p.renderer, None, p.SDL_PIXELFORMAT_RGBA32,
                                 buffer, WIDTH * 4) == 0
    return bytes(buffer)


def interior(data, bounds):
    left, bottom, right, top = bounds
    return b"".join(data[(y * WIDTH + left + 8) * 4:(y * WIDTH + right - 8) * 4]
                    for y in range(HEIGHT - top + 8, HEIGHT - bottom - 8))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--animation-dir", type=Path)
    args = parser.parse_args()
    p.open_canvas(WIDTH, HEIGHT)
    display = menu = None
    try:
        assert p.SDL_GetCurrentVideoDriver() == b"dummy", "Physical display must not be used"
        display, menu = View(), FrontEnd()
        with patch("game.front_end.perf_counter", return_value=0):
            menu.activate("story")
        snapshots = []
        for index in range(4):
            menu.update(index * PANEL_SECONDS + 2.5)
            assert menu.story_page == index
            menu.draw(display)
            data = pixels()
            for previous, saved in enumerate(snapshots):
                assert interior(data, PANEL_BOUNDS[previous]) == saved, "Earlier panel changed"
            snapshots.append(interior(data, PANEL_BOUNDS[index]))
            for future in range(index + 1, 4):
                left, bottom, right, top = PANEL_BOUNDS[future]
                x, y = (left + right) // 2, HEIGHT - (bottom + top) // 2
                assert data[(y * WIDTH + x) * 4:(y * WIDTH + x) * 4 + 3] == bytes((248, 239, 220))
            assert not p.SDL_RenderIsClipEnabled(p.renderer)
            for image in menu.images.values():
                alpha = ctypes.c_ubyte()
                assert p.SDL_GetTextureAlphaMod(image.texture, ctypes.byref(alpha)) == 0
                assert alpha.value == 255
            if args.capture_dir:
                capture(args.capture_dir / f"panel-{index + 1:02d}.png")
        menu.update(1000)
        assert menu.screen == "story" and menu.comic.finished
        with patch("game.front_end.perf_counter", return_value=1000):
            menu.activate("story_play")
        assert menu.story_page == 0 and not menu.comic.paused
        menu.update(1000.1)
        menu.draw(display)
        first = pixels()
        menu.update(1000.4)
        menu.draw(display)
        assert interior(first, PANEL_BOUNDS[0]) != interior(pixels(), PANEL_BOUNDS[0]), "Missing entrance motion"

        def click(x, y):
            return menu.handle(SimpleNamespace(type=p.SDL_MOUSEBUTTONDOWN,
                                               button=p.SDL_BUTTON_LEFT, x=x, y=HEIGHT - 1 - y))

        assert click(1050, 300) is None and menu.story_page == 0  # 아직 공개하지 않은 컷
        with patch("game.front_end.perf_counter", return_value=1000.4):
            menu.activate("story_play")
        before = menu.comic.elapsed
        menu.update(1020)
        assert menu.comic.elapsed == before
        with patch("game.front_end.perf_counter", return_value=1020):
            menu.activate("story_play")
        menu.update(1020.2)
        assert menu.comic.elapsed > before
        with patch("game.front_end.perf_counter", return_value=1020.2):
            assert click(520, 700) == "story_next" and menu.story_page == 1
            menu.selected = 2  # Space는 건너뛰기 포커스와 관계없이 다음 컷이다.
            menu.handle(SimpleNamespace(type=p.SDL_KEYDOWN, key=p.SDLK_SPACE))
            assert menu.story_page == 2 and menu.screen == "story"
            menu.activate("story_back")
            assert menu.story_page == 1 and menu.comic.paused
            menu.activate("title")
            menu.activate("story")
            assert menu.story_page == 0 and not menu.comic.paused

        if args.animation_dir:
            args.animation_dir.mkdir(parents=True, exist_ok=True)
            with patch("game.front_end.perf_counter", return_value=0):
                menu.activate("story")
            frames = []
            for index in range(4):
                for step in range(18):
                    menu.update(index * PANEL_SECONDS + step * 0.15)
                    menu.draw(display)
                    filename = f"frame-{len(frames):03d}.png"
                    capture(args.animation_dir / filename)
                    frames.append({"file": filename, "duration_ms": 150 if step < 17 else 3950})
            (args.animation_dir / "frames.json").write_text(json.dumps(frames), encoding="utf-8")
        print("Comic smoke OK: dummy/software rendering, four automatic reveals, earlier panels unchanged, "
              "future panels hidden, entrance motion, pause/resume/replay, pointer/Space/back, texture/clip restoration.")
    finally:
        if menu:
            menu.close()
        if display:
            display.close()
        p.close_canvas()


if __name__ == "__main__":
    main()

