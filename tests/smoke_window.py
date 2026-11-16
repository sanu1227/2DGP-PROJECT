"""선택 검사: 실제 SDL 창에 키 이벤트를 넣어 모든 방의 UI 흐름을 재생한다.

실행: python -m tests.smoke_window
실물 키보드나 자동화 도구의 운영체제 입력 전달까지 검증하지는 않는다.
"""

import argparse
from collections import deque
import ctypes
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.model import Game
from tests.test_game import SOLUTIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-down", action="store_true", help="탑다운 화면과 부품 클릭도 검사")
    args = parser.parse_args()
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
            display.coordinate_overlay(levels[stage], display.projection(levels[stage]))
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
        (p.SDLK_e, lambda: expect(0)),
        (p.SDLK_SPACE, lambda: expect(0)),
        (p.SDLK_F2, lambda: expect_coordinates(True)),
        (p.SDLK_F2, lambda: expect_coordinates(False)),
        ("click_part" if args.top_down else p.SDLK_d, lambda: expect(1)),
        (p.SDLK_e, lambda: expect(2, "part")),
        (p.SDLK_q, lambda: expect(2, "part")),  # Removed key must not drop or consume a turn.
        (p.SDLK_b, lambda: expect(2, "part")),
        (p.SDLK_e, lambda: expect(3)),
        (p.SDLK_BACKSPACE, lambda: expect(2, "part")),
        (p.SDLK_z, lambda: expect(1)),
        (p.SDLK_r, lambda: expect(0)),
    ])
    # A same-room shortcut resets carried items, history, and unfinished walking.
    steps.extend([
        (p.SDLK_d, None), (p.SDLK_e, None),
        (p.SDLK_1, lambda: expect_room(0)),
        (p.SDLK_d, None),
    ])
    for stage in reversed(range(len(levels))):
        steps.append((p.SDLK_1 + stage, lambda stage=stage: expect_room(stage)))
    keys = {"up": p.SDLK_w, "down": p.SDLK_s, "left": p.SDLK_a,
            "right": p.SDLK_RIGHT, "interact": p.SDLK_SPACE}
    for index, level in enumerate(levels):
        actions = SOLUTIONS[level.id]
        for action in actions:
            steps.append((action if action.startswith("push_") else keys[action], None))
        key, _ = steps.pop()
        steps.append((key, lambda count=len(actions), stage=index: expect(count, cleared=True, stage=stage)))
        steps.append((p.SDLK_RETURN, lambda count=len(actions), stage=index: expect(count, cleared=True, stage=stage)))
        next_key = p.SDLK_e if index % 2 == 0 else p.SDLK_SPACE
        # Inputs from the same event batch must not act in the newly opened room.
        steps.append(((next_key, p.SDLK_d, p.SDLK_SPACE),
                      lambda stage=(index + 1) % len(levels): expect(0, stage=stage)))
    steps.append(("close", None))

    original_events = p.get_events
    pending_check = None

    def scripted_events():
        nonlocal pending_check
        if pending_check:
            pending_check()
            pending_check = None
        key, pending_check = steps.popleft()
        p.SDL_SetModState(p.KMOD_NONE)
        for queued_key in key if isinstance(key, tuple) else (key,):
            event = p.SDL_Event()
            window_id = p.SDL_GetWindowID(p.window)
            if queued_key == "click_part":
                display, game = displays[-1], games[-1]
                part = next(pos for pos, kind in game.state.items.items() if kind == "part")
                x, y = display.projection(game.level).screen(part)
                assert display.pick_cell(game, x, y) == part
                event.type, event.button.windowID = p.SDL_MOUSEBUTTONDOWN, window_id
                event.button.button, event.button.state = p.SDL_BUTTON_LEFT, p.SDL_PRESSED
                event.button.x, event.button.y = round(x), round(view.HEIGHT - 1 - y)
            elif queued_key == "close":
                event.type = p.SDL_QUIT
            else:
                if isinstance(queued_key, str) and queued_key.startswith("push_"):
                    p.SDL_SetModState(p.KMOD_SHIFT)
                    queued_key = keys[queued_key.removeprefix("push_")]
                event.type, event.key.windowID = p.SDL_KEYDOWN, window_id
                event.key.state, event.key.repeat = p.SDL_PRESSED, 0
                event.key.keysym.sym = queued_key
            if p.SDL_PushEvent(ctypes.byref(event)) != 1:
                raise RuntimeError("SDL 검사 이벤트를 넣을 수 없습니다.")
        return original_events()

    # 자동 장치 안내는 smoke_device_guide에서 별도로 검사한다.
    with patch.object(view.PlayMenu, "offer"), \
            patch.object(view, "Game", ObservedGame), patch.object(p, "get_events", scripted_events), \
            patch.object(view.View, "__init__", initialize):
        view.run(levels, show_title=False, top_down=args.top_down)
    assert not steps
    assert len(games) == 2 * len(levels) + 2
    print(f"Native SDL smoke OK: {len(levels)} clears, coordinates/F2, shortcuts 1-{len(levels)}, E/Space drop and next/replay, Q/B/Enter ignored, transition input isolation, undo, restart, window close.")


if __name__ == "__main__":
    main()
