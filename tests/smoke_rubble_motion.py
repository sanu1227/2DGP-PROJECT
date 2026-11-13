"""실제 밀기 입력의 보간·상판 진입·빠른 재입력·정지·되돌리기를 SDL로 검사한다."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'
import argparse
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import pico2d.pico2d as p
from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard
from game.view import View, WIDTH, HEIGHT, PUSH_SECONDS, PLATE_SECONDS
from tests.smoke_gate_animation import save_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    game = Game(load_levels()[3])
    game.state.player = (2, 2)
    source, target = (2, 3), (2, 4)
    projection = IsoBoard(game.level.width, game.level.height)
    scale = projection.half_width * 2 / 224
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        view = View()

        def frame(now):
            state = deepcopy(game.state)
            with patch('game.view.perf_counter', return_value=now), \
                    patch.object(view.art, 'draw', wraps=view.art.draw) as draw:
                view.draw(game, 3, 8)
            assert game.state == state
            return next(call.args[1:3] for call in draw.call_args_list if call.args[0] == 'push_rubble')

        def move(now, action):
            previous = game.state
            assert game.act(action), game.message
            with patch('game.view.perf_counter', return_value=now):
                view.animate_move(game, previous, action)

        initial = frame(0)
        move(1, 'down')
        assert frame(1) == initial, '밀기 시작 순간 잔해가 튀었습니다.'
        with patch('game.view.perf_counter', return_value=1 + PUSH_SECONDS / 2):
            position, height = view.rubble_pose(game, target, view.now())
            assert abs(position[1] - 3.5) < 1e-8 and 0 < height < 60
            player = view.player_position(game.state.player, view.now())
            assert abs(player[1] - 2.5) < 1e-8, '캐릭터와 잔해 속도가 다릅니다.'
        frame(1.1)
        assert view.plate_depths[target] == 0, '잔해 도착 전에 발판이 눌렸습니다.'
        frame(1.22)
        assert 0 < view.plate_depths[target] < 1
        end = 1 + PUSH_SECONDS * .65 + PLATE_SECONDS
        frame(end + .001)
        assert view.plate_depths[target] == 1
        x, y = projection.screen(target)
        actual = frame(2)
        assert abs(actual[0] - x) < 1e-8 and abs(actual[1] - y - 32 * scale) < 1e-8

        # 다시 시작해 일정 간격의 실제 렌더 프레임을 남긴다.
        assert game.undo()
        view.reset_player()
        view.reset_plates()
        frame(3)
        move(4, 'down')
        for i in range(31):
            frame(4 + i / 60)
            if args.capture:
                save_frame(args.capture / f'frame-{i:02d}.png')

        # 평지 연속 밀기도 현재 표시 위치에서 이어지며, 일시정지 시간은 제외한다.
        game = Game(replace(game.level, id='push_fixture', walls=frozenset(), plates=frozenset(), gates={},
                            rubble=frozenset({(2, 3)})))
        game.state.player = (2, 2)
        view.reset_player()
        frame(5)
        move(6, 'down')
        before = frame(6.03)
        move(6.03, 'down')
        assert frame(6.03) == before, '연속 밀기가 순간 이동했습니다.'
        frozen = frame(6.1)
        with patch('game.view.perf_counter', return_value=6.1):
            view.pause()
        assert frame(16.1) == frozen
        with patch('game.view.perf_counter', return_value=16.1):
            view.resume()
        assert frame(16.1) == frozen
        assert game.undo()
        view.reset_player()
        assert not view.rubble_motions and not view.plate_delays
        assert frame(17) == projection.screen((2, 4))
        game.restart()
        view.reset_player()
        assert frame(18) == projection.screen((2, 3))
        print('Rubble motion OK: smooth push, climb then press, rapid input, pause, undo, restart; no model mutation.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
