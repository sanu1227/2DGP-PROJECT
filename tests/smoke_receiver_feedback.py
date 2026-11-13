"""수신 표시의 실제 입력, 일시정지, 되돌리기와 세 방의 렌더링을 검사한다."""

import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'

from copy import deepcopy
from ctypes import byref, c_int
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pico2d.pico2d as p

from game import view
from game.levels import load_levels
from game.mechanics import trace_magic
from game.model import Game
from game.receiver_feedback import ReceiverFeedback, RECEIVE_SECONDS
from tests.smoke_gate_animation import save_frame
from tests.smoke_placement import visible_item_pixel
from tests.smoke_play_menu import key
from tests.solutions import SOLUTIONS

FOLDER = Path('docs/screenshots/receiver-feedback')


def input_checks(level):
    level = replace(level, id='receiver_probe', start=(3, 3), exit=(6, 6), action_limit=None,
                    sources={(1, 3): 'right'}, mirrors=frozenset({(3, 3)}), receivers=frozenset({(3, 5)}),
                    walls=frozenset(), traps=frozenset(), posts=frozenset(), benches=frozenset(),
                    levers=frozenset(), gates={}, chutes={}, plates=frozenset(), initial_items={},
                    device_labels={(3, 5): 'M1'})
    # 실제 run 입력 분기를 통과한다. 같은 연결은 다시 시작하지 않고, 30ms 재연결은 새 파동 하나만 만든다.
    steps = [
        (0, None, False, 1), (1, p.SDLK_e, True, 0), (1.2, None, True, .2 / RECEIVE_SECONDS),
        (1.2, p.SDLK_ESCAPE, True, .2 / RECEIVE_SECONDS),
        (11.2, None, True, .2 / RECEIVE_SECONDS),
        (11.2, p.SDLK_ESCAPE, True, .2 / RECEIVE_SECONDS),
        (11.3, None, True, .3 / RECEIVE_SECONDS), (12, None, True, 1),
        (12.1, p.SDLK_e, False, 1), (12.13, p.SDLK_e, True, 0),
        (12.2, p.SDLK_z, False, 1), (12.3, p.SDLK_e, True, 0),
        (12.4, p.SDLK_r, False, 1), (12.5, p.SDLK_e, True, 0),
        (12.6, p.SDLK_1, False, 1),
    ]
    frame, now, drawn = -1, 0, 0
    labels, current = [], []
    draw, text, feedback_draw = view.View.draw, view.View.text, ReceiverFeedback.draw

    def events():
        nonlocal frame, now, drawn
        frame += 1
        now, code, _, _ = steps[frame]
        drawn = 0
        labels.clear()
        return [] if code is None else [key(code)]

    def checked_draw(display, game, *args):
        state = deepcopy(game.state)
        current[:] = [display, game]
        draw(display, game, *args)
        assert game.state == state, '수신 연출이 게임 상태를 변경했습니다.'

    def checked_text(display, x, y, value, *args):
        labels.append(value)
        text(display, x, y, value, *args)

    def checked_feedback(effect, *args):
        nonlocal drawn
        before, after = c_int(), c_int()
        p.SDL_GetRenderDrawBlendMode(p.renderer, byref(before))
        feedback_draw(effect, *args)
        p.SDL_GetRenderDrawBlendMode(p.renderer, byref(after))
        assert before.value == after.value, '수신기의 합성 방식이 다른 그림에 남았습니다.'
        drawn += 1

    def check_frame():
        if frame < 0:
            return  # open_canvas도 첫 게임 프레임 전에 update_canvas를 호출한다.
        display, game = current
        _, _, powered, expected_progress = steps[frame]
        assert bool(trace_magic(game.level, game.state)[1]) == powered
        assert drawn == int(powered), (frame, drawn)
        label = 'M1 수신 완료' if powered else 'M1 수신 대기'
        assert label in labels, (frame, labels)
        progress = display.receiver_feedback.progress(game, (3, 5), display.now())
        assert abs(progress - expected_progress) < 1e-8, (frame, progress)
        if not powered or expected_progress == 1:
            assert not display.receiver_feedback.bursts, (frame, display.receiver_feedback.bursts)
        if frame == 2:
            visible_item_pixel(display, game, (3, 5), 'mana_receiver')

    with (patch.object(p, 'get_events', events), patch.object(p, 'update_canvas', check_frame),
          patch.object(view, 'perf_counter', side_effect=lambda: now),
          patch.object(view.PlayMenu, 'offer', return_value=None),
          patch.object(view.View, 'draw', checked_draw), patch.object(view.View, 'text', checked_text),
          patch.object(ReceiverFeedback, 'draw', checked_feedback)):
        view.run([level], show_title=False, smoke_frames=len(steps))


def capture_rooms(levels):
    p.open_canvas(view.WIDTH, view.HEIGHT)
    display = None
    try:
        display = view.View()
        for index in (4, 5, 7):
            game = Game(levels[index])
            display.reset_player()
            # 재생 전후 화면과 수신 파동을 같은 실제 풀이 위치에서 비교한다.
            for action in SOLUTIONS[game.level.id]:
                previous = game.state
                assert game.act(action)
                if trace_magic(game.level, game.state)[1]:
                    break
            assert game.undo()
            with patch.object(view, 'perf_counter', return_value=10):
                display.draw(game, index, len(levels))
            if index == 4:
                save_frame(FOLDER / 'waiting.png')
            previous = game.state
            assert game.act(action)
            display.receiver_feedback.changed(game, previous, 10)
            for name, now in [('arrival', 10.12), ('powered', 11)]:
                with patch.object(view, 'perf_counter', return_value=now):
                    display.draw(game, index, len(levels))
                for receiver in game.level.receivers:
                    visible_item_pixel(display, game, receiver, 'mana_receiver')
                save_frame(FOLDER / f'stage-{index + 1:02}-{name}.png')
    finally:
        if display:
            display.close()
        p.close_canvas()


if __name__ == '__main__':
    levels = load_levels()
    input_checks(levels[4])
    capture_rooms(levels)
    print('Receiver feedback OK: input, stable power, cutoff, 30ms reconnect, pause/resume, undo, restart, room change, blend restoration and rooms 5/6/8 clicks.')
