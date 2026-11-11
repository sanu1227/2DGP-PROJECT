"""Native SDL checks for automatic belt animation and input recovery."""

from collections import deque
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import argparse
import ctypes
import math

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.model import Game
from tests.smoke_gate_animation import save_frame
from tests.test_game import SOLUTIONS


def check_frames(levels, capture):
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    try:
        display = view.View()
        game = Game(levels[5])
        for action in SOLUTIONS[game.level.id][:5]:
            assert game.act(action)
        with patch.object(view, "perf_counter", return_value=0):
            display.draw(game, 5, len(levels))
        assert game.act("interact")
        final = deepcopy(game.state)
        display.belt_animation.start(game, 0)
        projection = view.IsoBoard(10, 10)
        scale = projection.half_width * 2 / 224
        for now, position in ((0, (3, 3)), (.08, (3.5, 3)), (.16, (4, 3)),
                              (.24, (4.5, 3)), (.32, (5, 3)), (.4, (5, 2.5)),
                              (.48, (5, 2)), (.56, (5, 1.5)), (.64, (5, 1)), (1.1, (5, 1))):
            with patch.object(view, "perf_counter", return_value=now), \
                    patch.object(display.art, "draw", wraps=display.art.draw) as draw:
                display.draw(game, 5, len(levels))
            parts = [call for call in draw.call_args_list if call.args[0] == "part"]
            assert len(parts) == 1
            x, y = projection.screen(position)
            y += display.player_support_height(game, position) * scale
            assert math.isclose(parts[0].args[1], x, abs_tol=1e-7)
            assert math.isclose(parts[0].args[2], y, abs_tol=1e-7)
            assert game.state == final and len(game.history) == 6
            if now < .64:
                assert display.plate_depths[(5, 1)] == 0
                assert display.gate_motions[(6, 4)][1] == 0
                assert not display.interaction_regions
            if capture and now in (.24, 1.1):
                save_frame(capture / ("moving.png" if now == .24 else "arrived.png"))
            p.update_canvas()
        assert display.plate_depths[(5, 1)] == 1
        assert display.gate_motions[(6, 4)][1] == 1
    finally:
        if display:
            display.close()
        p.close_canvas()


def check_inputs(levels):
    games, displays = [], []
    now = [0.0]
    original_initialize = view.View.__init__

    def initialize(display):
        original_initialize(display)
        displays.append(display)

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            if level.id == levels[5].id:
                for action in SOLUTIONS[level.id][:5]:
                    assert self.act(action)
            games.append(self)

    def expect(moves, busy=False, stage=5, navigating=False):
        game = games[-1]
        assert game.level.id == levels[stage].id
        assert game.state.moves == moves, (game.state.moves, moves)
        assert len(game.history) == moves
        assert displays[-1].transporting(game, now[0]) == busy
        assert displays[-1].navigation.active == navigating
        if stage == 5 and moves == 6:
            assert game.state.items[(5, 1)] == "part"
            assert game.gate_status((6, 4)) == "open"
        if stage == 5 and moves == 5:
            assert game.state.carrying == "part" and game.state.player == (3, 3)
            assert game.gate_status((6, 4)) == "closed"

    def prepare_navigation():
        expect(7)
        game = games[-1]
        game.restart()
        game.state.items[(3, 3)] = game.state.items.pop((2, 2))
        game.state.player = (5, 3)
        displays[-1].reset_player()

    steps = deque([
        (0, [p.SDLK_e], lambda: expect(6, True)),
        (.02, [p.SDLK_RIGHT, p.SDLK_e, p.SDLK_SPACE, p.SDLK_b, "click"], lambda: expect(6, True)),
        (.05, [p.SDLK_z], lambda: expect(5)),
        (.08, [p.SDLK_e], lambda: expect(6, True)),
        (.1, [p.SDLK_r], lambda: expect(0)),
        (.12, [p.SDLK_6], lambda: expect(5)),
        (.14, [p.SDLK_SPACE], lambda: expect(6, True)),
        (.16, [p.SDLK_1], lambda: expect(0, stage=0)),
        (.18, [p.SDLK_6], lambda: expect(5)),
        (.2, [p.SDLK_e], lambda: expect(6, True)),
        (.9, [p.SDLK_RIGHT], prepare_navigation),
        (1, ["path"], lambda: expect(1, True, navigating=True)),
        (1.2, [], lambda: expect(1, True, navigating=True)),
        (1.34, [], lambda: expect(2, True)),
        (1.52, [], lambda: expect(2)),
        (1.7, [p.SDLK_ESCAPE], None),
    ])
    original_events = p.get_events
    pending = None

    def events():
        nonlocal pending
        if pending:
            pending()
        now[0], keys, pending = steps.popleft()
        for key in keys:
            event = p.SDL_Event()
            if key in ("click", "path"):
                x, y = view.IsoBoard(10, 10).screen((4, 3) if key == "click" else (5, 1))
                event.type = p.SDL_MOUSEBUTTONDOWN
                event.button.button = p.SDL_BUTTON_LEFT
                event.button.x, event.button.y = int(x), int(view.HEIGHT - 1 - y)
            else:
                event.type = p.SDL_KEYDOWN
                event.key.state = p.SDL_PRESSED
                event.key.keysym.sym = key
            assert p.SDL_PushEvent(ctypes.byref(event)) == 1
        return original_events()

    with patch.object(view, "Game", ObservedGame), patch.object(view.View, "__init__", initialize), \
            patch.object(view, "perf_counter", side_effect=lambda: now[0]), \
            patch.object(p, "get_events", events):
        view.run(levels, index=5, show_title=False)
    assert not steps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    levels = load_levels()
    check_frames(levels, args.capture)
    check_inputs(levels)
    print("Automatic belt SDL smoke OK: ten animation samples, support height, plate/gate arrival, "
          "single action/history, movement/interaction/click lock, undo/restart/room switch, input/navigation resume.")


if __name__ == "__main__":
    main()
