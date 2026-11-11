"""실제 SDL로 첫 실행 화면 전환을 검사한다. --capture-dir로 화면도 저장한다."""

import argparse
from collections import deque
import ctypes
from pathlib import Path
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.front_end import FrontEnd, DIALOGUE_BOUNDS, DIALOGUE_SIZE
from game.story import STORY
from game.levels import load_levels
from game.model import Game
from tests.test_game import SOLUTIONS


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
    games, menus, displays = [], [], []
    checked_glyphs = set()
    original_initialize, original_text = view.View.__init__, view.View.text

    def initialize(display):
        original_initialize(display)
        displays.append(display)
        # 세 줄 대사가 화면 안뿐 아니라 실제 말풍선의 여백 안에 들어가야 한다.
        for page in STORY:
            for bounds, words in zip(DIALOGUE_BOUNDS, page.dialogue):
                for value in words[1:]:
                    width = ctypes.c_int()
                    p.TTF_SizeUTF8(display.fonts[DIALOGUE_SIZE].font, value.encode("utf-8"),
                                   ctypes.byref(width), None)
                    assert width.value <= bounds[2] - bounds[0] - 36, (value, width.value)

    def checked_text(display, x, y, value, size=18, color=view.INK):
        for character in str(value):
            if character.isprintable() and (size, character) not in checked_glyphs:
                assert p.TTF_GlyphIsProvided(display.fonts[size].font, ord(character)), (size, character, value)
                checked_glyphs.add((size, character))
        if menus and menus[-1].screen != "playing":
            width = ctypes.c_int()
            p.TTF_SizeUTF8(display.fonts[size].font, str(value).encode("utf-8"), ctypes.byref(width), None)
            assert 0 <= x and x + width.value <= view.WIDTH, (value, x, width.value)
            assert size / 2 <= y <= view.HEIGHT - size / 2, (value, y)
        original_text(display, x, y, value, size, color)

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
        ([("left", 600, 188)], "title", 0, None),
        ([("right", 800, 227)], "title", 0, None),
        ([("left", 800, 227), ("left", 1390, 72)], "story:0", 0, "story-01"),
        ([p.SDLK_d, p.SDLK_e, p.SDLK_r, p.SDLK_6, p.SDLK_F2], "story:0", 0, None),
        ([p.SDLK_RIGHT], "story:1", 0, "story-02"),
        ([p.SDLK_LEFT], "story:0", 0, None),
        ([("left", 1390, 72)], "story:1", 0, None),
        ([p.SDLK_RETURN], "story:2", 0, "story-03"),
        ([p.SDLK_SPACE], "story:3", 0, "story-04"),
        ([p.SDLK_RETURN], "story:4", 0, "story-05"),
        ([p.SDLK_LEFT], "story:3", 0, None),
        ([p.SDLK_RIGHT], "story:4", 0, None),
        ([("left", 1390, 72)], "story:5", 0, "story-06"),
        ([p.SDLK_SPACE], "story:6", 0, "story-07"),
        ([p.SDLK_RIGHT], "story:7", 0, "story-08"),
        ([p.SDLK_RETURN], "controls:0", 0, "repair-guide"),
        ([p.SDLK_d, p.SDLK_e, p.SDLK_r, p.SDLK_6, p.SDLK_F2], "controls:0", 0, None),
        ([("left", 1390, 72)], "controls:1", 0, "controls"),
        ([("left", 210, 72)], "controls:0", 0, None),
        ([("left", 210, 72)], "story:7", 0, None),
        ([p.SDLK_ESCAPE], "title", 0, None),
        ([p.SDLK_TAB, p.SDLK_UP, p.SDLK_RETURN, p.SDLK_RETURN], "story:0", 0, None),
        ([("left", 1460, 900)], "controls:0", 0, None),
        ([p.SDLK_ESCAPE], "title", 0, None),
        ([p.SDLK_SPACE], "story:0", 0, None),
        ([("left", 210, 72)], "title", 0, None),
        ([p.SDLK_RETURN], "story:0", 0, None),
        ([("left", 1460, 900)], "controls:0", 0, None),
        ([p.SDLK_RETURN], "controls:1", 0, None),
        ([("left", 1390, 72), p.SDLK_d], "playing", 0, None),
        ([p.SDLK_d], "playing", 1, None),
        ([p.SDLK_r], "playing", 0, None),
        ([("left", 100, 700)], "playing", 0, None),
    ])
    keys = {"up": p.SDLK_w, "down": p.SDLK_s, "left": p.SDLK_a,
            "right": p.SDLK_d, "interact": p.SDLK_e}
    for moves, action in enumerate(SOLUTIONS["stage_01"], 1):
        steps.append(([keys[action]], "playing", moves, None))
        if action == "interact":
            steps.append(([p.SDLK_z], "playing", moves - 1, None))
            steps.append(([keys[action]], "playing", moves, None))
    steps.extend([
        ([p.SDLK_BACKSPACE], "playing", 18, None),
        ([p.SDLK_a], "playing", 19, None),
        ([p.SDLK_SPACE], "playing", 0, None, "stage_02"),
        ([p.SDLK_1], "playing", 0, None),
        ([p.SDLK_ESCAPE], "playing", 0, None),
    ])
    original_events, original_update = p.get_events, p.update_canvas
    current = None

    def events():
        nonlocal current
        # 창을 다시 열 때 발생하는 실제 마우스 이동이 버튼 포커스를 바꾸지 않게 한다.
        original_events()
        current = steps.popleft()
        for value in current[0]:
            event = p.SDL_Event()
            window = p.SDL_GetWindowID(p.window)
            if value == "close":
                event.type = p.SDL_QUIT
            elif isinstance(value, int):
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
        _, screen, moves, filename, *room = current
        menu = menus[-1]
        actual = menu.screen
        if actual == "story":
            actual += f":{menu.story_page}"
            assert menu.buttons[0].label == ("작업 안내" if menu.story_page == len(STORY) - 1 else "다음 이야기")
        elif actual == "controls":
            actual += f":{menu.guide_page}"
        assert actual == screen, (actual, screen, current[0])
        assert games[-1].state.moves == moves, (games[-1].state.moves, moves)
        assert games[-1].level.id == (room[0] if room else "stage_01")
        if screen == "playing":
            display = displays[-1]
            if room == ["stage_02"]:
                assert display.tutorial is None
            else:
                expected_step = 1 if moves < 2 else 2 if moves == 2 else 3 if moves < 10 else 4 if moves < 17 else 5
                assert display.tutorial.step == expected_step, (moves, display.tutorial)
                assert display.tutorial.complete == (moves == 19)
                assert display.pick_cell(games[-1], 100, 700) is None
                if display.tutorial.target is not None:
                    sx, sy = view.IsoBoard(10, 10).screen(display.tutorial.target)
                    assert display.pick_cell(games[-1], sx, sy - 46) == display.tutorial.target
        if args.capture_dir and filename:
            if screen == "playing":
                # 기록용 PNG는 걸음 보간이 끝난 위치를 보여 준다.
                p.SDL_Delay(200)
                displays[-1].draw(games[-1], 0, len(load_levels()))
            capture(args.capture_dir / f"{filename}.png")
        original_update()

    with patch.object(view, "Game", ObservedGame), patch.object(view, "FrontEnd", ObservedFrontEnd), \
            patch.object(view.View, "__init__", initialize), patch.object(p, "get_events", events), \
            patch.object(view.View, "text", checked_text), patch.object(p, "update_canvas", update):
        view.run(load_levels())
        assert not steps
        # 타이틀 종료 버튼과 키보드 시작, 전환 직후 창 닫기도 실제 루프로 검사한다.
        for scenario in (
            [([p.SDLK_DOWN, p.SDLK_RETURN], "title", 0, None)],
            [([("left", 800, 131)], "title", 0, None)],
            [([p.SDLK_ESCAPE], "title", 0, None)],
            [([p.SDLK_RETURN, "close"], "story:0", 0, None)],
            [([p.SDLK_RETURN], "story:0", 0, None), (["close"], "story:0", 0, None)],
            [([p.SDLK_RETURN], "story:0", 0, None),
             ([p.SDLK_DOWN, p.SDLK_DOWN, p.SDLK_RETURN], "controls:0", 0, None),
             ([p.SDLK_RETURN], "controls:1", 0, None), ([p.SDLK_RETURN], "playing", 0, None),
             ([p.SDLK_ESCAPE], "playing", 0, None)],
        ):
            current = None
            steps.extend(scenario)
            view.run(load_levels())
            assert not steps
    assert all(not menu.images for menu in menus)
    print("Native onboarding smoke OK: illustrated title, eight comic panels, two guides, back/skip/replay, glyphs and balloon bounds, "
          "input isolation, all five tutorial steps, target picking, "
          "undo/restart, first clear, next room, room shortcut, Escape.")


if __name__ == "__main__":
    main()
