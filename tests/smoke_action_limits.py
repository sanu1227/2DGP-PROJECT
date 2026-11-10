"""Native SDL failure/recovery checks using the shipped 75-action room budget."""

from collections import deque
from copy import deepcopy
import ctypes
from pathlib import Path
from unittest.mock import patch
import argparse

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.model import Game
from tests.smoke_gate_animation import save_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    levels, games = load_levels(), []
    displays, snapshots = [], {}
    original_draw = view.View.draw

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            games.append(self)

    def draw(display, game, index, total):
        displays[:] = [display]
        with patch.object(display, "text", wraps=display.text) as text:
            original_draw(display, game, index, total)
        labels = [call.args[2] for call in text.call_args_list]
        if game.failed:
            assert "남은 행동 0 / 75" in labels
            assert any("실패" in label and "재시작" in label for label in labels)
            assert not display.interaction_regions and not display.navigation.active
            if args.capture and "failed" not in snapshots:
                save_frame(args.capture / "failed.png")
            snapshots.setdefault("failed", deepcopy(game.state))
        elif index == 0:
            assert "행동 무제한" in labels
        elif game.state.moves == 74:
            assert "남은 행동 1 / 75" in labels

    def expect(moves, failed=False, stage=1):
        game = games[-1]
        assert game.level.id == levels[stage].id
        assert game.state.moves == moves and game.failed == failed
        assert len(game.history) == moves
        if failed:
            assert game.state == snapshots["failed"]
        if args.capture and moves == 74 and "failed" in snapshots and "recovered" not in snapshots:
            save_frame(args.capture / "recovered.png")
            snapshots["recovered"] = True

    steps = deque([(p.SDLK_UP, lambda: expect(0))])  # Wall bump is free.
    steps.extend((p.SDLK_b, None) for _ in range(74))
    steps.append((p.SDLK_b, lambda: expect(75, True)))
    for key in (p.SDLK_RIGHT, p.SDLK_e, p.SDLK_q, p.SDLK_b, p.SDLK_RETURN, "click"):
        steps.append((key, lambda: expect(75, True)))
    steps.extend([
        (p.SDLK_z, lambda: expect(74)),
        (p.SDLK_b, lambda: expect(75, True)),
        (p.SDLK_BACKSPACE, lambda: expect(74)),
        (p.SDLK_r, lambda: expect(0)),
        (p.SDLK_b, lambda: expect(1)),
        (p.SDLK_1, lambda: expect(0, stage=0)),
        (p.SDLK_b, lambda: expect(1, stage=0)),
        (p.SDLK_2, lambda: expect(0)),
        (p.SDLK_ESCAPE, None),
    ])
    original_events, pending = p.get_events, None

    def events():
        nonlocal pending
        if pending:
            pending()
        key, pending = steps.popleft()
        event = p.SDL_Event()
        if key == "click":
            sx, sy = view.IsoBoard(10, 10).screen((4, 1))
            event.type = p.SDL_MOUSEBUTTONDOWN
            event.button.button = p.SDL_BUTTON_LEFT
            event.button.x, event.button.y = int(sx), int(view.HEIGHT - 1 - sy)
        else:
            event.type = p.SDL_KEYDOWN
            event.key.keysym.sym = key
            event.key.state = p.SDL_PRESSED
        assert p.SDL_PushEvent(ctypes.byref(event)) == 1
        return original_events()

    with patch.object(view, "Game", ObservedGame), patch.object(view.View, "draw", draw), \
            patch.object(p, "get_events", events):
        view.run(levels, index=1, show_title=False)
    assert not steps and "failed" in snapshots
    print("Action limit SDL smoke OK: real 75-action exhaustion, blocked inputs/click, "
          "Z/Backspace recovery, restart, room switch and unlimited tutorial HUD.")


if __name__ == "__main__":
    main()
