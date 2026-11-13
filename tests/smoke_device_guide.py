"""장치 첫 안내·다시 보기·강조 영역과 실제 게임 루프의 입력 격리 검사."""

from copy import deepcopy
import argparse
import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.device_guide import outside_rectangles
from game.levels import load_levels
from game.model import Game
from game.play_menu import PlayMenu
from game.tutorial import device_lessons
from tests.smoke_onboarding import capture
from tests.smoke_play_menu import key, click, pixels
from tests.solutions import SOLUTIONS


def check_layout(menu):
    rectangles = [*menu.guide_regions, *menu.guide_labels.values(), menu.guide_card]
    for i, (left, bottom, right, top) in enumerate(rectangles):
        assert 0 <= left < right <= view.WIDTH and 0 <= bottom < top <= view.HEIGHT
        for other in rectangles[i + 1:]:
            l, b, r, t = other
            assert min(right, r) <= max(left, l) or min(top, t) <= max(bottom, b), (
                "강조 창·이름표·안내 카드가 겹침", rectangles[i], other)
    for left, bottom, right, top in menu.guide_bounds.values():
        assert any(l <= left and b <= bottom and r >= right and t >= top
                   for l, b, r, t in menu.guide_regions), "강조 창에서 장치가 잘림"


def render_checks(levels, folder=Path("docs/screenshots/gimmicks-v1/device-guide")):
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    original_text = view.View.text
    menu = PlayMenu()
    seen = []

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
        for index, level in enumerate(levels):
            game = Game(level)
            initial = deepcopy(game.state)
            menu.offer(game, display)
            display.tutorial_hidden = menu.mode == "device"
            offered = [lesson.kind for lesson in menu.pages] if menu.active else []
            assert offered == {0: ["trap"], 1: ["assembly"], 3: ["plate", "rubble"], 4: ["chute", "mirror"], 6: ["helper"]}.get(index, []), (index, offered)
            while menu.active:
                with patch.object(view.View, "text", checked_text):
                    display.draw(game, index, len(levels))
                    before = pixels()
                    menu.draw(display, game)
                    after = pixels()
                check_layout(menu)
                assert before != after
                lesson = menu.pages[menu.page_index]
                capture(folder / f"{level.id}-{lesson.kind}.png")
                # 흰 테두리·문구·연결선 바깥에 실제 장치 픽셀이 밝게 보존된다.
                for left, bottom, right, top in menu.guide_bounds.values():
                    same, colored = 0, 0
                    for y in range(bottom + 4, top - 4, 5):
                        for x in range(left + 4, right - 4, 5):
                            offset = ((view.HEIGHT - 1 - y) * view.WIDTH + x) * 4
                            if max(before[offset:offset + 3]) > 40:
                                colored += 1
                                same += before[offset:offset + 3] == after[offset:offset + 3]
                    assert colored and same / colored > .75, (level.id, same, colored)
                result = menu.activate("guide_next")
                seen.append(lesson.kind)
                if result == "resume":
                    menu.close(display)
            assert game.state == initial and not game.history
            game.restart()
            menu.offer(game, display)
            assert not menu.active, "재시작에 안내가 반복됨"
        assert seen == ["trap", "assembly", "plate", "rubble", "chute", "mirror", "helper"]

        # 이미 본 장치도 모든 방에서 다시 열어, 가까운 배치와 긴 이름을 검사한다.
        for index, level in enumerate(levels):
            game = Game(level)
            display.tutorial_hidden = True
            for lesson in device_lessons(level):
                menu.pages, menu.page_index, menu.mode = (lesson,), 0, "device"
                with patch.object(view.View, "text", checked_text):
                    display.draw(game, index, len(levels))
                    menu.draw(display, game)
                check_layout(menu)
                for pos, _ in lesson.targets:
                    assert 0 <= pos[0] < level.width and 0 <= pos[1] < level.height
        # 서로 겹친 강조 창도 배경이 중복해서 어두워지지 않아야 한다.
        rectangles = outside_rectangles(((10, 10, 100, 100), (50, 50, 200, 200)))
        area = sum((r - l) * (t - b) for l, b, r, t in rectangles)
        assert area == view.WIDTH * view.HEIGHT - (90 * 90 + 150 * 150 - 50 * 50)
    finally:
        if display:
            display.close()
        p.close_canvas()


def input_checks(levels):
    games, menus = [], []
    frame = -1
    original_update = p.update_canvas
    batches = [
        ([key(p.SDLK_d), key(p.SDLK_e), key(p.SDLK_r), key(p.SDLK_6)], "device", "stage_04"),
        ([key(p.SDLK_RETURN), key(p.SDLK_d)], "device", "stage_04"),
        ([key(p.SDLK_RETURN), key(p.SDLK_d)], "device", "stage_04"),
        ([key(p.SDLK_ESCAPE), key(p.SDLK_d)], None, "stage_04"),
        ([key(p.SDLK_r)], None, "stage_04"),
        ([key(p.SDLK_5), key(p.SDLK_d)], "device", "stage_05"),
        ([], None, "stage_05"),
        ([key(p.SDLK_4)], None, "stage_04"),
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
        if frame == 6:
            button = menus[-1].buttons[1]
            l, b, r, t = button.bounds
            return [click((l + r) / 2, (b + t) / 2), key(p.SDLK_d)]
        return batches[frame][0]

    def update():
        if frame >= 0:
            _, mode, stage = batches[frame]
            assert menus[-1].mode == mode, (frame, menus[-1].mode, mode)
            assert games[-1].level.id == stage
            assert games[-1].state.moves == 0 and not games[-1].history
            if frame == 1:
                assert menus[-1].pages[menus[-1].page_index].kind == "assembly"
            if frame == 2:
                assert menus[-1].pages[menus[-1].page_index].kind == "plate"
            if frame == 5:
                assert [p.kind for p in menus[-1].pages] == ["chute", "mirror"]
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
        ([key(p.SDLK_d), key(p.SDLK_e), key(p.SDLK_r), key(p.SDLK_2)], "device", 0),
        ([key(p.SDLK_RETURN), key(p.SDLK_d)], None, 0),
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
                assert [page.kind for page in menus[-1].pages] == ["trap"]
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
    args = parser.parse_args()
    levels = load_levels()
    render_checks(levels, args.capture_dir)
    input_checks(levels)
    first_room_checks(levels)
    print("Device guide smoke OK: seven first encounters, non-overlapping spotlights/labels/cards in every room, spotlight pixels, glyphs, skip/replay, undo/restart, full first-room clear and input isolation.")


if __name__ == "__main__":
    main()
