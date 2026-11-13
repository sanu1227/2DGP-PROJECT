"""Deterministic SDL checks for gate movement, reversal and animated alpha picking."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import argparse

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.view import View, WIDTH, HEIGHT, GATE_SECONDS
from tests.test_game import SOLUTIONS


def save_frame(path):
    surface = p.SDL_CreateRGBSurfaceWithFormat(0, WIDTH, HEIGHT, 32, p.SDL_PIXELFORMAT_RGBA32)
    if not surface:
        raise RuntimeError("SDL surface creation failed")
    try:
        assert p.SDL_RenderReadPixels(p.renderer, None, surface.contents.format.contents.format,
                                     surface.contents.pixels, surface.contents.pitch) == 0
        path.parent.mkdir(parents=True, exist_ok=True)
        assert p.IMG_SavePNG(surface, str(path).encode("utf-8")) == 0
    finally:
        p.SDL_FreeSurface(surface)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    levels = load_levels()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        view = View()
        for index in (3, 4, 6):
            game = Game(levels[index])
            gate = next(iter(game.level.gates))

            def frame(now):
                before = deepcopy(game.state)
                with patch("game.view.perf_counter", return_value=now):
                    view.draw(game, index, len(levels))
                assert game.state == before
                region, mask = next((r, m) for r, m in view.gate_hit_masks.items() if r[0] == gate)
                sx, sy, scale, opening, flip = mask
                # A sample of moving grille pixels still belongs to the same gate cell.
                for dx in range(-12, 13, 4):
                    for dy in range(25, 66, 8):
                        point = (sx + dx, sy + dy)
                        if view.art.gate_hit_test(sx, sy, scale, point, opening, flip):
                            # Isolate gate pixels from labels/player legitimately drawn above it.
                            with patch.object(view, "hit_regions", [region]):
                                assert view.pick_cell(game, *point) == gate
                return opening, mask

            assert frame(0)[0] == 0
            for action in SOLUTIONS[game.level.id]:
                assert game.act(action)
                if game.gate_status(gate) == "open":
                    trigger = action
                    break
            assert frame(10)[0] == 0
            values, masks = [], []
            for step, fraction in enumerate([step / 12 for step in range(12)] + [1.01]):
                value, mask = frame(10 + GATE_SECONDS * fraction)
                values.append(value)
                masks.append(mask)
                if args.capture and index == 3:
                    save_frame(args.capture / f"opening-{step}.png")
            assert values[0] == 0 and values[-1] == 1
            assert all(a < b for a, b in zip(values, values[1:]))
            sx, sy, scale, _, flip = masks[len(masks) // 2]
            # Midway is a translated grille, not a static closed/open texture switch.
            different = sum(view.art.gate_hit_test(sx, sy, scale, (sx + dx, sy + dy), .5, flip)
                            != view.art.gate_hit_test(sx, sy, scale, (sx + dx, sy + dy), 0, flip)
                            for dx in range(-20, 21) for dy in range(15, 80))
            assert different > 100, different

            assert game.undo()
            assert frame(11)[0] == 1
            halfway = frame(11 + GATE_SECONDS / 2)[0]
            assert abs(halfway - .5) < 1e-8
            if args.capture and index == 3:
                save_frame(args.capture / "closing-half.png")
            # Reverse closing immediately, without snapping back to an endpoint.
            assert game.act(trigger)
            assert abs(frame(11 + GATE_SECONDS / 2)[0] - halfway) < 1e-8
            assert halfway < frame(11 + GATE_SECONDS * .75)[0] < 1
            assert frame(12)[0] == 1
            assert game.undo()
            assert frame(13)[0] == 1
            assert frame(14)[0] == 0
            if args.capture and index == 3:
                save_frame(args.capture / "closed-again.png")
            # Restart clears animation; switching rooms starts at their actual state.
            assert game.act(trigger)
            frame(15)
            game.restart()
            view.reset_gates()
            assert frame(15.1)[0] == 0
            game = Game(levels[index])
            assert frame(15.2)[0] == 0
            # Occupied gate remains raised while waiting for the occupant to leave.
            game.state.player = gate
            assert game.gate_status(gate) == "held"
            frame(16)
            assert frame(17)[0] == 1
        print("Gate animation smoke OK: rooms 4, 5, 7; timed lift/lower, midpoint pixels, "
              "continuous reversal, undo, restart, room switch, held and animated picking.")
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
