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
                if (display.art.hit_test(*mask[:4], (x, y), mask[4])
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

        game = Game(levels[5])
        projection = IsoBoard(game.level.width, game.level.height)
        scale = projection.half_width * 2 / 224
        checkpoints = {}
        for step, action in enumerate(SOLUTIONS[game.level.id][:7], 1):
            assert game.act(action), game.message
            if step not in (3, 6, 7):
                continue
            # Compare settled anchors; automatic transport now reaches the animated plate immediately.
            with patch("game.view.perf_counter", return_value=float(step)):
                display.draw(game, 5, len(levels))
            with patch("game.view.perf_counter", return_value=step + 1.1), \
                    patch.object(display.art, "draw", wraps=display.art.draw) as draw:
                display.draw(game, 5, len(levels))
            if step == 3:
                assert game.state.carrying == "part"
                carried = [call for call in draw.call_args_list if call.args[0] == "part"]
                assert carried and all(call.kwargs["anchor"] == {"x": 128, "y": 220}
                                       for call in carried)
                continue
            pos = next(pos for pos, kind in game.state.items.items() if kind == "part")
            assert pos in game.level.plates
            visible_item_pixel(display, game, pos, "part")
            sx, sy = projection.screen(pos)
            calls = [call for call in draw.call_args_list if call.args[0] == "part"]
            assert len(calls) == 1
            assert calls[0].args[1] == sx
            assert abs(calls[0].args[2] - sy - display.support_height(game, pos) * scale) < 1e-8
            assert "anchor" not in calls[0].kwargs  # Ground anchor, not the carrying anchor.
            checkpoints[step] = (deepcopy(game.state), [region for region, mask in display.hit_masks.items()
                                                      if mask[0] == "part"])
        assert game.undo()
        with patch("game.view.perf_counter", return_value=8):
            display.draw(game, 5, len(levels))
        assert game.state == checkpoints[6][0]
        assert [region for region, mask in display.hit_masks.items() if mask[0] == "part"] == checkpoints[6][1]
        p.update_canvas()
        print(f"Placement smoke OK: {checked} ground items in six rooms; "
              "belt/plate height and picking, carrying/HUD anchor, undo, theme grounding.")
    finally:
        if display:
            display.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
