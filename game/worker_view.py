"""인부의 기록, 재생, 문양 상태를 표시한다."""

from math import hypot, pi, sin

import pico2d.pico2d as p

from game.levels import DIRECTIONS
from game.layout import WIDTH, STATUS_Y
from game.play_effects import ring


ECHO_COLOR = (197, 137, 243)
STEP_COLOR = (233, 199, 255)
SEAL_COLOR = (123, 223, 192)
STRIDE_SECONDS = .18
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

    view.text(58, STATUS_Y, f"{title} {step}/{total}", 18, ECHO_COLOR)
    for index, action in enumerate(slots):
        x = 212 + 42 * index
        current = index == (step if recording else step - 1)
        border = ECHO_COLOR if current else (88, 103, 111)
        p.draw_rectangle(x, STATUS_Y - 16, x + 34, STATUS_Y + 16, 42, 47, 57, filled=True)
        p.draw_rectangle(x, STATUS_Y - 16, x + 34, STATUS_Y + 16, *border, filled=False)
        if action is not None:
            draw_direction_arrow(x + 17, STATUS_Y, action, ECHO_COLOR if recording else (210, 215, 222))
        elif not recording:
            view.centered(x + 17, STATUS_Y, str(index + 1), 16, border)

    if recording:
        view.text(486, STATUS_Y, "방향키로 이동", 16, (178, 188, 192))
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
            p.draw_rectangle(x, STATUS_Y - 16, x + 112, STATUS_Y + 16, 42, 47, 57, filled=True)
            p.draw_rectangle(x, STATUS_Y - 16, x + 112, STATUS_Y + 16, *color, filled=False)
            view.centered(x + 56, STATUS_Y, f"{label} {word}", 16, color)
        if context:
            view.wrapped(750, STATUS_Y, context, width=WIDTH - 798, size=16, color=context_color)
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
            if self.motion and old and echo.origin == old.origin:
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
        fraction = min(1, max(0, (now - began) / STRIDE_SECONDS))
        return tuple(a + (b - a) * fraction for a, b in zip(start, end))

    def stride(self, now):
        if self.motion and self.motion[0] != self.motion[1]:
            fraction = min(1, max(0, (now - self.motion[2]) / STRIDE_SECONDS))
            return 1 + .11 * sin(pi * fraction)
        return 1

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
            if seal in level.plates:
                continue
            x, y = board.screen(seal)
            p.draw_circle(x, y, radius, *ECHO_COLOR, filled=False)
            p.draw_circle(x, y, radius // 2, *ECHO_COLOR, filled=False)
            if game.echo_pressed(gate):
                p.draw_circle(x, y, radius // 3, *ECHO_COLOR)
    draw_echo_trail(game, board)


def draw_echo_trail(game, board):
    state = game.state
    if state.recording:
        pos = state.recording.origin
        inputs = state.recording.inputs
        for index, action in enumerate(inputs):
            dx, dy = DIRECTIONS[action]
            target = pos[0] + dx, pos[1] + dy
            color = STEP_COLOR if index == len(inputs) - 1 else ECHO_COLOR
            draw_step_arrow(board, pos, target, color)
            pos = target


def draw_step_arrow(board, source, target, color, *, tip_at=.62):
    sx, sy = board.screen(source)
    tx, ty = board.screen(target)
    length = max(1, hypot(tx - sx, ty - sy))
    dx, dy = (tx - sx) / length, (ty - sy) / length
    x, y = sx + (tx - sx) * tip_at, sy + (ty - sy) * tip_at
    size = max(4, min(9, board.half_width * .16))
    for side in (-1, 1):
        p.draw_line(x, y, x - (dx + side * dy) * size, y - (dy - side * dx) * size, *color)


def draw_echo_turn(game, board, motion, now):
    echo = game.state.echo
    if echo is None:
        return
    seals, _ = game.level.echo_links[echo.origin]
    for gate, seal in seals.items():
        if game.echo_pressed(gate):
            if seal not in game.level.plates:
                x, y = board.screen(seal)
                ring(x, y, board.half_width * .43, SEAL_COLOR, 230)
            x, y = board.screen(gate)
            extent = board.half_width * .37
            for side in (-1, 1):
                edge = x + side * extent
                p.draw_line(edge, y - 5, edge, y + 5, *SEAL_COLOR)
                p.draw_line(edge, y + 5, edge - side * 4, y + 5, *SEAL_COLOR)
    if echo.just_stepped and motion.game is game and motion.motion:
        dx, dy = DIRECTIONS[motion.direction]
        x, y = echo.position
        draw_step_arrow(board, (x - dx, y - dy), echo.position, STEP_COLOR, tip_at=.8)
