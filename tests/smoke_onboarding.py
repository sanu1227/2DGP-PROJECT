"""실제 SDL로 첫 실행 화면 전환을 검사한다. --capture-dir로 화면도 저장한다."""

import argparse
from collections import deque
import ctypes
from pathlib import Path
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.front_end import FrontEnd
from game.levels import load_levels
from game.model import Game


def capture(path):
    surface = p.SDL_CreateRGBSurfaceWithFormat(0, view.WIDTH, view.HEIGHT, 32, p.SDL_PIXELFORMAT_RGBA32)
    if not surface:
        raise RuntimeError("SDL surface 생성 실패")
    try:
        assert p.SDL_RenderReadPixels(p.renderer, None, surface.contents.format.contents.format,
                                     surface.contents.pixels, surface.contents.pitch) == 0
        path.parent.mkdir(parents=True, exist_ok=True)
        assert p.IMG_SavePNG(surface, str(path).encode("utf-8")) == 0
    finally:
        p.SDL_FreeSurface(surface)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    args = parser.parse_args()
    games, menus = [], []

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            games.append(self)

    class ObservedFrontEnd(FrontEnd):
        def __init__(self, show_title=True):
            super().__init__(show_title)
            menus.append(self)

    # 각 tuple은 입력 묶음, 표시 화면, 행동 수, 선택적인 캡처 이름이다.
    steps = deque([
        ([], "title", 0, "title"),
        ([p.SDLK_d, p.SDLK_e, p.SDLK_q, p.SDLK_6], "title", 0, None),
        ([("left", 60, 60)], "title", 0, None),
        ([("right", 320, 326)], "title", 0, None),
        ([("left", 320, 326), ("left", 1274, 128)], "controls", 0, "controls"),
        ([p.SDLK_d, p.SDLK_e, p.SDLK_r, p.SDLK_6, p.SDLK_F2], "controls", 0, None),
        ([p.SDLK_ESCAPE], "title", 0, None),
        ([p.SDLK_TAB, p.SDLK_UP, p.SDLK_RETURN, p.SDLK_RETURN], "controls", 0, None),
        ([("left", 230, 128)], "title", 0, None),
        ([p.SDLK_SPACE], "controls", 0, None),
        ([("left", 1274, 128), p.SDLK_d], "playing", 0, "room-01"),
        ([p.SDLK_d], "playing", 1, None),
        ([p.SDLK_ESCAPE], "playing", 1, None),
    ])
    original_events, original_update = p.get_events, p.update_canvas
    current = None

    def events():
        nonlocal current
        current = steps.popleft()
        for value in current[0]:
            event = p.SDL_Event()
            window = p.SDL_GetWindowID(p.window)
            if isinstance(value, int):
                event.type = p.SDL_KEYDOWN
                event.key.windowID, event.key.state = window, p.SDL_PRESSED
                event.key.repeat, event.key.keysym.sym = 0, value
            else:
                kind, x, y = value
                event.type = p.SDL_MOUSEBUTTONDOWN
                event.button.windowID, event.button.state = window, p.SDL_PRESSED
                event.button.button = p.SDL_BUTTON_LEFT if kind == "left" else p.SDL_BUTTON_RIGHT
                event.button.x, event.button.y = x, view.HEIGHT - 1 - y
            assert p.SDL_PushEvent(ctypes.byref(event)) == 1
        return original_events()

    def update():
        if current is None:
            original_update()
            return
        _, screen, moves, filename = current
        assert menus[-1].screen == screen, (menus[-1].screen, screen)
        assert games[-1].state.moves == moves, (games[-1].state.moves, moves)
        assert games[-1].level.id == "stage_01"
        if args.capture_dir and filename:
            capture(args.capture_dir / f"{filename}.png")
        original_update()

    with patch.object(view, "Game", ObservedGame), patch.object(view, "FrontEnd", ObservedFrontEnd), \
            patch.object(p, "get_events", events), patch.object(p, "update_canvas", update):
        view.run(load_levels())
    assert not steps
    print("Native onboarding smoke OK: title, controls, mouse/keyboard, back, input isolation, first room, Escape.")


if __name__ == "__main__":
    main()
