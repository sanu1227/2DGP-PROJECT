"""선택 검사: python -m tests.smoke_controls (실제 SDL, 제어된 애니메이션 시계).

WASD·빠른 모서리 이동의 실제 worker 그리기 좌표를 검사한다.
SDL 이벤트 전달을 검사하며 운영체제의 물리 키보드 전달은 검사하지 않는다.
"""

from collections import deque
from copy import deepcopy
import ctypes
from dataclasses import replace
from math import isclose
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.art import Art
from game.levels import load_levels
from game.model import Game
from game.projection import BoardProjection


def main():
    source = load_levels()[5]
    untouched = deepcopy(source)
    items = dict(source.initial_items)
    items[(3, 3)] = items.pop((2, 2))  # A live belt exposes accidental extra model ticks.
    level = replace(source, start=(2, 2), initial_items=items)
    reference, games = Game(level), []
    projection = BoardProjection(level.width, level.height)
    steps = deque([(0, None, (2, 2), "se")])
    previous = (2, 2)
    for time, (key, target, facing) in enumerate(((p.SDLK_w, (2, 1), "ne"),
            (p.SDLK_a, (1, 1), "nw"), (p.SDLK_s, (1, 2), "sw"),
            (p.SDLK_d, (2, 2), "se")), start=1):
        midpoint = tuple((a + b) / 2 for a, b in zip(previous, target))
        steps.extend(((time, key, previous, facing), (time + 0.07, None, midpoint, facing),
                      (time + 0.15, None, target, facing)))
        previous = target
    steps.extend(((5, p.SDLK_w, (2, 2), "ne"),
                  (5.035, p.SDLK_d, (2, 1.84375), "ne"),
                  (5.07, None, (2, 1.5), "ne"), (5.14, None, (2, 1), "se"),
                  (5.175, None, (2.5, 1), "se"), (5.22, None, (3, 1), "se"),
                  (6, p.SDLK_z, (2, 1), "se"), (7, p.SDLK_r, (2, 2), "se"),
                  (8, (p.SDLK_w, 1), (2, 2), "se"), (9, p.SDLK_ESCAPE, (2, 2), "se")))
    now, current, worker = 0, None, None
    actions = {p.SDLK_w: "up", p.SDLK_a: "left", p.SDLK_s: "down", p.SDLK_d: "right"}
    original_events, original_update, original_draw = p.get_events, p.update_canvas, Art.draw

    class ObservedGame(Game):
        def __init__(self, selected):
            super().__init__(selected)
            games.append(self)

    def draw(art, name, sx, sy, *args, **kwargs):
        nonlocal worker
        if name.startswith("worker_"):
            worker = (name, sx, sy)
        return original_draw(art, name, sx, sy, *args, **kwargs)

    def events():
        nonlocal now, current, worker
        now, key, position, facing = steps.popleft()
        current, worker = (position, facing), None
        if key is not None:
            key, repeat = key if isinstance(key, tuple) else (key, 0)
            if not repeat and key in actions:
                assert reference.act(actions[key])
            elif key == p.SDLK_z:
                assert reference.undo()
            elif key == p.SDLK_r:
                reference.restart()
            event = p.SDL_Event()
            event.type, event.key.windowID = p.SDL_KEYDOWN, p.SDL_GetWindowID(p.window)
            event.key.state, event.key.repeat, event.key.keysym.sym = p.SDL_PRESSED, repeat, key
            assert p.SDL_PushEvent(ctypes.byref(event)) == 1
        return original_events()

    def update():
        original_update()
        if current is None:  # open_canvas presents its initialization frames first.
            return
        position, facing = current
        assert worker is not None
        assert worker[0].startswith(f"worker_{facing}_"), (now, worker, facing)
        assert all(isclose(a, b, abs_tol=1e-7) for a, b in zip(worker[1:], projection.screen(position))), (now, worker, position)
        assert games[-1].state == reference.state, (now, games[-1].state, reference.state)
        assert games[-1].history == reference.history
        assert len(games[-1].history) == games[-1].state.moves

    with patch.object(view, "Game", ObservedGame), patch.object(view, "perf_counter", lambda: now), \
            patch.object(Art, "draw", draw), patch.object(p, "get_events", events), patch.object(p, "update_canvas", update):
        view.run([level])
    assert not steps and len(games) == 1 and source == untouched
    print("Native controls OK: WASD axes, queued corner/facing, one action per belt tick, undo/reset, repeat filtering.")


if __name__ == "__main__":
    main()
