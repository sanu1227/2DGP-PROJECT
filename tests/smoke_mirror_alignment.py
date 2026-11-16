"""네 거울 방향 × 네 입사 방향에서 방출·표시·클릭을 검사한다."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'
from copy import deepcopy
import argparse
from ctypes import byref, c_ubyte
from dataclasses import replace
from math import dist
from pathlib import Path
from unittest.mock import patch
import pico2d.pico2d as p
import game.view as display
from game.art import MAGIC_BEAM_HEIGHT
from game.levels import DIRECTIONS, load_levels
from game.model import Game
from game.mechanics import trace_magic
from game.navigation import IsoBoard
from game.optics import trace_display_magic
from tests.solutions import SOLUTIONS
from tests.smoke_gate_animation import save_frame
from tests.smoke_placement import visible_item_pixel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    args = parser.parse_args()
    levels = load_levels()
    level = replace(levels[4], id='mirror_alignment_probe', title='거울 방향 확인', hint='거울 면과 빛의 꺾임을 비교하세요.',
                    action_limit=None, width=8, height=8, start=(1, 6), exit=(6, 6), rubble=frozenset(),
                    walls=frozenset((x, y) for x in range(8) for y in range(8) if x in (0, 7) or y in (0, 7)),
                    mirrors=frozenset({(3, 3)}), gates={}, chutes={}, plates=frozenset(), traps=frozenset(),
                    levers=frozenset(), benches=frozenset(), posts=frozenset(), initial_items={})
    projection = IsoBoard(8, 8)
    sx, sy = projection.screen((3, 3))
    scale = projection.half_width * 2 / 224
    center = sx, sy + MAGIC_BEAM_HEIGHT * scale
    p.open_canvas(display.WIDTH, display.HEIGHT, sync=True)
    view = None
    try:
        view = display.View()
        for rotation, outgoing in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
            for direction, incoming in DIRECTIONS.items():
                source = tuple(3 - 2 * d for d in incoming)
                receiver = tuple(3 + 2 * d for d in outgoing)
                receivers = frozenset() if receiver == source else frozenset({receiver})
                game = Game(replace(level, sources={source: direction}, receivers=receivers,
                                    device_labels={pos: '수신기' for pos in receivers}))
                if rotation:
                    game.state.mirror_rotations[(3, 3)] = rotation
                before = deepcopy(game.state)
                segments, powered = trace_magic(game.level, game.state)
                assert powered == receivers
                assert segments[2] == ((3, 3), tuple(3 + d for d in outgoing))
                with patch('game.view.perf_counter', return_value=10), patch('game.view.line', wraps=display.line) as lines:
                    view.draw(game, 0, 1)
                tint = tuple(c_ubyte() for _ in range(3))
                p.SDL_GetTextureColorMod(view.art.atlases['gimmicks'].texture, *(byref(value) for value in tint))
                assert tuple(value.value for value in tint) == (255, 255, 255), '뒷면 색이 다른 기믹에 남았습니다.'
                beams = [call.args[:4] for call in lines.call_args_list if call.args[-1] == (244, 185, 255)]
                display_segments, display_powered = trace_display_magic(game.level, game.state, game.state.mirror_rotations)
                assert display_powered == powered
                expected_beams = []
                for start, end in display_segments:
                    x1, y1 = projection.screen(start); x2, y2 = projection.screen(end)
                    expected_beams.append((x1, y1 + MAGIC_BEAM_HEIGHT * scale, x2, y2 + MAGIC_BEAM_HEIGHT * scale))
                assert len(beams) == len(expected_beams)
                assert all(dist(actual, expected) < 1e-8 for actual, expected in zip(beams, expected_beams))
                assert len(beams) == 2 and dist(beams[0][2:], beams[1][:2]) < 1e-8
                assert view.pick_cell(game, *center) == (3, 3)
                assert not view.art.hit_test('mirror', sx, sy, scale, (sx, sy + 180 * scale), rotation=rotation)
                arrow_start, tip, *_ = view.art.mirror_arrow(sx, sy, scale, rotation)
                next_x, next_y = projection.screen(tuple(3 + d for d in outgoing))
                ax, ay = tip[0] - arrow_start[0], tip[1] - arrow_start[1]
                dx, dy = next_x - sx, next_y - sy
                assert abs(ax * dy - ay * dx) < 1e-8 and ax * dx + ay * dy > 0
                assert view.pick_cell(game, *tip) == (3, 3)
                assert game.state == before
                if args.capture_dir and direction == 'right':
                    save_frame(args.capture_dir / f'rotation-{rotation}.png')

        for index in (4, 5, 7):
            game = Game(levels[index])
            for action in SOLUTIONS[game.level.id]:
                assert game.act(action)
                if trace_magic(game.level, game.state)[1]:
                    break
            with patch('game.view.perf_counter', return_value=1000):
                view.draw(game, index, len(levels))
            for mirror in game.level.mirrors:
                visible_item_pixel(view, game, mirror, 'mirror')
            if args.capture_dir:
                save_frame(args.capture_dir / f'stage-{index+1:02}.png')
        print('Mirror alignment OK: 4 output poses x 4 incoming directions, center contact, arrow clicks, rooms 5/6/8.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
