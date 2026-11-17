"""같이 움직이는 장치의 연결을 색, 도형, 점선으로 표시한다."""

from collections import defaultdict
from dataclasses import dataclass
from math import ceil, hypot

import pico2d.pico2d as p

from game.levels import Pos


COLORS = (
    (112, 220, 190), (255, 196, 107), (199, 159, 250),
    (130, 193, 252), (245, 142, 167), (212, 224, 131),
)
MARK_BACKGROUND = (21, 31, 35)


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
    p.draw_circle(x, y, 9, *MARK_BACKGROUND, filled=True)
    p.draw_circle(x, y, 9, *(color if highlighted else (74, 89, 92)))
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


def draw_link_line(start, end, color):
    x, y = start
    dx, dy = end[0] - x, end[1] - y
    segments = max(1, ceil(hypot(dx, dy) / 12))
    for index in range(1, segments):
        sx, sy = x + dx * index / segments, y + dy * index / segments
        p.draw_circle(sx, sy, 3, *MARK_BACKGROUND, filled=True)
        p.draw_circle(sx, sy, 2, *color, filled=True)


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

    columns = max(1, (board.cell_size - 4) // 21)
    positions = {}
    for pos, linked in marks.items():
        sx, sy = board.screen(pos)
        for index, link in enumerate(linked):
            row, column = divmod(index, columns)
            positions[link, pos] = (sx - board.half_width + 13 + 21 * column,
                                    sy + board.half_height - 13 - 21 * row)

    for link in links:
        if link in focused:
            for start, end in zip(link.cells, link.cells[1:]):
                draw_link_line(positions[link, start], positions[link, end], link.color)
            for pos in link.cells:
                if pos != hovered:
                    view.tile_outline(board, *board.screen(pos), board.half_width - 3, board.half_height - 3,
                                      link.color)
    for (link, _), (x, y) in positions.items():
        draw_link_mark(x, y, link, highlighted=link in focused)
