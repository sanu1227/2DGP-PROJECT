"""장치 첫 안내·다시 보기·강조 영역과 실제 게임 루프의 입력 격리 검사."""

import argparse
import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.device_guide import dim_except
from game.levels import load_levels
from game.model import Game
from game.play_menu import PlayMenu
from game.tutorial import device_lessons
from tests.smoke_onboarding import capture
from tests.smoke_play_menu import key, click, pixels
from tests.solutions import SOLUTIONS


def check_layout(menu, display, game):
    for left, bottom, right, top in (menu.guide_region, menu.guide_card):
        assert 0 <= left < right <= view.WIDTH and 0 <= bottom < top <= view.HEIGHT
    left, bottom, right, top = menu.guide_region
    assert top < menu.guide_card[1] or menu.guide_card[3] < bottom
    lesson = menu.pages[menu.page_index]
    x, y = display.projection(game.level).screen(lesson.target)
    assert left < x < right and bottom < y < top
    for cell, (l, b, r, t) in display.hit_regions:
        if cell == lesson.target:
            assert left <= l < r <= right and bottom <= b < t <= top, (menu.guide_region, (l, b, r, t))
    left, _, right, _ = menu.guide_card
    assert display.text_width(lesson.instruction, 22) <= right - left - 44, lesson.instruction


def render_checks(levels, folder=Path("docs/screenshots/gimmicks-v1/device-guide"), *, top_down=False):
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    original_text = view.View.text
    menu = PlayMenu()

    def checked_text(display, x, y, value, size=18, color=view.INK):
        width = ctypes.c_int()
        p.TTF_SizeUTF8(display.fonts[size].font, str(value).encode(), ctypes.byref(width), None)
        assert 0 <= x and x + width.value <= view.WIDTH, (value, x, width.value)
        assert 0 <= y <= view.HEIGHT
        for ch in str(value):
            if ch.isprintable():
                assert p.TTF_GlyphIsProvided(display.fonts[size].font, ord(ch)), (value, ch)
        original_text(display, x, y, value, size, color)

    try:
        display = view.View()
        display.top_down = top_down
        p.draw_rectangle(0, 0, view.WIDTH - 1, view.HEIGHT - 1, 180, 180, 180, filled=True)
        dim_except((180, 180, 260, 250))
        buffer = pixels()

        def shade(x, y):
            return buffer[4 * ((view.HEIGHT - 1 - y) * view.WIDTH + x)]

        assert shade(215, 215) == 180
        assert shade(175, 215) > shade(160, 215) > shade(145, 215) > shade(120, 215)
        assert abs(shade(131, 215) - shade(129, 215)) <= 4, "강조 영역의 경계에 이음새가 생김"
        for level in levels:
            game = Game(level)
            menu.offer(game, display)
            assert not menu.active and display.clock.frozen is None

        # 이미 본 장치도 모든 방에서 다시 열어, 가까운 배치와 긴 이름을 검사한다.
        for index, level in enumerate(levels):
            game = Game(level)
            display.tutorial_hidden = True
            lessons = device_lessons(level)
            menu.start_guide(lessons, "playing")
            for page, lesson in enumerate(lessons):
                menu.page_index = page
                with patch.object(view.View, "text", checked_text):
                    display.draw(game, index, len(levels))
                    menu.draw(display, game)
                check_layout(menu, display, game)
                capture(folder / f"{level.id}-{page + 1:02d}-{lesson.kind}.png")
    finally:
        if display:
            display.close()
        p.close_canvas()


def input_checks(levels):
    games, menus = [], []
    frame = -1
    original_update = p.update_canvas
    batches = [
        ([click(800, 400), key(p.SDLK_RETURN)], "device", "stage_04"),
        ([key(p.SDLK_d), key(p.SDLK_e), click(100, 100)], "device", "stage_04"),
        ([key(p.SDLK_RETURN), key(p.SDLK_d)], "device", "stage_04"),
        ([key(p.SDLK_RETURN), key(p.SDLK_d)], "device", "stage_04"),
        ([key(p.SDLK_SPACE), key(p.SDLK_d)], None, "stage_04"),
        ([key(p.SDLK_r)], None, "stage_04"),
        ([key(p.SDLK_5), key(p.SDLK_RETURN)], "device", "stage_05"),
        ([key(p.SDLK_ESCAPE)], None, "stage_05"),
        ([key(p.SDLK_4)], "device", "stage_04"),
        ([key(p.SDLK_ESCAPE)], None, "stage_04"),
        ([key(p.SDLK_4)], "device", "stage_04"),
        ([key(p.SDLK_ESCAPE)], None, "stage_04"),
        ([key(p.SDLK_ESCAPE)], "pause", "stage_04"),
        ([click(800, 445)], "controls", "stage_04"),
        ([click(600, 253), key(p.SDLK_d)], "device", "stage_04"),
        ([key(p.SDLK_RETURN)], "device", "stage_04"),
        ([key(p.SDLK_ESCAPE)], "controls", "stage_04"),
        ([key(p.SDLK_ESCAPE)], "pause", "stage_04"),
        ([key(p.SDLK_ESCAPE), key(p.SDLK_d)], None, "stage_04"),
        ([SimpleNamespace(type=p.SDL_QUIT)], None, "stage_04"),
    ]

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            games.append(self)

    class ObservedMenu(PlayMenu):
        def __init__(self):
            super().__init__()
            menus.append(self)

    def events():
        nonlocal frame
        frame += 1
        assert frame < len(batches)
        return batches[frame][0]

    def update():
        if frame >= 0:
            _, mode, stage = batches[frame]
            assert menus[-1].mode == mode, (frame, menus[-1].mode, mode)
            assert games[-1].level.id == stage
            assert games[-1].state.moves == 0 and not games[-1].history
            menu = menus[-1]
            if mode == "device" and menu.return_mode == "playing":
                titles = (["뼈 투입구", "배출구", "이동 거울", "빛 수신기"] if stage == "stage_05"
                          else ["발판", "연결문", "잔해"])
                assert [page.title for page in menu.pages] == titles
                assert menu.page_index == (frame - 1 if frame in (2, 3) else 0)
                assert menu.buttons[0].label == ("작업 시작" if frame == 3 else "다음")
        original_update()

    with patch.object(view, "Game", ObservedGame), patch.object(view, "PlayMenu", ObservedMenu), \
            patch.object(p, "get_events", events), patch.object(p, "update_canvas", update):
        view.run(levels, index=3, show_title=False)
    assert frame == len(batches) - 1


def first_room_checks(levels):
    games, menus, displays = [], [], []
    frame = -1
    original_update = p.update_canvas
    original_initialize = view.View.__init__

    def initialize(display):
        original_initialize(display)
        displays.append(display)
    batches = [
        ([], None, 0),
        ([key(p.SDLK_d)], None, 1),
        ([key(p.SDLK_z)], None, 0),
        ([key(p.SDLK_r)], None, 0),
        ([key(p.SDLK_ESCAPE)], "pause", 0),
        ([click(800, 445)], "controls", 0),
        ([click(600, 253)], "device", 0),
        ([key(p.SDLK_ESCAPE), key(p.SDLK_d)], "controls", 0),
        ([key(p.SDLK_ESCAPE)], "pause", 0),
        ([key(p.SDLK_ESCAPE)], None, 0),
    ]
    keys = {"up": p.SDLK_w, "down": p.SDLK_s, "left": p.SDLK_a,
            "right": p.SDLK_d, "interact": p.SDLK_e}
    batches.extend(([key(keys[action])], None, moves)
                   for moves, action in enumerate(SOLUTIONS[levels[0].id], 1))
    batches.append(([SimpleNamespace(type=p.SDL_QUIT)], None, len(SOLUTIONS[levels[0].id])))

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            games.append(self)

    class ObservedMenu(PlayMenu):
        def __init__(self):
            super().__init__()
            menus.append(self)

    def events():
        nonlocal frame
        frame += 1
        assert frame < len(batches)
        return batches[frame][0]

    def update():
        if frame >= 0:
            _, mode, moves = batches[frame]
            assert menus[-1].mode == mode, (frame, menus[-1].mode)
            assert games[-1].state.moves == moves, frame
            assert games[-1].level is levels[0]
            assert displays[-1].tutorial_hidden == (mode == "device")
            if mode == "device":
                assert [page.title for page in menus[-1].pages] == ["함정", "가동 레버"]
            if frame == len(batches) - 1:
                assert games[-1].state.cleared
        original_update()

    with patch.object(view, "Game", ObservedGame), patch.object(view, "PlayMenu", ObservedMenu), \
            patch.object(view.View, "__init__", initialize), \
            patch.object(p, "get_events", events), patch.object(p, "update_canvas", update):
        view.run(levels, show_title=False)
    assert frame == len(batches) - 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, default=Path("docs/screenshots/gimmicks-v1/device-guide"))
    parser.add_argument("--top-down", action="store_true", help="탑다운 플레이 화면의 안내를 검사")
    args = parser.parse_args()
    levels = load_levels()
    render_checks(levels, args.capture_dir, top_down=args.top_down)
    input_checks(levels)
    first_room_checks(levels)
    print("Device guide smoke OK: one spotlight and one-line bubble per step, glyphs, skip/replay, undo/restart, full first-room clear and input isolation.")


if __name__ == "__main__":
    main()
