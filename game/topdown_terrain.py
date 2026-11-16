"""퍼즐 격자 위에 방별 벽 단차와 국소 조명을 그린다."""

from ctypes import byref, c_int
from dataclasses import dataclass
from math import cos, pi, sin

import pico2d.pico2d as p

from game.layout import HEIGHT


_RING = tuple((cos(index * pi / 8), sin(index * pi / 8)) for index in range(16))


@dataclass(frozen=True)
class Materials:
    floors: tuple[str, ...]
    cap: str
    face: str
    corner: str
    rocks: tuple[str, str]


WORKSHOP = Materials(
    ("workshop_floor_ashlar", "workshop_floor_slate", "workshop_floor_ashlar",
     "workshop_floor_slate", "workshop_floor_scorched"),
    "workshop_cap", "workshop_face", "workshop_corner", ("workshop_rock", "workshop_rock_chipped"),
)


def materials_for(stage):
    if stage == 1:
        return WORKSHOP
    prefix = f"room_{stage:02d}"
    plain, alt = f"{prefix}_floor", f"{prefix}_floor_alt"
    floors = (plain, alt, plain, alt, f"{prefix}_floor_inlay") if stage == 8 else (plain, plain, alt, plain, plain)
    rock = f"{prefix}_rock"
    return Materials(floors, f"{prefix}_cap", f"{prefix}_face",
                     f"{prefix}_corner", (rock, f"{prefix}_rock_alt" if stage == 8 else rock))


def radial_layer(x, y, width, height, color, alpha):
    """중심에서 가장자리로 옅어지는 타원형 빛과 그림자를 같은 방식으로 그린다."""
    vertices = [p.SDL_Vertex(p.SDL_FPoint(x, HEIGHT - y), p.SDL_Color(*color, alpha), p.SDL_FPoint())]
    indices = []
    count = len(_RING)
    for ring, (radius, strength) in enumerate(((.35, .74), (.68, .30), (1, 0))):
        start = 1 + ring * count
        tint = p.SDL_Color(*color, round(alpha * strength))
        for index, (dx, dy) in enumerate(_RING):
            vertices.append(p.SDL_Vertex(p.SDL_FPoint(x + width * radius * dx, HEIGHT - y + height * radius * dy),
                                         tint, p.SDL_FPoint()))
            current = start + index
            following = start + (index + 1) % count
            if ring == 0:
                indices.extend((0, current, following))
            else:
                indices.extend((current - count, current, following, current - count, following, following - count))
    mesh = (p.SDL_Vertex * len(vertices))(*vertices)
    triangles = (c_int * len(indices))(*indices)
    p.SDL_RenderGeometry(p.renderer, None, mesh, len(vertices), triangles, len(indices))


def panel(art, name, left, bottom, width, height, *, vertical=False):
    x, y = left + width / 2, bottom + height / 2
    if vertical:
        art.draw(name, x, y, height, height_scale=width / height, angle=pi / 2)
    else:
        art.draw(name, x, y, width, height_scale=height / width)


def wall_rim(art, board, pos, floors, materials):
    """바닥과 만나는 면은 밝은 윗돌과 어두운 벽면으로 표시한다."""
    x, y = pos
    size = board.cell_size
    sx, sy = board.screen(pos)
    left, bottom = sx - size / 2, sy - size / 2
    rim = round(size * .19)
    face = round(size * (.40 if y == 0 else .31))
    north, west, east, south = ((x, y - 1) in floors, (x - 1, y) in floors,
                                 (x + 1, y) in floors, (x, y + 1) in floors)
    if west:
        panel(art, materials.cap, left, bottom, rim, size, vertical=True)
    if east:
        panel(art, materials.cap, left + size - rim, bottom, rim, size, vertical=True)
    if north:
        panel(art, materials.face, left, bottom + size - rim - face * .5, size, face * .5)
        panel(art, materials.cap, left, bottom + size - rim, size, rim)
        p.draw_line(left, bottom + size - 1, left + size - 1, bottom + size - 1, 127, 116, 105, 125)
    if south:
        panel(art, materials.face, left, bottom, size, face)
        panel(art, materials.cap, left, bottom + face, size, rim)
        p.draw_line(left, bottom + face, left + size - 1, bottom + face, 201, 178, 143, 110)
    for direction, side in ((-1, west), (1, east)):
        if side:
            continue
        corner = left if direction < 0 else left + size - rim
        if not south and (x + direction, y + 1) in floors:
            panel(art, materials.face, corner, bottom, rim, face)
            panel(art, materials.corner, corner, bottom + face, rim, rim)
        if not north and (x + direction, y - 1) in floors:
            panel(art, materials.corner, corner, bottom + size - rim, rim, rim)


def floor_shadows(center, size, north, west, east):
    if not (north or west or east):
        return
    sx, sy = center
    left, right, top, bottom = sx - size / 2, sx + size / 2, sy + size / 2, sy - size / 2
    depth = round(size * .16)
    for offset in range(depth):
        alpha = round(106 * (1 - offset / depth) ** 2)
        if north:
            p.draw_line(left, top - 1 - offset, right - 1, top - 1 - offset, 12, 9, 13, alpha)
        if west:
            p.draw_line(left + offset, bottom, left + offset, top - 1, 12, 9, 13, alpha // 2)
        if east:
            p.draw_line(right - 1 - offset, bottom, right - 1 - offset, top - 1, 12, 9, 13, alpha // 3)


def draw_terrain(art, board, level, materials, lights):
    size = board.cell_size
    floors = {(x, y) for y in range(level.height) for x in range(level.width) if (x, y) not in level.walls}

    previous = c_int()
    p.SDL_GetRenderDrawBlendMode(p.renderer, byref(previous))
    p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
    try:
        for y in range(level.height):
            for x in range(level.width):
                pos = x, y
                center = board.screen(pos)
                if pos in floors:
                    floor = materials.floors[(x * 7 + y * 3) % len(materials.floors)]
                    art.draw(floor, *center, size)
                    floor_shadows(center, size, (x, y - 1) not in floors, (x - 1, y) not in floors,
                                  (x + 1, y) not in floors)
                    sx, sy = center
                    p.draw_rectangle(sx - size / 2, sy - size / 2, sx + size / 2 - 1, sy + size / 2 - 1,
                                     31, 24, 26, 68)
                else:
                    distance = min((abs(x - fx) + abs(y - fy) for fx, fy in floors), default=3)
                    rock = materials.rocks[int((x + y * 2) % 3 == 0)]
                    art.draw(rock, *center, size, angle=((x * 3 + y) % 4) * pi / 2,
                             opacity=max(.14, .77 - .28 * (distance - 1)))
                    wall_rim(art, board, pos, floors, materials)
        for position, width, height, color, alpha in lights:
            radial_layer(*board.screen(position), size * width, size * height, color, alpha)
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, previous.value)


def draw_shadows(board, player, objects):
    size = board.cell_size
    previous = c_int()
    p.SDL_GetRenderDrawBlendMode(p.renderer, byref(previous))
    p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
    try:
        for pos in objects:
            sx, sy = board.screen(pos)
            radial_layer(sx + size * .05, sy - size * .13, size * .36, size * .22, (12, 9, 11), 134)
        sx, sy = board.screen(player)
        radial_layer(sx + size * .04, sy - size * .24, size * .28, size * .14, (12, 9, 11), 191)
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, previous.value)
