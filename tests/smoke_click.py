"""선택 검사: python -m tests.smoke_click (실제 SDL 마우스·View·장치 그림).

SDL 이벤트와 제어된 시계로 클릭 이동을 검사한다. 운영체제의 물리 입력은 제외한다.
"""

from collections import deque
import ctypes
from math import ceil, floor
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard


def main():
    level = load_levels()[0]
    board, reference = IsoBoard(level.width, level.height), Game(level)
    games, views, expected_calls = [], [], []
    # time, real SDL input, expected model action, remaining navigation
    steps = deque([
        (0, None, None, False),  # Populate actual object hit regions first.
        (0.05, ("motion", (3, 2)), None, False),
        (0.10, ("pixel", (300, view.HEIGHT - 40)), None, False),
        (0.15, ("pixel", (10, 450)), None, False),
        (0.20, ("floor", (3, 2)), "down", True),
        (0.25, ("right", (3, 2)), None, False),
        (0.40, None, None, False),
        (0.50, ("floor", (3, 2)), "right", True),
        (0.55, ("floor", (4, 2)), None, True),  # Retarget before interpolation ends.
        (0.65, None, None, True),
        (0.70, None, "right", True),
        (0.90, None, "right", False),
        (1.10, ("object", (2, 2)), "left", True),
        (1.30, None, "left", False),
        (1.50, ("object", (2, 2)), None, False),
        (1.60, ("floor", (3, 2)), "right", False),
        (1.65, ("floor", (4, 2)), None, True),
        (1.70, ("key", p.SDLK_a), "left", False),
        (1.90, None, None, False),
        (2.00, ("key", p.SDLK_z), "undo", False),
        (2.10, ("key", p.SDLK_r), "restart", False),
    ])
    route = ["down"] + ["right"] * 5 + ["down"] * 4 + ["left"] * 3 + ["down"]
    for index, action in enumerate(route):
        steps.append((2.3 + index * 0.2, ("object", (3, 7)) if index == 0 else None,
                      action, index + 1 < len(route)))
    steps.extend(((5.3, ("motion", (2, 2)), None, False),
                  (5.5, ("close", None), None, False)))
    now, current = 0, None
    original_init, original_events, original_update = view.View.__init__, p.get_events, p.update_canvas

    class ObservedGame(Game):
        def __init__(self, selected):
            super().__init__(selected)
            self.calls = []
            games.append(self)

        def act(self, action):
            self.calls.append(action)
            return super().act(action)

    def initialize(display):
        original_init(display)
        views.append(display)

    def events():
        nonlocal now, current
        now, command, action, active = steps.popleft()
        current = active
        if action == "undo":
            assert reference.undo()
        elif action == "restart":
            reference.restart()
        elif action:
            assert reference.act(action)
            expected_calls.append(action)
        if command is not None:
            kind, value = command
            event = p.SDL_Event()
            window = p.SDL_GetWindowID(p.window)
            if kind == "close":
                event.type = p.SDL_QUIT
            elif kind == "key":
                event.type, event.key.windowID = p.SDL_KEYDOWN, window
                event.key.state, event.key.repeat, event.key.keysym.sym = p.SDL_PRESSED, 0, value
            else:
                if kind == "pixel":
                    sx, sy = value
                elif kind == "object":
                    display = views[-1]
                    candidates = []
                    for region, mask in display.hit_masks.items():
                        pos, (left, bottom, right, top) = region
                        if pos != value:
                            continue
                        for sy in range(ceil(top) - 1, floor(bottom) - 1, -1):
                            for sx in range(ceil(left), ceil(right)):
                                if (display.art.hit_test(*mask[:4], (sx, sy), *mask[4:])
                                        and display.pick_cell(games[-1], sx, sy) == value
                                        # The grounded fragment now fits inside its own tile.
                                        # Use the tall lever to verify picking above another tile.
                                        and (now != 2.30 or board.pick(sx, sy) != value)):
                                    candidates.append((sy, sx))
                    assert candidates, (now, value, "No visible opaque sprite pixel")
                    sy, sx = max(candidates)
                else:
                    sx, sy = board.screen(value)
                    if kind == "floor":
                        assert views[-1].pick_cell(games[-1], sx, sy) == value
                x, y = round(sx), round(view.HEIGHT - 1 - sy)
                if kind == "motion":
                    event.type, event.motion.windowID = p.SDL_MOUSEMOTION, window
                    event.motion.x, event.motion.y = x, y
                else:
                    event.type, event.button.windowID = p.SDL_MOUSEBUTTONDOWN, window
                    event.button.button = p.SDL_BUTTON_RIGHT if kind == "right" else p.SDL_BUTTON_LEFT
                    event.button.state, event.button.x, event.button.y = p.SDL_PRESSED, x, y
            assert p.SDL_PushEvent(ctypes.byref(event)) == 1
        return original_events()

    def update():
        original_update()
        if current is None:
            return
        if now == 0:
            # The transparent corner of the front wall must not steal this floor click.
            front_floor = level.exit
            assert views[-1].pick_cell(games[-1], *board.screen(front_floor)) == front_floor
        assert games[-1].state == reference.state, (now, games[-1].state, reference.state)
        assert games[-1].history == reference.history
        assert games[-1].calls == expected_calls, (now, games[-1].calls, expected_calls)
        assert views[-1].navigation.active == current, (now, views[-1].navigation.path)
        assert len(games[-1].history) == games[-1].state.moves

    # 자동 장치 안내는 smoke_device_guide에서 별도로 검사한다.
    with patch.object(view.PlayMenu, "offer"), \
            patch.object(view, "Game", ObservedGame), patch.object(view.View, "__init__", initialize), \
            patch.object(view, "perf_counter", lambda: now), patch.object(p, "get_events", events), \
            patch.object(p, "update_canvas", update):
        view.run([level], show_title=False)
    assert not steps and len(games) == 1
    assert games[0].state.carrying is None and not games[0].state.active
    assert games[0].state.player == (3, 7) and "interact" not in games[0].calls
    print("Native click smoke OK: alpha-aware floor/object/device picking, preview/UI no-turn, cancel, retarget delay, keyboard/undo/restart, no automatic interact.")


if __name__ == "__main__":
    main()
