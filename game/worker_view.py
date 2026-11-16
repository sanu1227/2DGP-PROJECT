"""분신 기록석, 문양, 발걸음 표시와 재생 보간."""

import pico2d.pico2d as p

from game.levels import DIRECTIONS


ECHO_COLOR = (197, 137, 243)


def recording_label(level, station):
    seals, steps = level.echo_links[station]
    if len(seals) > 1:
        return f"기록 {steps}걸음"
    return f"{level.device_labels[station]} {steps}걸음"


class EchoMotion:
    def __init__(self):
        self.game = None
        self.motion = None
        self.direction = "down"

    def change(self, game, previous, now):
        if game is not self.game:
            self.game, self.motion = game, None
        echo = game.state.echo
        old = previous.echo
        if not echo:
            self.motion = None
            return
        if old != echo:
            start = old.position if old else echo.origin
            if self.motion:
                start = self.position_at(now)
            self.motion = (start, echo.position, now)
            inputs = old.remaining if old else ()
            if inputs:
                self.direction = inputs[0]
            elif echo.position != echo.origin:
                dx = echo.position[0] - echo.origin[0]
                dy = echo.position[1] - echo.origin[1]
                self.direction = next(key for key, value in DIRECTIONS.items() if value == (dx, dy))

    def position_at(self, now):
        start, end, began = self.motion
        fraction = min(1, max(0, (now - began) / .18))
        return tuple(a + (b - a) * fraction for a, b in zip(start, end))

    def pose(self, game, now):
        echo = game.state.echo
        if not echo:
            return None
        position = self.position_at(now) if game is self.game and self.motion else echo.position
        return position, self.direction


def draw_echo_marks(game, board):
    level, state = game.level, game.state
    radius = max(8, round(board.half_width * .34))
    for origin, (seals, _) in level.echo_links.items():
        x, y = board.screen(origin)
        points = ((x-radius, y), (x, y+radius), (x+radius, y), (x, y-radius))
        for a, b in zip(points, points[1:] + points[:1]):
            p.draw_line(*a, *b, *ECHO_COLOR)
        p.draw_circle(x, y, radius // 3, *ECHO_COLOR, filled=False)
        for gate, seal in seals.items():
            x, y = board.screen(seal)
            p.draw_circle(x, y, radius, *ECHO_COLOR, filled=False)
            p.draw_circle(x, y, radius // 2, *ECHO_COLOR, filled=False)
            if game.echo_pressed(gate):
                p.draw_circle(x, y, radius // 3, *ECHO_COLOR)
    if state.recording:
        x, y = state.recording.origin
        for action in state.recording.inputs:
            dx, dy = DIRECTIONS[action]
            a, b = board.screen((x + dx * .45, y + dy * .45))
            p.draw_circle(a, b, max(3, radius // 4), *ECHO_COLOR)
            x, y = x + dx, y + dy
