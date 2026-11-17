"""같이 움직이는 장치의 연결을 색, 도형, 점선으로 표시한다."""

from collections import defaultdict
from dataclasses import dataclass
from math import hypot

import pico2d.pico2d as p

from game.device_outline import OUTLINE_COLOR
from game.levels import Pos
from game.play_effects import alpha_blend


COLORS = (
    (255, 95, 116), (255, 104, 210), (179, 245, 90),
    (165, 120, 255), (255, 158, 70), (107, 153, 255),
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


@dataclass(frozen=True)
class DeviceLighting:
    color: tuple[int, int, int]
    strength: float
    tint: tuple[int, int, int] | None


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


def device_lighting(view, game, links, focused, devices, hovered, now):
    """연결된 장치에는 같은 발광색을 쓰고, 가리킨 장치의 본체에도 색을 준다."""
    hover_strengths = {pos: view.link_glow(game, pos, pos == hovered, now) for pos in devices}
    linked_cells = {pos for link in links for pos in link.cells}
    contributions = defaultdict(list)
    for link in links:
        strength = view.link_glow(game, link, link in focused, now)
        if strength:
            for pos in link.cells:
                contributions[pos].append((link.color, strength))
    for pos, strength in hover_strengths.items():
        if strength and pos not in linked_cells:
            contributions[pos].append((COLORS[0], strength))

    lighting = {}
    for pos, sources in contributions.items():
        # 공유 장치에서 여러 색이 섞여 흐려지는 것을 피한다.
        active_color, strength = max(sources, key=lambda source: source[1])
        color = tuple(round(resting + (channel - resting) * strength)
                      for resting, channel in zip(OUTLINE_COLOR, active_color))
        hover = hover_strengths.get(pos, 0)
        tint = tuple(round(255 + (channel - 255) * .64 * hover) for channel in color) if hover else None
        lighting[pos] = DeviceLighting(color, strength, tint)
    return lighting


def draw_device_links(board, links, focused, hovered):
    if not links:
        return
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
