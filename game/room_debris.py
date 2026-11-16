"""벽가에 간헐적으로 떨어지는 작은 돌조각을 그린다."""

from ctypes import byref, c_int
from itertools import cycle
from math import cos, sin
from random import Random

import pico2d.pico2d as p

from game.layout import HEIGHT
from game.mechanics import fixed_devices


CHIPS = (
    (0.00, .49, -13, -7, 43, 3.4),
    (0.10, .56,   0,  5, 56, 4.0),
    (0.19, .39,  12,  9, 36, 2.5),
    (0.24, .50,  22,  4, 49, 2.0),
)
LANDING_SECONDS = .34
FALL_SECONDS = max(delay + seconds for delay, seconds, *_ in CHIPS) + LANDING_SECONDS


class RoomDebris:
    def __init__(self, game, now):
        level = game.level
        occupied = (level.walls | fixed_devices(level, game.state) | level.gates.keys()
                    | level.plates | level.rubble | level.initial_items.keys() | set(level.chutes.values()))
        # 뒤쪽 벽이 붙은 빈 바닥에만 돌조각이 닿는다.
        sites = [(x, wall_y + 1) for x, wall_y in sorted(level.walls)
                 if wall_y + 1 < level.height and (x, wall_y + 1) not in occupied]
        self.random = Random(level.id)
        self.random.shuffle(sites)
        self.sites = cycle(sites)
        self.next_drop = now + .55
        self.fall = None

    def draw(self, board, now):
        if now >= self.next_drop:
            site = next(self.sites, None)
            if site is None:
                return
            self.fall = (site, now, self.random.choice((-1, 1)))
            self.next_drop = now + self.random.uniform(1.45, 2.25)
        if self.fall is None:
            return
        (x, y), began, direction = self.fall
        age = now - began
        if age >= FALL_SECONDS:
            self.fall = None
            return

        sx, sy = board.screen((x, y - .19))
        scale = min(1.15, max(.70, board.half_width / 42))
        blend = c_int()
        p.SDL_GetRenderDrawBlendMode(p.renderer, byref(blend))
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        try:
            for delay, seconds, offset, drift, height, size in CHIPS:
                time = age - delay
                if not 0 <= time < seconds + LANDING_SECONDS:
                    continue
                travel = min(1, time / seconds)
                landing = max(0, (time - seconds) / LANDING_SECONDS)
                alpha = (1 - landing) ** 2
                px = sx + scale * direction * (offset + drift * travel)
                py = sy + scale * height * (1 - travel * travel)
                p.draw_line(px - 2 * scale, sy, px + 2 * scale, sy, 30, 26, 26,
                            round(80 * travel * alpha))
                if landing:
                    for side in (-1, 1):
                        dust_x = px + side * scale * (3 + 9 * landing)
                        dust_y = sy + scale * (1 + 4 * landing)
                        p.draw_line(dust_x, dust_y, dust_x + side * scale, dust_y, 183, 156, 127,
                                    round(162 * alpha))
                draw_chip(px, py, size * scale, direction * (offset + 3 * travel), round(230 * alpha))
        finally:
            p.SDL_SetRenderDrawBlendMode(p.renderer, blend.value)


def draw_chip(x, y, size, angle, alpha):
    """모서리가 깨진 돌조각에 윗면과 그늘을 그린다."""
    c, s = cos(angle), sin(angle)
    points = [p.SDL_FPoint(x + size * (u * c - v * s), HEIGHT - 1 - y - size * (u * s + v * c))
              for u, v in ((-1, .24), (.19, .85), (1, -.04), (-.28, -.78))]
    vertices = (p.SDL_Vertex * 6)()
    for index, (corner, color) in enumerate(zip(
            (0, 1, 2, 0, 2, 3), ((214, 195, 168),) * 3 + ((135, 115, 98),) * 3)):
        vertices[index] = p.SDL_Vertex(points[corner], p.SDL_Color(*color, alpha), p.SDL_FPoint())
    p.SDL_RenderGeometry(p.renderer, None, vertices, len(vertices), None, 0)
