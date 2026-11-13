"""실제 잔해 밀기 후 발판의 그리기 순서·접점·클릭·되돌리기를 검사한다."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'
import argparse
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import pico2d.pico2d as p
from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard
from game.view import View, WIDTH, HEIGHT, PLATE_SECONDS
from tests.solutions import SOLUTIONS
from tests.smoke_gate_animation import save_frame
from tests.smoke_placement import visible_item_pixel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    levels = load_levels()
    index = next(i for i, level in enumerate(levels) if level.rubble and level.plates)
    game = Game(levels[index])
    for action in SOLUTIONS[game.level.id]:
        before = deepcopy(game.state)
        assert game.act(action), game.message
        if game.state.rubble & game.level.plates:
            break
    else:
        raise AssertionError('기준 풀이에서 발판 위 잔해를 찾지 못했습니다.')
    loaded = deepcopy(game.state)
    plate = next(iter(game.state.rubble & game.level.plates))
    projection = IsoBoard(game.level.width, game.level.height)
    sx, sy = projection.screen(plate)
    scale = projection.half_width * 2 / 224
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        view = View()
        original_draw, original_plate = view.art.draw, view.art.draw_plate
        events = []

        def draw(name, x, y, sprite_scale, **kwargs):
            if name == 'push_rubble':
                events.append(('rubble', x, y, sprite_scale))
            return original_draw(name, x, y, sprite_scale, **kwargs)

        def draw_plate(x, y, sprite_scale, fraction):
            events.append(('plate', x, y, sprite_scale))
            return original_plate(x, y, sprite_scale, fraction)

        def frame(now):
            events.clear()
            with patch('game.view.perf_counter', return_value=now), \
                    patch.object(view.art, 'draw', draw), patch.object(view.art, 'draw_plate', draw_plate):
                view.draw(game, index, len(levels))

        game.state = before
        frame(0)
        game.state = loaded
        frame(1)
        for fraction in (0, .5, 1):
            frame(1 + PLATE_SECONDS * fraction + 1e-7)
            if args.capture:
                save_frame(args.capture / f'pressed-{fraction:g}.png')
            names = [event[0] for event in events]
            assert names.index('plate') < names.index('rubble'), '상판이 잔해를 덮습니다.'
            _, x, y, sprite_scale = next(e for e in events if e[0] == 'rubble')
            assert x == sx and sprite_scale == scale
            assert abs(y - sy - view.support_height(game, plate) * scale) < 1e-8
            visible_item_pixel(view, game, plate, 'push_rubble')
            assert game.state == loaded
        assert game.undo() and game.state == before
        frame(2)
        frame(3)
        assert not game.state.rubble & game.level.plates
        assert view.plate_depths[plate] == 0
        print('Rubble/plate smoke OK: actual push, foreground order, 3 press heights, alpha picking and undo.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
