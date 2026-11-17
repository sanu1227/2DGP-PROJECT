"""같이 움직이는 장치의 연결을 색, 도형, 점선으로 표시한다."""

from collections import defaultdict
from dataclasses import dataclass
from math import hypot

import pico2d.pico2d as p

from game.levels import Pos
from game.play_effects import alpha_blend


COLORS = (
    (112, 220, 190), (255, 196, 107), (199, 159, 250),
    (130, 193, 252), (245, 142, 167), (212, 224, 131),
)
PIN_FACE = (48, 40, 35)
PIN_RIM = (127, 104, 75)
PIN_LIGHT = (184, 151, 103)
PIN_SHADOW = (27, 23, 23)


@dataclass(frozen=True)
class DeviceLink:
    cells: tuple[Pos, ...]
    index: int

    @property
    def color(self):
        return COLORS[self.index % len(COLORS)]

    @property
    def shape(self):
        return (self.index + self.index // len(COLORS)) % 4


def device_links(level):
    """연결 장치의 좌표를 원인부터 결과까지 순서대로 모은다."""
    echoes = {gate: (station, seal, gate) for station, (seals, _) in level.echo_links.items()
              for gate, seal in seals.items()}
    routes = [echoes.get(gate, (control, gate)) for gate, control in level.gates.items()]
    routes.extend(level.chutes.items())
    return tuple(DeviceLink(route, index) for index, route in enumerate(sorted(routes)))


def draw_link_mark(x, y, link, highlighted=False):
    color = link.color
    p.draw_circle(x + 1, y - 1, 10, *PIN_SHADOW, filled=True)
    p.draw_circle(x, y, 10, *PIN_FACE, filled=True)
    p.draw_circle(x, y, 10, *(color if highlighted else PIN_RIM))
    p.draw_line(x - 4, y + 8, x + 3, y + 8, *PIN_LIGHT)
    if link.shape == 0:
        p.draw_circle(x, y, 5, *color, filled=True)
    elif link.shape == 1:
        for dy in range(-6, 7):
            span = 6 - abs(dy)
            p.draw_line(x - span, y + dy, x + span, y + dy, *color)
    elif link.shape == 2:
        for row in range(11):
            span = round(row * .58)
            p.draw_line(x - span, y + 5 - row, x + span, y + 5 - row, *color)
    else:
        p.draw_rectangle(x - 4, y - 4, x + 4, y + 4, *color, filled=True)
    shine = tuple((channel + 255) // 2 for channel in color)
    p.draw_line(x - 1, y + 2, x + 1, y + 2, *shine)


def draw_link_line(start, end, color):
    x, y = start
    dx, dy = end[0] - x, end[1] - y
    length = hypot(dx, dy)
    if length <= 24:
        return
    bend = min(24, length * .10)
    nx, ny = -dy / length, dx / length

    def point(distance):
        t = distance / length
        offset = 4 * t * (1 - t) * bend
        return x + dx * t + nx * offset, y + dy * t + ny * offset

    for distance in range(13, int(length) - 12, 13):
        x0, y0 = point(distance)
        x1, y1 = point(min(distance + 6, length - 12))
        for side in (-1, 1):
            ox, oy = nx * side, ny * side
            p.draw_line(x0 + ox, y0 + oy, x1 + ox, y1 + oy, *PIN_SHADOW, 160)
        p.draw_line(x0, y0, x1, y1, *color, 230)


def draw_link_corners(board, pos, color):
    sx, sy = board.screen(pos)
    extent = board.half_width - 4
    length = min(12, extent * .40)
    for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        x, y = sx + dx * extent, sy + dy * extent
        p.draw_line(x, y, x - dx * length, y, *color, 220)
        p.draw_line(x, y, x, y - dy * length, *color, 220)


def draw_device_links(view, game, board):
    links = device_links(game.level)
    if not links:
        return
    hovered = view.pick_cell(game, *view.mouse_position) if view.mouse_position else None
    focused = {link for link in links if hovered in link.cells}
    marks = defaultdict(list)
    for link in links:
        for pos in link.cells:
            marks[pos].append(link)

    columns = max(1, (board.cell_size - 4) // 24)
    positions = {}
    for pos, linked in marks.items():
        sx, sy = board.screen(pos)
        for index, link in enumerate(linked):
            row, column = divmod(index, columns)
            positions[link, pos] = (sx - board.half_width + 15 + 24 * column,
                                    sy + board.half_height - 15 - 24 * row)

    if focused:
        with alpha_blend():
            for link in links:
                if link not in focused:
                    continue
                for start, end in zip(link.cells, link.cells[1:]):
                    draw_link_line(positions[link, start], positions[link, end], link.color)
                for pos in link.cells:
                    if pos != hovered:
                        draw_link_corners(board, pos, link.color)
    for (link, _), (x, y) in positions.items():
        draw_link_mark(x, y, link, highlighted=link in focused)
