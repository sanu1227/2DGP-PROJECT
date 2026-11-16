"""인부의 기록, 재생, 문양 상태를 표시한다."""

import pico2d.pico2d as p

from game.levels import DIRECTIONS
from game.layout import WIDTH


ECHO_COLOR = (197, 137, 243)
GATE_STYLES = {
    "open": ("통과", (123, 223, 192)),
    "held": ("통과 중", (234, 192, 111)),
    "closed": ("닫힘", (178, 188, 192)),
}


def recording_label(level, station):
    seals, steps = level.echo_links[station]
    if len(seals) > 1:
        return f"기록 {steps}걸음"
    return f"{level.device_labels[station]} {steps}걸음"


def draw_direction_arrow(x, y, action, color):
    dx, map_dy = DIRECTIONS[action]
    dy = -map_dy
    sx, sy = -dy, dx
    tip = (x + dx * 8, y + dy * 8)
    for offset in (-1, 0, 1):
        p.draw_line(x - dx * 8 + sx * offset, y - dy * 8 + sy * offset,
                    tip[0] + sx * offset, tip[1] + sy * offset, *color)
    for side in (-1, 1):
        p.draw_line(*tip, x + dx * 2 + sx * side * 6, y + dy * 2 + sy * side * 6, *color)


def draw_worker_status(view, game, context, context_color):
    """하단에서 입력 순서, 재생 위치, 지금 건널 수 있는 문을 함께 보여준다."""
    state, level = game.state, game.level
    recording, echo = state.recording, state.echo
    if game.failed or state.cleared or (recording is None and echo is None):
        return False

    origin = recording.origin if recording else echo.origin
    seals, total = level.echo_links[origin]
    if recording:
        step = len(recording.inputs)
        slots = recording.inputs + (None,) * (total - step)
        title = "발걸음 기록"
    else:
        step = total - len(echo.remaining)
        crossing = state.player in seals and game.gate_status(state.player) == "held"
        title = "인부 재생" if origin in state.replay_workers else "분신 재생"
        if not echo.remaining and not crossing:
            previous = game.history[-1].echo if game.history else None
            if not previous or previous.origin != origin or not previous.remaining:
                return False
            title = "재생 완료"
        slots = (None,) * step + echo.remaining

    p.draw_rectangle(32, 32, WIDTH - 32, 78, 28, 39, 44, filled=True)
    view.text(48, 55, f"{title} {step}/{total}", 18, ECHO_COLOR)
    for index, action in enumerate(slots):
        x = 212 + 42 * index
        current = index == (step if recording else step - 1)
        border = ECHO_COLOR if current else (88, 103, 111)
        p.draw_rectangle(x, 39, x + 34, 71, 42, 47, 57, filled=True)
        p.draw_rectangle(x, 39, x + 34, 71, *border, filled=False)
        if action is not None:
            draw_direction_arrow(x + 17, 55, action, ECHO_COLOR if recording else (210, 215, 222))
        elif not recording:
            view.centered(x + 17, 55, str(index + 1), 16, border)

    if recording:
        view.text(486, 55, "방향키로 이동", 16, (178, 188, 192))
    else:
        gates = []
        for gate in seals:
            status = game.gate_status(gate)
            if status == "held" and state.player != gate:
                status = "closed"
            if status != "closed" or len(seals) <= 2:
                gates.append((level.device_labels[gate], status))
        for index, (label, status) in enumerate(gates):
            x = 486 + 124 * index
            word, color = GATE_STYLES[status]
            p.draw_rectangle(x, 39, x + 112, 71, 42, 47, 57, filled=True)
            p.draw_rectangle(x, 39, x + 112, 71, *color, filled=False)
            view.centered(x + 56, 55, f"{label} {word}", 16, color)
        if context:
            view.wrapped(750, 61, context, width=WIDTH - 798, size=16, color=context_color)
    return True


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
            origin = previous.replay_workers.get(echo.origin, echo.origin)
            start = old.position if old else origin
            if self.motion and echo.origin not in game.state.replay_workers:
                start = self.position_at(now)
            self.motion = (start, echo.position, now)
            inputs = old.remaining if old else ()
            if inputs:
                self.direction = inputs[0]
            elif echo.position != origin:
                dx = echo.position[0] - origin[0]
                dy = echo.position[1] - origin[1]
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
    draw_echo_trail(game, board)


def draw_echo_trail(game, board):
    state = game.state
    if state.recording:
        radius = max(3, round(board.half_width * .34) // 4)
        x, y = state.recording.origin
        for action in state.recording.inputs:
            dx, dy = DIRECTIONS[action]
            a, b = board.screen((x + dx * .45, y + dy * .45))
            p.draw_circle(a, b, radius, *ECHO_COLOR)
            x, y = x + dx, y + dy
