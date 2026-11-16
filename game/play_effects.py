"""게임판 위의 짧은 효과. 좌표와 시간은 표시용이다."""

from contextlib import contextmanager
from ctypes import byref, c_int
from math import cos, hypot, pi, sin

import pico2d.pico2d as p

DUST = (192, 168, 138)


@contextmanager
def alpha_blend():
    previous = c_int()
    p.SDL_GetRenderDrawBlendMode(p.renderer, byref(previous))
    p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
    try:
        yield
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, previous.value)


def dust(x, y, progress, *, direction=(0, 0), size=1, color=DUST):
    """바닥 가까이에서 흩어지는 가루. 진행률 1에서 사라진다."""
    dx, dy = direction
    opacity = round(150 * (1 - progress) ** 2)
    with alpha_blend():
        for i in range(6):
            angle = i * 2.4
            spread = (3 + progress * 14) * size
            px = x + (cos(angle) + dx * .8) * spread
            py = y + (sin(angle) * .36 + dy * .55) * spread + progress * 5 * size
            p.draw_circle(px, py, max(1, round((1 + i % 2) * size)), *color, opacity, filled=True)


def rubble_scrape(board, start, target, position, progress):
    x, y = board.screen(position)
    sx, sy = board.screen(start)
    tx, ty = board.screen(target)
    length = max(1, hypot(tx - sx, ty - sy))
    dx, dy = (tx - sx) / length, (ty - sy) / length
    radius = board.half_width * .38
    dust(x - dx * radius, y - dy * radius * .55, progress,
         direction=(-dx, -dy), size=max(.7, min(1.4, board.half_width / 45)))
