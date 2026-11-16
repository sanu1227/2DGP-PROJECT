"""게임판 위의 짧은 효과. 좌표와 시간은 표시용이다."""

from contextlib import contextmanager
from ctypes import byref, c_int
from math import cos, hypot, pi, sin

import pico2d.pico2d as p

from game.worker_animation import GESTURES

DUST = (192, 168, 138)
TEAL = (112, 216, 190)
AMBER = (233, 174, 99)
VIOLET = (235, 180, 255)
WORK_SECONDS = {
    "pickup": .24, "drop": .26, "install": .44, "lever": .31,
    "trap": .52, "deliver": .35, "assemble": .56, "deploy": .51,
}


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
        return max((sin(pi * (now - began - .06) / .24)
                    for outlet, began, blocked in self.events.values()
                    if pos == outlet and not blocked and .06 < now - began < .30),
                   default=0)

    def draw(self, board, now, draw_bone, *, top_down):
        self.events = {inlet: event for inlet, event in self.events.items()
                       if now - event[1] < self.seconds}
        size = board.half_width
        for inlet, (outlet, began, blocked) in self.events.items():
            age = max(0, now - began)
            sx, sy = board.screen(inlet)
            tx, ty = board.screen(outlet)
            hatch_y = sy if top_down else sy + size * .42
            if blocked:
                opacity = 210 * (1 - age / self.seconds)
                self.shutter(sx, hatch_y, size, .18 * sin(min(1, age / .16) * pi), opacity)
                ring(sx, sy + size * .13, size * (.22 + min(age, .09)), AMBER, opacity)
                with alpha_blend():
                    for side in (-1, 1):
                        p.draw_line(tx - 6, ty - 6 * side, tx + 6, ty + 6 * side, *AMBER, round(opacity))
            else:
                if age < self.arrival:
                    progress = age / self.arrival
                    self.shutter(sx, hatch_y, size, sin(pi * progress), 190)
                    draw_bone(sx, sy + size * (.13 + .29 * (1 - progress)), 1 - .65 * progress)
                    ring(sx, sy + size * .17, size * (.25 + .14 * progress), TEAL, 190 * (1 - progress))
                else:
                    progress = (age - self.arrival) / (self.seconds - self.arrival)
                    ring(tx, ty + size * .11, size * (.21 + .23 * progress), TEAL, 192 * (1 - progress))

    @staticmethod
    def shutter(x, y, size, opening, opacity):
        width = size * .31
        gap = width * (.09 + opening * .71)
        with alpha_blend():
            for side in (-1, 1):
                left, right = sorted((x + side * gap, x + side * width))
                p.draw_rectangle(left, y - 2, right, y + 2, 91, 79, 66, round(opacity), filled=True)
                p.draw_line(left, y + 2, right, y + 2, 194, 173, 129, round(opacity))


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


def trap_motion(x, y, size, now):
    radius = max(2, size * .085)
    angle = now * 5
    for index in range(3):
        spoke = angle + index * (2 * pi / 3)
        p.draw_line(x, y, x + radius * cos(spoke), y + radius * sin(spoke), 226, 163, 89)


class WorkFeedback:
    def __init__(self):
        self.events = {}

    def changed(self, game, before, now):
        state, level = game.state, game.level
        pos = before.player
        kind = None
        if before.carrying is None and pos in before.items and pos not in state.items and state.carrying:
            kind = "pickup"
        elif before.carrying and state.carrying is None and pos in state.items and pos not in before.items:
            kind = "drop"
        elif pos in state.installed - before.installed:
            kind = "install"
        elif pos in state.soldiers - before.soldiers:
            kind = "deploy"
        elif state.bench_bones != before.bench_bones:
            if state.carrying == "soldier":
                pos = next(iter(before.bench_bones.keys() - state.bench_bones.keys()))
                kind = "assemble"
            else:
                pos = next(iter(state.bench_bones.keys() - before.bench_bones.keys()))
                kind = "deliver"
        elif state.active and not before.active:
            kind = "lever"
            self.events.update(((trap, "trap"), now) for trap in level.traps)
        if kind:
            self.events[pos, kind] = now
            return kind, pos
        return None

    def progress(self, pos, kind, now):
        began = self.events.get((pos, kind))
        if began is None:
            return 1
        return min(1, max(0, (now - began) / WORK_SECONDS[kind]))

    def contacted(self, pos, kind, now):
        if kind == "trap":
            elapsed = now - self.events.get((pos, kind), now - WORK_SECONDS[kind])
            return elapsed >= WORK_SECONDS["lever"] * GESTURES["lever"].contact
        return self.progress(pos, kind, now) >= GESTURES[kind].contact

    def drop_lift(self, pos, now):
        progress = self.progress(pos, "drop", now)
        contact = GESTURES["drop"].contact
        if contact < progress < 1:
            return .22 * sin(pi * (progress - contact) / (1 - contact))
        return 0

    def soldier_height(self, pos, now):
        progress = self.progress(pos, "deploy", now)
        if progress < 1:
            contact = GESTURES["deploy"].contact
            progress = max(0, (progress - contact) / (1 - contact))
            return 1 - .25 * (1 - progress) * cos(progress * 10)
        phase = (now + pos[0] * .4 + pos[1] * .7) % 6
        return 1 + .022 * sin(pi * phase / .52) if phase < .52 else 1

    def draw(self, board, now):
        self.events = {(pos, kind): began for (pos, kind), began in self.events.items()
                       if now - began < WORK_SECONDS[kind]}
        for pos, kind in self.events:
            progress = self.progress(pos, kind, now)
            x, y = board.screen(pos)
            size = board.half_width
            if kind in ("install", "lever", "trap", "deploy", "drop"):
                if kind != "drop" or progress >= .6:
                    dust(x, y + size * .08, progress, size=.85, color=AMBER if kind == "trap" else DUST)
            if kind in ("install", "lever", "trap"):
                cy = y + size * (.30 if kind != "trap" else .44)
                width = max(3, size * .14)
                with alpha_blend():
                    for index in range(3):
                        angle = (progress + index / 3) * 2 * pi
                        p.draw_line(x, cy, x + cos(angle) * width, cy + sin(angle) * width,
                                    *AMBER, round(215 * (1 - progress)))
            elif kind in ("deliver", "assemble"):
                for index in range(4 if kind == "assemble" else 2):
                    angle = index * pi / 2
                    reach = size * .52 * (1 - progress)
                    px, py = x + cos(angle) * reach, y + size * .27 + sin(angle) * reach
                    with alpha_blend():
                        p.draw_line(px - 4, py - 3, px + 4, py + 3, 236, 219, 185, round(220 * (1 - progress)))
            elif kind == "deploy":
                ring(x, y, size * (.26 + progress * .30), TEAL, 175 * (1 - progress))
