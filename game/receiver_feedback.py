"""수신기의 연결 순간과 유지 상태를 표시한다. 퍼즐 상태는 변경하지 않는다."""

from ctypes import byref, c_int
from math import cos, pi, sin

import pico2d.pico2d as p

from game.mechanics import trace_magic

RECEIVE_SECONDS = .7
VIOLET = (190, 115, 255)
LIGHT = (247, 213, 255)


class ReceiverFeedback:
    def __init__(self):
        self.reset()

    def reset(self):
        self.game = None
        self.bursts = {}

    def changed(self, game, previous, now):
        """성공한 행동에서 새 연결만 한 번 재생한다. 유지 중인 연결은 재생하지 않는다."""
        if self.game is not game:
            self.reset()
            self.game = game
        if not game.level.receivers:
            return
        powered = trace_magic(game.level, game.state)[1]
        before = trace_magic(game.level, previous)[1]
        self.bursts = {pos: began for pos, began in self.bursts.items()
                       if pos in powered and now - began < RECEIVE_SECONDS}
        self.bursts.update((pos, now) for pos in powered - before)

    def progress(self, game, pos, now):
        began = self.bursts.get(pos) if self.game is game else None
        if began is None:
            return 1.0
        value = max(0.0, (now - began) / RECEIVE_SECONDS)
        if value >= 1:
            self.bursts.pop(pos)
        return min(1.0, value)

    @staticmethod
    def ring(x, y, scale, radius, color, alpha):
        # 원본 유리 면의 기울기를 따른다. SDL의 가산 합성으로 황동 질감을 보존한다.
        points = []
        for i in range(49):
            angle = i * pi / 24
            dx, dy = cos(angle) * 32 * radius, sin(angle) * 41 * radius
            points.append((x + (dx + dy * .24) * scale, y + dy * scale))
        for start, end in zip(points, points[1:]):
            p.draw_line(*start, *end, *color, alpha)

    def draw(self, game, pos, sx, sy, scale, now):
        """수신 중에만 호출한다. 작은 지속 발광과 0.7초의 단발 파동을 합성한다."""
        x, y = sx + 4 * scale, sy + 81 * scale
        progress = self.progress(game, pos, now)
        blend = c_int()
        p.SDL_GetRenderDrawBlendMode(p.renderer, byref(blend))
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_ADD)
        try:
            # 계속 켜진 보석과 테두리. 반복 점멸이나 화면 전체 섬광은 사용하지 않는다.
            for radius in range(24, 2, -2):
                p.draw_circle(x, y, max(1, round(radius * scale)), *VIOLET, 13, filled=True)
            p.draw_circle(x, y, max(1, round(4 * scale)), *LIGHT, 230, filled=True)
            for radius, alpha in ((.97, 125), (1.0, 170), (1.03, 75)):
                self.ring(x, y, scale, radius, VIOLET, alpha)
            if progress < 1:
                spread = 1 - (1 - progress) ** 3
                alpha = round(180 * (1 - progress) ** 2)
                self.ring(x, y, scale, 1 + .6 * spread, LIGHT, alpha)
                for i in range(4):
                    angle = i * pi / 2 + pi / 4
                    dx, dy = cos(angle) * (38 + 22 * spread), sin(angle) * (47 + 22 * spread)
                    px, py = x + (dx + dy * .24) * scale, y + dy * scale
                    length = (2 + 3 * (1 - progress)) * scale
                    p.draw_line(px - length, py, px + length, py, *LIGHT, alpha)
                    p.draw_line(px, py - length, px, py + length, *LIGHT, alpha)
        finally:
            p.SDL_SetRenderDrawBlendMode(p.renderer, blend.value)
