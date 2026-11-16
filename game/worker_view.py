"""호출대와 인부 통로 표시. 보간은 게임 행동 수나 문 판정과 별개다."""

from math import floor, hypot

import pico2d.pico2d as p


class WorkerMotion:
    def __init__(self):
        self.game = None
        self.motions = {}

    @staticmethod
    def step(route, state, station):
        return state.worker_steps.get(station, len(route)) if station in state.workers else 0

    def change(self, game, previous, now):
        if game is not self.game:
            self.game, self.motions = game, {}
        for station, route in game.level.worker_routes.items():
            start = self.step(route, previous, station)
            end = self.step(route, game.state, station)
            if end == 0:
                self.motions.pop(station, None)
            elif start != end:
                motion = self.motions.get(station)
                start = self.progress(motion, now) if motion else start
                self.motions[station] = (start, end, now, .18 * (end - start))

    @staticmethod
    def progress(motion, now):
        start, end, began, duration = motion
        fraction = min(1, max(0, (now - began) / duration))
        return start + (end - start) * fraction

    def pose(self, game, station, now):
        """보이는 현재 위치와 작업 자세 전환 여부를 반환한다."""
        route = game.level.worker_routes[station]
        step = self.step(route, game.state, station)
        if not step:
            return None, False
        motion = self.motions.get(station) if game is self.game else None
        step = self.progress(motion, now) if motion else step
        if step >= len(route):
            return route[-1], True
        path = (station, *route)
        index = floor(step)
        fraction = step - index
        start, end = path[index:index + 2]
        return tuple(a + (b - a) * fraction for a, b in zip(start, end)), False


def draw_routes(level, board):
    color = (195, 158, 92)
    for station, route in level.worker_routes.items():
        nodes = [board.screen(pos) for pos in (station, *route)]
        for (x1, y1), (x2, y2) in zip(nodes, nodes[1:]):
            dx, dy = x2 - x1, y2 - y1
            length = hypot(dx, dy)
            nx, ny = -dy / length, dx / length
            for start, end in ((.17, .33), (.42, .58), (.67, .83)):
                for side in (-2, 2):
                    p.draw_line(x1 + dx * start + nx * side, y1 + dy * start + ny * side,
                                x1 + dx * end + nx * side, y1 + dy * end + ny * side, *color)
        x, y = nodes[0]
        radius = max(8, round(board.half_width * .32))
        p.draw_circle(x, y, radius, *color, filled=False)
        p.draw_circle(x, y, round(radius * .54), *color, filled=False)
        for x, y in nodes[1:-1]:
            p.draw_circle(x, y, max(3, round(radius * .3)), *color, filled=False)
