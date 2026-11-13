"""실제 장치 그림·카드 여백·페이지 이동·게임 입력 격리를 검사한다."""

from copy import deepcopy
import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.device_catalog import CARDS, PAGE_COUNT, present_devices
from game.levels import load_levels
from game.model import Game
from game.play_menu import PlayMenu
from tests.smoke_onboarding import capture
from tests.smoke_play_menu import key, click, pixels


def render_checks(levels):
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    original_text = view.View.text
    folder = Path("docs/screenshots/gimmicks-v1/device-catalog")

    def checked_text(display, x, y, value, size=18, color=view.INK):
        width = ctypes.c_int()
        p.TTF_SizeUTF8(display.fonts[size].font, str(value).encode(), ctypes.byref(width), None)
        assert 0 <= x and x + width.value <= view.WIDTH, (value, x, width.value)
        for ch in str(value):
            if ch.isprintable():
                assert p.TTF_GlyphIsProvided(display.fonts[size].font, ord(ch)), (value, ch)
        # 카드 본문이 아래 경계나 옆 카드로 넘치지 않아야 한다.
        if x in (118, 594, 1070) and y < 470:
            assert y >= 315 and width.value <= 388, (value, x, y, width.value)
        original_text(display, x, y, value, size, color)

    try:
        display = view.View()
        menu = PlayMenu()
        game = Game(levels[-1])
        initial = deepcopy(game.state)
        menu.open(display)
        menu.activate("catalog")
        assert set().union(*(present_devices(level) for level in levels)) == {card.kind for card in CARDS}
        for page in range(PAGE_COUNT):
            menu.catalog_page = page
            display.draw(game, 7, len(levels))
            with patch.object(view.View, "text", checked_text):
                menu.draw(display, game)
            capture(folder / f"page-{page + 1:02d}.png")
            for card in CARDS[page * 3:page * 3 + 3]:
                for name, _ in card.pictures:
                    rect = display.art.manifest["sprites"][name]["content_rect"]
                    assert rect["width"] > 0 and rect["height"] > 0
            before = pixels()
            with patch.object(view, "perf_counter", return_value=100000):
                display.draw(game, 7, len(levels))
                menu.draw(display, game)
                assert before == pixels(), "도감 중 플레이 화면이 움직임"
            assert game.state == initial and not game.history
        assert present_devices(levels[0]) == {"trap", "lever"}
    finally:
        if display:
            display.close()
        p.close_canvas()


def input_checks(levels):
    games, menus = [], []
    frame = -1
    update = p.update_canvas
    batches = [
        ([key(p.SDLK_ESCAPE)], None, 0, 0),  # 첫 장치 안내를 닫는다.
        ([key(p.SDLK_ESCAPE)], "pause", 0, 0),
        ([click(800, 365), key(p.SDLK_d)], "catalog", 0, 0),
        ([key(p.SDLK_RIGHT)], "catalog", 1, 0),
        ([key(p.SDLK_e), key(p.SDLK_r), key(p.SDLK_2)], "catalog", 1, 0),
        ([click(224, 234)], "catalog", 0, 0),
        ([key(p.SDLK_LEFT)], "catalog", PAGE_COUNT - 1, 0),
        ([click(800, 168)], "pause", PAGE_COUNT - 1, 0),
        ([key(p.SDLK_ESCAPE), key(p.SDLK_d)], None, PAGE_COUNT - 1, 0),
        ([key(p.SDLK_d)], None, PAGE_COUNT - 1, 1),
        ([key(p.SDLK_ESCAPE)], "pause", PAGE_COUNT - 1, 1),
        ([key(p.SDLK_DOWN)] * 3 + [key(p.SDLK_RETURN)], "catalog", 0, 1),
        ([key(p.SDLK_ESCAPE)], "pause", 0, 1),
        ([key(p.SDLK_ESCAPE)], None, 0, 1),
        ([SimpleNamespace(type=p.SDL_QUIT)], None, 0, 1),
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

    def checked_update():
        if frame >= 0:
            _, mode, page, moves = batches[frame]
            assert menus[-1].mode == mode, (frame, menus[-1].mode)
            assert menus[-1].catalog_page == page
            assert games[-1].level is levels[0] and games[-1].state.moves == moves, frame
        update()

    with patch.object(view, "Game", ObservedGame), patch.object(view, "PlayMenu", ObservedMenu), \
            patch.object(p, "get_events", events), patch.object(p, "update_canvas", checked_update):
        view.run(levels, show_title=False)
    assert frame == len(batches) - 1


def main():
    levels = load_levels()
    render_checks(levels)
    input_checks(levels)
    print("Device catalog smoke OK: nine illustrated cards, page wrap, room presence, glyphs/card bounds, frozen scene, keyboard/mouse, modal input isolation and resume.")


if __name__ == "__main__":
    main()
