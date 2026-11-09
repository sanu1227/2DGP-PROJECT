"""Real SDL gate state, aperture, picking and traversal checks in rooms 4–6."""

from copy import deepcopy
from dataclasses import replace
from math import ceil, floor
from unittest.mock import patch

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard, find_path
from game.view import View, WIDTH, HEIGHT
from tests.test_game import SOLUTIONS


def main():
    levels = load_levels()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    checked = 0
    try:
        view = View()
        clock = 100.0
        for index in range(3, 6):
            game = Game(levels[index])
            gate, plate = next(iter(game.level.gates.items()))
            statuses = set()

            def check():
                nonlocal checked, clock
                before = deepcopy(game.state)
                status = game.gate_status(gate)
                statuses.add(status)
                # This suite checks settled artwork; timing and reversals have a separate suite.
                with patch("game.view.perf_counter", return_value=clock):
                    view.draw(game, index, len(levels))
                clock += 1
                with patch("game.view.perf_counter", return_value=clock):
                    with patch.object(view.art, "draw", wraps=view.art.draw) as draw:
                        view.draw(game, index, len(levels))
                assert game.state == before
                calls = [call for call in draw.call_args_list if call.args[0].startswith("gate_")]
                assert len(calls) == 1
                sprite = "gate_closed" if status == "closed" else "gate_open"
                assert calls[0].args[0] == sprite
                assert not calls[0].kwargs["flip"]  # All authored gates cross the x travel axis.
                region, mask = next((region, mask) for region, mask in view.hit_masks.items()
                                    if region[0] == gate and mask[0] == sprite)
                _, (left, bottom, right, top) = region
                assert any(view.art.hit_test(*mask[:4], (x, y), mask[4])
                           and view.pick_cell(game, x, y) == gate
                           for y in range(ceil(top) - 1, floor(bottom), -1)
                           for x in range(ceil(left), ceil(right)))
                assert game.walkable(gate) == (status == "open")
                checked += 1

            check()
            previous = "closed"
            for action in SOLUTIONS[game.level.id]:
                before = deepcopy(game.state)
                assert game.act(action), game.message
                status = game.gate_status(gate)
                if status != previous or game.state.player == gate:
                    check()
                    after = deepcopy(game.state)
                    assert game.undo() and game.state == before
                    check()
                    assert game.act(action) and game.state == after
                previous = status
            assert game.state.cleared and {"closed", "open"} <= statuses

            # Closing waits for an occupant to leave; the grille must not impale them.
            game.restart()
            game.state.player = gate
            game.state.items.pop(plate, None)
            assert game.gate_status(gate) == "held"
            check()
            destination = (gate[0] + 1, gate[1])
            assert find_path(game, destination) == [destination]
            assert game.act("right") and game.gate_status(gate) == "closed"
            check()
            assert game.undo() and game.gate_status(gate) == "held"
            check()

        # The transparent opening must stop claiming pixels formerly occupied by bars.
        projection = IsoBoard(game.level.width, game.level.height)
        sx, sy = projection.screen(gate)
        scale = projection.half_width * 2 / 224
        aperture = [(sx + dx, sy + dy) for dx in range(-18, 19) for dy in range(20, 75)
                    if view.art.hit_test("gate_closed", sx, sy, scale, (sx + dx, sy + dy))
                    and not view.art.hit_test("gate_open", sx, sy, scale, (sx + dx, sy + dy))]
        assert len(aperture) > 300, len(aperture)
        # Alternate wall axis uses the matching mirrored visual and alpha mask.
        rotated = replace(game.level, walls=frozenset({(gate[0] - 1, gate[1]), (gate[0] + 1, gate[1])}))
        with patch.object(view.art, "draw", wraps=view.art.draw) as draw:
            view.gate(rotated, gate, sx, sy, scale, "open")
        assert draw.call_args.kwargs["flip"]
        assert any(mask[0] == "gate_open" and mask[4] for mask in view.hit_masks.values())
        print(f"Gate smoke OK: {checked} states; rooms 4–6 solved, transitions/undo, "
              f"held exit, alpha picking, {len(aperture)} clear aperture pixels and both axes.")
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
