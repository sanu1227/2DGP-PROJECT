"""선택 검사: 실제 SDL 창에 키 이벤트를 넣어 모든 방의 UI 흐름을 재생한다.

실행: python -m tests.smoke_window
실물 키보드나 자동화 도구의 운영체제 입력 전달까지 검증하지는 않는다.
"""

from collections import deque
import ctypes
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.model import Game
from tests.test_game import SOLUTIONS


def main():
    levels = load_levels()
    games = []
    displays = []
    original_initialize = view.View.__init__

    def initialize(display):
        original_initialize(display)
        assert not display.show_coordinates
        displays.append(display)

    def expect_coordinates(visible):
        expect(0)
        assert displays[-1].show_coordinates == visible

    def expect_room(stage):
        expect(0, stage=stage)
        display = displays[-1]
        assert display.motion is None and not display.navigation.active
        assert not games[-1].history
        assert games[-1].state.player == levels[stage].start
        assert not display.show_coordinates
        # Every tile, including walls, must receive its own data coordinate.
        with patch.object(display, "text") as labels:
            display.coordinate_overlay(levels[stage], view.IsoBoard(levels[stage].width, levels[stage].height))
        assert [call.args[2] for call in labels.call_args_list] == [
            f"({x},{y})" for y in range(levels[stage].height) for x in range(levels[stage].width)
        ]

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            games.append(self)

    def expect(moves, carrying=None, cleared=False, stage=0):
        game = games[-1]
        assert game.level.id == levels[stage].id
        assert game.state.moves == moves, (game.state.moves, moves)
        assert game.state.carrying == carrying
        assert game.state.cleared == cleared
        assert len(game.history) == moves

    # 두 이동 방식, 상호작용, 내려놓기, 두 undo 키, 재시작을 검사한다.
    steps = deque([
        (p.SDLK_F2, lambda: expect_coordinates(True)),
        (p.SDLK_F2, lambda: expect_coordinates(False)),
        (p.SDLK_d, lambda: expect(1)),
        (p.SDLK_DOWN, lambda: expect(2)),
        (p.SDLK_e, lambda: expect(3, "part")),
        (p.SDLK_q, lambda: expect(3, "part")),  # Removed key must not drop or consume a turn.
        (p.SDLK_b, lambda: expect(3, "part")),
        (p.SDLK_e, lambda: expect(4)),
        (p.SDLK_BACKSPACE, lambda: expect(3, "part")),
        (p.SDLK_z, lambda: expect(2)),
        (p.SDLK_r, lambda: expect(0)),
    ])
    # A same-room shortcut resets carried items, history, and unfinished walking.
    steps.extend([
        (p.SDLK_d, None), (p.SDLK_DOWN, None), (p.SDLK_e, None),
        (p.SDLK_1, lambda: expect_room(0)),
        (p.SDLK_d, None),
    ])
    for stage in (5, 4, 3, 2, 1, 0):
        steps.append((p.SDLK_1 + stage, lambda stage=stage: expect_room(stage)))
    keys = {"up": p.SDLK_w, "down": p.SDLK_s, "left": p.SDLK_a,
            "right": p.SDLK_RIGHT, "interact": p.SDLK_SPACE}
    for index, level in enumerate(levels):
        actions = SOLUTIONS[level.id]
        for action in actions:
            steps.append((keys[action], None))
        key, _ = steps.pop()
        steps.append((key, lambda count=len(actions), stage=index: expect(count, cleared=True, stage=stage)))
        steps.append((p.SDLK_RETURN, lambda stage=(index + 1) % len(levels): expect(0, stage=stage)))
    steps.append((p.SDLK_ESCAPE, None))

    original_events = p.get_events
    pending_check = None

    def scripted_events():
        nonlocal pending_check
        if pending_check:
            pending_check()
            pending_check = None
        if displays[-1].transporting(games[-1]):
            return original_events()
        key, pending_check = steps.popleft()
        event = p.SDL_Event()
        event.type = p.SDL_KEYDOWN
        event.key.windowID = p.SDL_GetWindowID(p.window)
        event.key.state = p.SDL_PRESSED
        event.key.repeat = 0
        event.key.keysym.sym = key
        if p.SDL_PushEvent(ctypes.byref(event)) != 1:
            raise RuntimeError("SDL 검사 이벤트를 넣을 수 없습니다.")
        return original_events()

    with patch.object(view, "Game", ObservedGame), patch.object(p, "get_events", scripted_events), \
            patch.object(view.View, "__init__", initialize):
        view.run(levels, show_title=False)
    assert not steps
    assert len(games) == len(levels) + 8
    print(f"Native SDL smoke OK: {len(levels)} clears, coordinates/F2, shortcuts 1-6, E/Space drop, Q/B ignored, undo, restart, next/replay, Escape.")


if __name__ == "__main__":
    main()
