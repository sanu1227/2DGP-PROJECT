"""Actual SDL pressure-plate travel, rider height and reversible timing checks."""

import argparse
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard
from game.view import View, WIDTH, HEIGHT, PLATE_SECONDS, ITEM_SPRITES
from tests.smoke_gate_animation import save_frame
from tests.test_game import SOLUTIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    levels = load_levels()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        view = View()
        riders = set()
        for index in range(3, 6):
            game = Game(levels[index])
            plate = next(iter(game.level.plates))
            projection = IsoBoard(game.level.width, game.level.height)
            sx, sy = projection.screen(plate)
            scale = projection.half_width * 2 / 224

            def frame(now):
                before = deepcopy(game.state)
                with patch("game.view.perf_counter", return_value=now):
                    with patch.object(view.art, "draw", wraps=view.art.draw) as draw:
                        view.draw(game, index, len(levels))
                assert game.state == before
                pressed = view.plate_depths[plate]
                height = 60 - 28 * pressed
                assert abs(view.support_height(game, plate) - height) < 1e-8
                if plate in game.state.items:
                    kind = game.state.items[plate]
                    riders.add(kind)
                    calls = [c for c in draw.call_args_list if c.args[0] == ITEM_SPRITES[kind]
                             and abs(c.args[1] - sx) < 1e-8 and "anchor" not in c.kwargs]
                    assert any(abs(c.args[2] - sy - height * scale) < 1e-8 for c in calls)
                if game.state.player == plate:
                    riders.add("player")
                    call = next(c for c in draw.call_args_list if c.args[0].startswith("worker_"))
                    assert abs(call.args[2] - (sy - 7 + height * scale)) < 1e-8
                region = next(r for r in view.plate_hit_masks if r[0] == plate)
                picked = 0
                with patch.object(view, "hit_regions", [region]):
                    for dx in range(-35, 36, 5):
                        for dy in range(-20, 61, 5):
                            point = (sx + dx, sy + dy)
                            if view.art.plate_hit_test(sx, sy, scale, point, pressed):
                                assert view.pick_cell(game, *point) == plate
                                picked += 1
                assert picked > 25
                return pressed

            assert frame(0) == 0
            for action in SOLUTIONS[game.level.id]:
                assert game.act(action)
                if game.plate_pressed(plate):
                    trigger = action
                    break
            assert frame(10) == 0
            values = []
            for step, fraction in enumerate([i / 12 for i in range(12)] + [1.01]):
                values.append(frame(10 + PLATE_SECONDS * fraction))
                if args.capture and index == 4:
                    save_frame(args.capture / f"press-{step}.png")
            assert values[0] == 0 and values[-1] == 1
            assert all(a < b for a, b in zip(values, values[1:]))
            assert abs(values[6] - .5) < 1e-8
            assert game.undo()
            assert frame(11) == 1
            halfway = frame(11 + PLATE_SECONDS / 2)
            assert abs(halfway - .5) < 1e-8
            assert game.act(trigger)
            assert abs(frame(11 + PLATE_SECONDS / 2) - halfway) < 1e-8
            assert halfway < frame(11 + PLATE_SECONDS * .75) < 1
            assert frame(12) == 1
            assert game.undo()
            assert frame(13) == 1
            release = []
            for step, fraction in enumerate([i / 12 for i in range(12)] + [1.01]):
                release.append(frame(13 + PLATE_SECONDS * fraction))
                if args.capture and index == 4:
                    save_frame(args.capture / f"release-{step}.png")
            assert all(a > b for a, b in zip(release, release[1:]))
            assert frame(14) == 0
            # Smooth support interpolation while walking onto/off the plate.
            heights = [view.player_support_height(game, (plate[0] - 1 + t, plate[1]))
                       for t in (0, .25, .5, .75, 1)]
            assert heights == sorted(heights) and heights[-1] == 60
            assert heights[0] == view.support_height(game, (plate[0] - 1, plate[1]))
            game.restart()
            view.reset_gates()
            view.reset_plates()
            assert frame(15) == 0
            game = Game(levels[index])
            assert frame(16) == 0
        assert riders == {"player", "bone", "part"}, riders
        print("Plate animation smoke OK: rooms 4–6; 13 travel samples, player/bone/belt-part "
              "height, animated picking, reverse/undo, release, restart and room switch.")
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
