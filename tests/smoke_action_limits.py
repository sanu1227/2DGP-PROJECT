"""Native SDL failure/recovery checks using the shipped room budget."""

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
from tests.test_game import SOLUTIONS


def check_feedback(levels, capture):
    """실제 풀이의 경고 경계·클리어와 운반 자세·클릭 영역을 검사한다."""
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    checked = 0
    try:
        display = view.View()
        for index, level in enumerate(levels):
            game = Game(level)
            limit = level.action_limit
            threshold = max(5, limit // 5) if limit else 0
            samples = {None, threshold + 1, threshold, 6, 5, 2}
            for action in [None, *SOLUTIONS[level.id]]:
                if action:
                    assert game.act(action), game.message
                if game.remaining_actions not in samples and not game.state.cleared:
                    continue
                before = deepcopy(game.state)
                with patch("game.view.perf_counter", return_value=10):
                    display.draw(game, index, len(levels))
                assert game.state == before
                tired = display.fatigue(game)
                expected = (0 if limit is None or game.state.cleared else
                            2 if game.remaining_actions <= 5 else
                            1 if game.remaining_actions <= threshold else 0)
                assert tired == expected
                region, mask = next((r, m) for r, m in display.hit_masks.items()
                                    if m[0].startswith("worker_"))
                left, bottom, right, top = region[1]
                assert any(display.art.hit_test(*mask[:4], (x, y), *mask[4:])
                           and display.pick_cell(game, x, y) == game.state.player
                           for x in range(int(left) + 2, int(right), 4)
                           for y in range(int(bottom) + 2, int(top), 4))
                badge = display.action_badge_bounds
                assert badge[1] > top
                assert display.pick_cell(game, (badge[0] + badge[2]) / 2,
                                         (badge[1] + badge[3]) / 2) is None
                assert all(badge[2] <= x1 or badge[0] >= x2 or badge[3] <= y1 or badge[1] >= y2
                           for x1, y1, x2, y2 in display.interaction_regions.values())
                with patch("game.view.perf_counter", return_value=10.2):
                    display.draw(game, index, len(levels))
                second = next(m for m in display.hit_masks.values() if m[0].startswith("worker_"))
                assert (mask[-1] != second[-1]) == bool(tired)
                assert game.state == before
                if capture and index == 1 and (game.remaining_actions in (threshold, 5) or game.state.cleared):
                    name = "cleared" if game.state.cleared else "tired" if tired == 1 else "critical"
                    save_frame(capture / f"{name}.png")
                checked += 1
            assert game.state.cleared and display.fatigue(game) == 0
            assert game.undo()
            assert display.fatigue(game) == (0 if limit is None else 2)
            game.restart()
            assert display.fatigue(game) == 0
        p.update_canvas()
        return checked
    finally:
        if display:
            display.close()
        p.close_canvas()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    levels, games = load_levels(), []
    budget = levels[1].action_limit
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
        assert "남은 행동" in labels
        assert ("무제한" if game.remaining_actions is None else str(game.remaining_actions)) in labels
        left, bottom, right, top = display.action_badge_bounds
        assert view.BOARD_BOTTOM < bottom < top < view.BOARD_TOP
        assert all(right <= x1 or left >= x2 or top <= y1 or bottom >= y2
                   for x1, y1, x2, y2 in display.interaction_regions.values())
        effort = {0: None, 1: "후우…", 2: "헉…", 3: "털썩…"}[display.fatigue(game)]
        assert not effort or effort in labels
        if game.failed:
            assert display.fatigue(game) == 3
            assert any("실패" in label and "재시작" in label for label in labels)
            assert not display.interaction_regions and not display.navigation.active
            if args.capture and "failed" not in snapshots:
                save_frame(args.capture / "failed.png")
            snapshots.setdefault("failed", deepcopy(game.state))
        elif index == 0:
            assert "무제한" in labels and display.fatigue(game) == 0
        elif game.state.moves == budget - 1:
            assert display.fatigue(game) == 2

    def expect(moves, failed=False, stage=1):
        game = games[-1]
        assert game.level.id == levels[stage].id
        assert game.state.moves == moves and game.failed == failed
        assert len(game.history) == moves
        if failed:
            assert game.state == snapshots["failed"]
        if args.capture and moves == budget - 1 and "failed" in snapshots and "recovered" not in snapshots:
            save_frame(args.capture / "recovered.png")
            snapshots["recovered"] = True

    steps = deque([(p.SDLK_UP, lambda: expect(0))])  # Wall bump is free.
    steps.extend((p.SDLK_RIGHT if index % 2 == 0 else p.SDLK_LEFT, None) for index in range(budget - 1))
    last_key = p.SDLK_RIGHT if (budget - 1) % 2 == 0 else p.SDLK_LEFT
    steps.append((last_key, lambda: expect(budget, True)))
    for key in (p.SDLK_RIGHT, p.SDLK_e, p.SDLK_q, p.SDLK_b, p.SDLK_RETURN, "click"):
        steps.append((key, lambda: expect(budget, True)))
    steps.extend([
        (p.SDLK_z, lambda: expect(budget - 1)),
        (last_key, lambda: expect(budget, True)),
        (p.SDLK_BACKSPACE, lambda: expect(budget - 1)),
        (p.SDLK_r, lambda: expect(0)),
        (p.SDLK_RIGHT, lambda: expect(1)),
        (p.SDLK_1, lambda: expect(0, stage=0)),
        (p.SDLK_RIGHT, lambda: expect(1, stage=0)),
        (p.SDLK_2, lambda: expect(0)),
        ("close", None),
    ])
    original_events, pending = p.get_events, None

    def events():
        nonlocal pending
        if pending:
            pending()
        key, pending = steps.popleft()
        event = p.SDL_Event()
        if key == "close":
            event.type = p.SDL_QUIT
        elif key == "click":
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
    checked = check_feedback(levels, args.capture)
    print(f"Action limit SDL smoke OK: real {budget}-action exhaustion, blocked inputs/click, "
          f"Z/Backspace recovery, restart, room switch; {checked} feedback states across eight rooms.")


if __name__ == "__main__":
    main()
