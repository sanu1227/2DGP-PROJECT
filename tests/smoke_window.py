"""선택 검사: 실제 SDL 창에 키 이벤트를 넣어 세 방의 UI 흐름을 재생한다.

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
        (p.SDLK_d, lambda: expect(1)),
        (p.SDLK_DOWN, lambda: expect(2)),
        (p.SDLK_e, lambda: expect(3, "part")),
        (p.SDLK_q, lambda: expect(4)),
        (p.SDLK_BACKSPACE, lambda: expect(3, "part")),
        (p.SDLK_z, lambda: expect(2)),
        (p.SDLK_r, lambda: expect(0)),
    ])
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

    with patch.object(view, "Game", ObservedGame), patch.object(p, "get_events", scripted_events):
        view.run(levels)
    assert not steps
    assert len(games) == 4
    print("Native SDL smoke OK: 3 clears, carry/drop, undo, restart, next/replay, Escape.")


if __name__ == "__main__":
    main()
