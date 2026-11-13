"""SDL 메뉴 입력, 실제 렌더링 정지와 재개 검사. 창 없이도 실행할 수 있다."""

from copy import deepcopy
from math import isclose
import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.front_end import FrontEnd
from game.levels import load_levels
from game.model import Game
from game.play_menu import PlayMenu
from game.tutorial import device_lessons
from tests.smoke_onboarding import capture
from tests.solutions import SOLUTIONS


def key(value):
    return SimpleNamespace(type=p.SDL_KEYDOWN, key=value)


def click(x, y):
    return SimpleNamespace(type=p.SDL_MOUSEBUTTONDOWN, button=p.SDL_BUTTON_LEFT,
                           x=x, y=view.HEIGHT - 1 - y)


def pixels():
    result = (ctypes.c_ubyte * (view.WIDTH * view.HEIGHT * 4))()
    assert p.SDL_RenderReadPixels(p.renderer, None, p.SDL_PIXELFORMAT_RGBA32,
                                 result, view.WIDTH * 4) == 0
    return bytes(result)


def animation_checks(levels, folder):
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    try:
        display = view.View()
        menu = PlayMenu()
        # 실제 발판과 문이 움직이는 중간 프레임에서 정지한다.
        game = Game(levels[3])
        menu.lessons = device_lessons(game.level)
        plate = next(iter(game.level.plates))
        with patch.object(view, "perf_counter", return_value=10):
            display.draw(game, 3, len(levels))
            previous = game.state.player
            game.state.player = plate
            display.move_player(previous, plate, "down")
            display.draw(game, 3, len(levels))
        with patch.object(view, "perf_counter", return_value=10.09):
            menu.open(display)
            display.draw(game, 3, len(levels))
            menu.draw(display, game)
            capture(folder / "pause.png")
            frozen = pixels()
            position = display.player_position(plate, display.now())
            depths = dict(display.plate_depths)
            assert any(0 < value < 1 for value in depths.values())
        with patch.object(view, "perf_counter", return_value=110):
            display.draw(game, 3, len(levels))
            menu.draw(display, game)
            assert pixels() == frozen, "메뉴 대기 중 플레이 화면이 움직임"
            assert display.player_position(plate, display.now()) == position
            assert display.plate_depths == depths
            menu.activate("controls")
            display.draw(game, 3, len(levels))
            menu.draw(display, game)
            capture(folder / "controls.png")
            menu.close(display)
            assert abs(display.now() - 10.09) < 1e-9
        with patch.object(view, "perf_counter", return_value=110.2):
            display.draw(game, 3, len(levels))
            assert display.plate_depths[plate] == 1
            assert display.player_position(plate, display.now()) == plate

    finally:
        if display:
            display.close()
        p.close_canvas()


def input_checks(levels):
    games, displays, menus, fronts = [], [], [], []
    original_init = view.View.__init__
    original_update = p.update_canvas
    original_text = view.View.text
    frame = -1
    times = [1, 1.05, 100, 101, 102, 103, 104, 104.01, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
    batches = [
        [], [key(p.SDLK_ESCAPE), key(p.SDLK_d)],
        [key(p.SDLK_e), key(p.SDLK_r), key(p.SDLK_6), click(50, 50)],
        [click(800, 445), key(p.SDLK_d)],
        [key(p.SDLK_ESCAPE)], [key(p.SDLK_ESCAPE), key(p.SDLK_d)], [],
        [key(p.SDLK_ESCAPE)], [key(p.SDLK_DOWN), key(p.SDLK_RETURN), key(p.SDLK_d)],
        [key(p.SDLK_d)], [key(p.SDLK_ESCAPE)],
        [key(p.SDLK_UP), key(p.SDLK_RETURN), key(p.SDLK_RETURN)],
        [key(p.SDLK_1)], [key(p.SDLK_ESCAPE)],
        [click(800, 605), key(p.SDLK_d)], [key(p.SDLK_ESCAPE)],
        [SimpleNamespace(type=p.SDL_QUIT)],
    ]

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            games.append(self)

    class ObservedMenu(PlayMenu):
        def __init__(self):
            super().__init__()
            # 첫 장치 안내를 읽은 플레이어의 메뉴 조작을 검사한다.
            self.seen_devices.add("trap")
            menus.append(self)

    class ObservedFront(FrontEnd):
        def __init__(self, show_title=True):
            super().__init__(show_title)
            fronts.append(self)

    def initialize(display):
        original_init(display)
        displays.append(display)

    def events():
        nonlocal frame
        frame += 1
        assert frame < len(batches), "창 닫기 입력을 처리하지 못함"
        if frame == 0:
            assert displays[-1].navigation.start(games[-1], (4, 2), times[0])
        return batches[frame]

    def checked_text(display, x, y, value, size=18, color=view.INK):
        if menus[-1].active:
            width = ctypes.c_int()
            p.TTF_SizeUTF8(display.fonts[size].font, str(value).encode(), ctypes.byref(width), None)
            assert 0 <= x and x + width.value <= view.WIDTH, (value, x, width.value)
            for ch in str(value):
                if ch.isprintable():
                    assert p.TTF_GlyphIsProvided(display.fonts[size].font, ord(ch)), (value, ch)
        original_text(display, x, y, value, size, color)

    def update():
        if frame < 0:
            original_update()
            return
        game, display, menu = games[-1], displays[-1], menus[-1]
        if frame <= 5:
            assert game.state.moves == 1, (frame, game.state.moves)
            assert display.navigation.active
        if frame in (1, 2):
            assert menu.mode == "pause"
        if frame == 3:
            assert menu.mode == "controls"
        if frame == 4:
            assert menu.mode == "pause"
        if frame == 5:
            assert not menu.active
        if frame == 6:
            assert game.state.moves == 2
        if frame == 8:
            assert game.state.moves == 0 and not display.navigation.active and not menu.active
        if frame in (9, 10):
            assert game.state.moves == 1
        if frame == 11:
            assert fronts[-1].screen == "title" and not menu.active
        if frame >= 12:
            assert game.state.moves == 0
        if frame == 14:
            assert not menu.active
        original_update()

    with patch.object(view, "Game", ObservedGame), patch.object(view, "PlayMenu", ObservedMenu), \
            patch.object(view, "FrontEnd", ObservedFront), patch.object(view.View, "__init__", initialize), \
            patch.object(view.View, "text", checked_text), patch.object(p, "get_events", events), \
            patch.object(p, "update_canvas", update), patch.object(view, "perf_counter", side_effect=lambda: times[max(0, frame)]):
        view.run(levels, show_title=False)
    assert frame == len(batches) - 1


def main():
    levels = load_levels()
    folder = Path("docs/screenshots/gimmicks-v1/play-menu")
    animation_checks(levels, folder)
    input_checks(levels)
    print("Play menu smoke OK: frozen rendering, gates/plates/player, resume, preserved click path, input isolation, controls, restart, title, close.")


if __name__ == "__main__":
    main()
