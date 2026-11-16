"""광원 네 방향의 실제 발사구 픽셀·광선 시작점·클릭을 SDL로 검사한다."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'

import ctypes
import argparse
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import pico2d.pico2d as p
from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard
from game.optics import MAGIC_BEAM_HEIGHT, source_origin, trace_display_magic
from game.view import View, WIDTH, HEIGHT
from tests.smoke_gate_animation import save_frame
from tests.smoke_placement import visible_item_pixel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    args = parser.parse_args()
    base = replace(load_levels()[4], id='source_directions', title='광원 방향 확인', start=(1, 6), exit=(6, 6),
                   action_limit=None, walls=frozenset(), traps=frozenset(), posts=frozenset(), levers=frozenset(),
                   benches=frozenset(), gates={}, chutes={}, mirrors=frozenset(), initial_items={}, receivers=frozenset())
    projection = IsoBoard(8, 8)
    scale = projection.half_width / 112
    p.open_canvas(WIDTH, HEIGHT)
    view = None
    try:
        view = View()
        for direction in ('right', 'down', 'left', 'up'):
            game = Game(replace(base, sources={(3, 3): direction}))
            sprite, flip = view.art.source_pose(direction)
            p.clear_canvas()
            sx, sy = projection.screen((3, 3))
            view.art.draw(sprite, sx, sy, scale, flip=flip)
            x, y = projection.screen(source_origin((3, 3), direction))
            y += MAGIC_BEAM_HEIGHT * scale
            rect = p.SDL_Rect(round(x) - 3, HEIGHT - 1 - round(y) - 3, 7, 7)
            pixels = (ctypes.c_ubyte * (7 * 7 * 4))()
            assert p.SDL_RenderReadPixels(p.renderer, ctypes.byref(rect), p.SDL_PIXELFORMAT_RGBA32, pixels, 7 * 4) == 0
            colors = [tuple(pixels[i:i + 4]) for i in range(0, len(pixels), 4)]
            assert any(b > 175 and g > 150 and b > r * 1.35 for r, g, b, _ in colors), (direction, '발사구에서 광선이 벗어났습니다.')
            rays, _ = trace_display_magic(game.level, game.state, {})
            assert rays[0][0] == source_origin((3, 3), direction)
            with patch('game.view.perf_counter', return_value=1000):
                view.draw(game, 0, 1)
            visible_item_pixel(view, game, (3, 3), sprite)
            if args.capture_dir:
                save_frame(args.capture_dir / f'source-{direction}.png')
        print('Light source SDL OK: four upright directions, actual cyan muzzle pixels within 3px of beam origin, alpha clicks.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
