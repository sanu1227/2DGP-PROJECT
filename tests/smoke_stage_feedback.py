"""방 입장·완료 연출과 실제 다음 방 입력을 SDL로 검사한다."""

from copy import deepcopy
import ctypes
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.model import Game
from game.stage_feedback import StageFeedback, ENTRY_SECONDS
from tests.smoke_onboarding import capture
from tests.smoke_play_menu import key, click, pixels
from tests.solutions import SOLUTIONS


def render_checks(levels):
    p.open_canvas(view.WIDTH, view.HEIGHT, sync=True)
    display = None
    text = view.View.text
    folder = Path("docs/screenshots/stage-feedback")

    def checked_text(display, x, y, value, size=18, color=view.INK):
        width = ctypes.c_int()
        p.TTF_SizeUTF8(display.fonts[size].font, str(value).encode(), ctypes.byref(width), None)
        assert 0 <= x and x + width.value <= view.WIDTH, (value, x, width.value)
        assert 0 <= y <= view.HEIGHT
        for ch in str(value):
            if ch.isprintable():
                assert p.TTF_GlyphIsProvided(display.fonts[size].font, ord(ch)), (value, ch)
        text(display, x, y, value, size, color)

    try:
        display = view.View()
        feedback = StageFeedback()
        game = Game(levels[3])
        with patch.object(view, "perf_counter", return_value=10):
            feedback.update(game, display.now())
        with patch.object(view, "perf_counter", return_value=10.4), patch.object(view.View, "text", checked_text):
            display.draw(game, 3, len(levels))
            feedback.draw(display, game, 3, len(levels))
            capture(folder / "entry.png")
            initial = pixels()
            display.pause()
        with patch.object(view, "perf_counter", return_value=110):
            display.draw(game, 3, len(levels))
            feedback.draw(display, game, 3, len(levels))
            assert initial == pixels(), "메뉴 대기 중 입장 연출 시간이 소모됨"
            display.resume()
        with patch.object(view, "perf_counter", return_value=110 + ENTRY_SECONDS), patch.object(feedback, "draw_entry") as entry:
            feedback.draw(display, game, 3, len(levels))
            entry.assert_not_called()

        for index in (0, 3, 7):
            level = levels[index]
            if index == 3:
                level = replace(level, action_limit=len(SOLUTIONS[level.id]))
            game = Game(level)
            for action in SOLUTIONS[level.id]:
                assert game.act(action)
            assert game.state.cleared
            state = deepcopy(game.state)
            feedback.update(game, display.now())
            with patch.object(view.View, "text", checked_text):
                display.draw(game, index, len(levels))
                feedback.draw(display, game, index, len(levels))
            capture(folder / f"clear-{index + 1:02d}.png")
            assert game.state == state
            assert game.remaining_actions == (None if index == 0 else 0 if index == 3 else 2)
            assert game.undo()
            feedback.update(game, display.now())
            assert feedback.completed_at is None
            assert game.act(SOLUTIONS[level.id][-1])
            feedback.update(game, display.now())
            assert feedback.completed_at is not None
            game.restart()
            feedback.enter(game, display.now())
            assert feedback.completed_at is None and game.state.moves == 0
    finally:
        if display:
            display.close()
        p.close_canvas()


def input_checks(levels):
    games = []
    frame = -1
    update = p.update_canvas
    final_key = {"left": p.SDLK_a, "right": p.SDLK_d, "up": p.SDLK_w, "down": p.SDLK_s,
                 "interact": p.SDLK_e}[SOLUTIONS[levels[0].id][-1]]
    batches = [
        ([key(p.SDLK_ESCAPE)], 0, False),  # 첫 장치 안내를 닫는다.
        ([key(final_key), key(p.SDLK_SPACE)], 0, True),
        ([key(p.SDLK_z)], 0, False),
        ([key(final_key)], 0, True),
        ([key(p.SDLK_ESCAPE)], 0, True),
        ([key(p.SDLK_ESCAPE)], 0, True),
        ([click(800, 272), key(p.SDLK_d)], 1, False),
        ([key(p.SDLK_ESCAPE)], 1, False),
        ([key(p.SDLK_8)], 7, True),
        ([key(p.SDLK_ESCAPE)], 7, True),
        ([click(800, 272), key(p.SDLK_d)], 0, False),
        ([key(p.SDLK_r)], 0, False),
        ([SimpleNamespace(type=p.SDL_QUIT)], 0, False),
    ]

    class ObservedGame(Game):
        def __init__(self, level):
            super().__init__(level)
            actions = SOLUTIONS[level.id] if level.id == levels[7].id else SOLUTIONS[level.id][:-1] if not games else []
            for action in actions:
                assert self.act(action)
            games.append(self)

    def events():
        nonlocal frame
        frame += 1
        assert frame < len(batches)
        return batches[frame][0]

    def checked_update():
        if frame >= 0:
            _, index, cleared = batches[frame]
            assert games[-1].level.id == levels[index].id, frame
            assert games[-1].state.cleared == cleared, frame
            if frame in (6, 7, 10, 11):
                assert games[-1].state.moves == 0, frame
        update()

    with patch.object(view, "Game", ObservedGame), patch.object(p, "get_events", events), \
            patch.object(p, "update_canvas", checked_update):
        view.run(levels, show_title=False)
    assert frame == len(batches) - 1


def main():
    levels = load_levels()
    render_checks(levels)
    input_checks(levels)
    print("Stage feedback smoke OK: entry timer/pause, real clear metrics, unlimited/zero remaining, undo/re-clear/restart, same-batch isolation, mouse next and final-room replay, glyphs/layout.")


if __name__ == "__main__":
    main()
