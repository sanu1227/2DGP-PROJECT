"""거울의 실제 표시 축·광선 접점·클릭을 양 방향과 네 입사 방향에서 검사한다."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'
from copy import deepcopy
from dataclasses import replace
from math import dist
from pathlib import Path
from unittest.mock import patch
import pico2d.pico2d as p
import game.view as display
from game.art import MAGIC_BEAM_HEIGHT
from game.levels import DIRECTIONS, load_levels
from game.model import Game
from game.mechanics import mirror_axis, trace_magic
from game.navigation import IsoBoard
from tests.solutions import SOLUTIONS
from tests.smoke_gate_animation import save_frame
from tests.smoke_placement import visible_item_pixel


def main():
    levels = load_levels()
    level = replace(levels[4], id='mirror_alignment_probe', title='거울 방향 확인', hint='거울 면과 빛의 꺾임을 비교하세요.',
                    action_limit=None, start=(1, 6), exit=(6, 6),
                    walls=frozenset((x, y) for x in range(8) for y in range(8) if x in (0, 7) or y in (0, 7)),
                    mirrors=frozenset({(3, 3)}), gates={}, chutes={}, traps=frozenset(),
                    levers=frozenset(), benches=frozenset(), posts=frozenset(), initial_items={})
    projection = IsoBoard(8, 8)
    sx, sy = projection.screen((3, 3))
    scale = projection.half_width * 2 / 224
    center = sx, sy + MAGIC_BEAM_HEIGHT * scale
    p.open_canvas(display.WIDTH, display.HEIGHT, sync=True)
    view = None
    try:
        view = display.View()
        for turned in (False, True):
            for direction, incoming in DIRECTIONS.items():
                tx, ty = mirror_axis(turned)
                normal = -ty, tx
                dot = sum(a * b for a, b in zip(incoming, normal))
                outgoing = tuple(int(v - dot * n) for v, n in zip(incoming, normal))
                source = tuple(3 - 2 * d for d in incoming)
                receiver = tuple(3 + 2 * d for d in outgoing)
                game = Game(replace(level, sources={source: direction}, receivers=frozenset({receiver}),
                                    device_labels={receiver: '수신기'}))
                if turned:
                    game.state.turned_mirrors.add((3, 3))
                before = deepcopy(game.state)
                segments, powered = trace_magic(game.level, game.state)
                assert powered == {receiver}
                assert next(end for start, end in segments if start == (3, 3)) == tuple(3 + d for d in outgoing)

                # 실제 표시한 면에 대한 반사 벡터와 게임의 출사 벡터를 비교한다.
                a, b = view.art.mirror_segment(sx, sy, scale, turned)
                assert dist(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), center) < 1e-8
                nx, ny = -(b[1] - a[1]), b[0] - a[0]
                ix, iy = incoming
                vx, vy = (ix - iy) * projection.half_width, -(ix + iy) * projection.half_height
                ratio = 2 * (vx * nx + vy * ny) / (nx * nx + ny * ny)
                ox, oy = outgoing
                expected = ((ox - oy) * projection.half_width, -(ox + oy) * projection.half_height)
                assert dist((vx - ratio * nx, vy - ratio * ny), expected) < 1e-8
                with patch('game.view.perf_counter', return_value=10), patch('game.view.line', wraps=display.line) as lines:
                    view.draw(game, 0, 1)
                beams = [call.args[:4] for call in lines.call_args_list if call.args[-1] == (244, 185, 255)]
                assert any(dist(ray[2:], center) < 1e-8 for ray in beams)
                assert any(dist(ray[:2], center) < 1e-8 for ray in beams)
                assert view.pick_cell(game, *center) == (3, 3)
                assert not view.art.hit_test('mirror', sx, sy, scale, (sx, sy + 140 * scale), turned)
                assert game.state == before
                if direction == 'right':
                    save_frame(Path('docs/screenshots/mirror-alignment') / f'after-{int(turned)}.png')

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
            save_frame(Path('docs/screenshots/compact-rooms') / f'stage-{index+1:02}-mirror.png')
        print('Mirror alignment OK: 2 poses x 4 incoming directions, displayed reflection plane, center contact, click and no stale panel hit; rooms 5/6/8 captured.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
