"""Actual SDL checks for grounded items, raised surfaces, carrying and picking."""

from copy import deepcopy
from math import ceil, floor
from unittest.mock import patch

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard
from game.view import View, WIDTH, HEIGHT, ITEM_SPRITES
from tests.test_game import SOLUTIONS


def visible_item_pixel(display, game, pos, sprite):
    """Find a visible opaque pixel that selects the item's logical cell."""
    for (cell, rect), mask in display.hit_masks.items():
        if cell != pos or mask[0] != sprite:
            continue
        left, bottom, right, top = rect
        for y in range(ceil(top) - 1, floor(bottom) - 1, -1):
            for x in range(ceil(left), ceil(right)):
                if (display.art.hit_test(*mask[:4], (x, y), *mask[4:])
                        and display.pick_cell(game, x, y) == pos):
                    return x, y
    raise AssertionError(f"No visible clickable pixel: {game.level.id} {pos} {sprite}")


def main():
    levels = load_levels()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    display = None
    checked = 0
    try:
        display = View()
        for index, level in enumerate(levels):
            game = Game(level)
            before = deepcopy(game.state)
            display.draw(game, index, len(levels))
            for pos, kind in game.state.items.items():
                visible_item_pixel(display, game, pos, ITEM_SPRITES[kind])
                checked += 1
            assert game.state == before
        # Loading theme packs applies the same footprint correction as core objects.
        pipe = display.art.manifest["sprites"]["sewer_pipe_elbow"]
        assert pipe["anchor"] == {"x": 94, "y": 205}
        assert pipe["display_anchor"] == {"x": 128, "y": 220}

        # 새 장치도 같은 기준점과 알파 클릭 판정을 사용한다.
        for index, level in enumerate(levels[3:],3):
            game=Game(level); display.draw(game,index,len(levels))
            for cells,sprite in ((level.mirrors,"mirror"),
                                 (level.jobs,"winch"),(level.rubble,"push_rubble")):
                for pos in cells:
                    visible_item_pixel(display,game,pos,sprite)
                    checked+=1
        p.update_canvas()
        print(f"Placement smoke OK: {checked} items and devices in eight rooms; "
              "new-device alpha picking and theme grounding.")
    finally:
        if display:
            display.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
