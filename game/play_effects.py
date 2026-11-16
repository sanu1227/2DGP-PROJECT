"""게임판 위의 짧은 효과. 좌표와 시간은 표시용이다."""

from contextlib import contextmanager
from ctypes import byref, c_int
from math import cos, hypot, pi, sin

import pico2d.pico2d as p

DUST = (192, 168, 138)
TEAL = (112, 216, 190)
AMBER = (233, 174, 99)
VIOLET = (235, 180, 255)


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


def ring(x, y, radius, color, opacity):
    with alpha_blend():
        p.draw_circle(x, y, max(2, round(radius)), *color, round(opacity), filled=False)


class ChuteFeedback:
    seconds = .44
    arrival = .16

    def __init__(self):
        self.events = {}

    def transferred(self, game, previous, now):
        inlet = previous.player
        outlet = game.level.chutes.get(inlet)
        if (outlet is not None and previous.carrying == "bone"
                and outlet not in previous.items and game.state.items.get(outlet) == "bone"):
            self.events[inlet] = (outlet, now, False)
            return outlet
        return None

    def blocked(self, game, now):
        state = game.state
        inlet = state.player
        outlet = game.level.chutes.get(inlet)
        if (outlet is not None and state.carrying == "bone" and inlet not in state.items
                and not (game.failed or state.recording or state.cleared)
                and (outlet == inlet or outlet in state.items or outlet in state.soldiers or outlet in state.rubble)):
            self.events[inlet] = (outlet, now, True)

    def item_lift(self, pos, now):
        return max((sin(pi * min(1, max(0, (now - began) / (self.arrival * 2))))
                    for outlet, began, blocked in self.events.values() if pos == outlet and not blocked),
                   default=0)

    def draw(self, board, now, draw_bone):
        self.events = {inlet: event for inlet, event in self.events.items()
                       if now - event[1] < self.seconds}
        size = board.half_width
        for inlet, (outlet, began, blocked) in self.events.items():
            age = max(0, now - began)
            sx, sy = board.screen(inlet)
            tx, ty = board.screen(outlet)
            if blocked:
                opacity = 210 * (1 - age / self.seconds)
                ring(sx, sy + size * .13, size * (.22 + min(age, .09)), AMBER, opacity)
                with alpha_blend():
                    for side in (-1, 1):
                        p.draw_line(tx - 6, ty - 6 * side, tx + 6, ty + 6 * side, *AMBER, round(opacity))
            else:
                if age < self.arrival:
                    progress = age / self.arrival
                    draw_bone(sx, sy + size * (.13 + .29 * (1 - progress)), 1 - .65 * progress)
                    ring(sx, sy + size * .17, size * (.25 + .14 * progress), TEAL, 190 * (1 - progress))
                else:
                    progress = (age - self.arrival) / (self.seconds - self.arrival)
                    ring(tx, ty + size * .11, size * (.21 + .23 * progress), TEAL, 192 * (1 - progress))


def beam_contacts(board, contacts, now, *, height=0):
    if not contacts:
        return
    with alpha_blend():
        for start, end in contacts:
            sx, sy = board.screen(start)
            x, y = board.screen(end)
            length = max(1, hypot(x - sx, y - sy))
            nx, ny = (y - sy) / length, (sx - x) / length
            y += height
            strength = .65 + .35 * sin(now * 18) ** 2
            p.draw_circle(x, y, 4, *VIOLET, round(115 * strength), filled=True)
            p.draw_line(x - nx * 6, y - ny * 6, x + nx * 6, y + ny * 6, *VIOLET, round(205 * strength))
