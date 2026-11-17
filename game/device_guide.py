"""게임판에서 장치를 하나씩 가리키는 안내 말풍선."""

from ctypes import c_int
from functools import lru_cache
from math import cos, pi, sin

import pico2d.pico2d as p

from game.comic import rounded
from game.layout import WIDTH, HEIGHT
from game.play_effects import alpha_blend

INK = (240, 237, 227)
MUTED = (165, 176, 171)
AMBER = (233, 187, 114)
POINTER_LIGHT = (255, 218, 154)
POINTER_EDGE = (24, 21, 17)
PANEL = (24, 32, 33)
SHADE = (5, 9, 13)
SHADE_ALPHA = 166
FEATHER = 50
CARD_HEIGHT, CARD_GAP = 128, 34
INSTRUCTION_SPACING = 27


def target_region(view, level, pos):
    projection = view.projection(level)
    x, y = projection.screen(pos)
    bounds = [(x - projection.half_width, y - projection.half_height,
               x + projection.half_width, y + projection.half_height)]
    bounds.extend(rect for cell, rect in view.hit_regions if cell == pos)
    return (max(12, int(min(b[0] for b in bounds) - 8)),
            max(12, int(min(b[1] for b in bounds) - 8)),
            min(WIDTH - 12, int(max(b[2] for b in bounds) + 8)),
            min(HEIGHT - 90, int(max(b[3] for b in bounds) + 8)))


def card_bounds(view, region, instruction_lines):
    left, bottom, right, top = region
    width = max(352, max(view.text_width(line, 22) for line in instruction_lines) + 44)
    height = CARD_HEIGHT + INSTRUCTION_SPACING * (len(instruction_lines) - 1)
    x = max(24, min(WIDTH - width - 24, (left + right - width) // 2))
    y = top + CARD_GAP
    if y + height > HEIGHT - 94:
        y = bottom - CARD_GAP - height
    return x, y, x + width, y + height


@lru_cache(maxsize=48)
def spotlight_mesh(region):
    """대상 주변의 투명도만 보간하며, 바깥 사각형과 같은 농도로 끝난다."""
    left, bottom, right, top = region
    vertices, indices = [], []
    steps = 6
    ring_size = 4 * (steps + 1)
    for ring, (spread, radius, opacity) in enumerate(((0, 15, 0), (15, 28, 32),
                                                     (34, 32, 124), (FEATHER, 0, SHADE_ALPHA))):
        x1, y1, x2, y2 = left - spread, bottom - spread, right + spread, top + spread
        corners = ((x2 - radius, y2 - radius), (x1 + radius, y2 - radius),
                   (x1 + radius, y1 + radius), (x2 - radius, y1 + radius))
        tint = p.SDL_Color(*SHADE, opacity)
        for corner, (x, y) in enumerate(corners):
            for index in range(steps + 1):
                angle = (corner + index / steps) * pi / 2
                point = p.SDL_FPoint(x + cos(angle) * radius, HEIGHT - y - sin(angle) * radius)
                vertices.append(p.SDL_Vertex(point, tint, p.SDL_FPoint()))
        if ring:
            for index in range(ring_size):
                current = ring * ring_size + index
                following = ring * ring_size + (index + 1) % ring_size
                indices.extend((current - ring_size, current, following,
                                current - ring_size, following, following - ring_size))
    return (p.SDL_Vertex * len(vertices))(*vertices), (c_int * len(indices))(*indices)


def dim_except(region):
    left, bottom, right, top = region
    left, bottom = max(0, left - FEATHER), max(0, bottom - FEATHER)
    right, top = min(WIDTH, right + FEATHER), min(HEIGHT, top + FEATHER)
    vertices, indices = spotlight_mesh(region)
    with alpha_blend():
        for x, y, end_x, end_y in ((0, 0, WIDTH, bottom), (0, top, WIDTH, HEIGHT),
                                  (0, bottom, left, top), (right, bottom, WIDTH, top)):
            if x < end_x and y < end_y:
                p.draw_rectangle(x, y, end_x - 1, end_y - 1, *SHADE, SHADE_ALPHA, filled=True)
        p.SDL_RenderGeometry(p.renderer, None, vertices, len(vertices), indices, len(indices))


def draw_pointer(card, region):
    left, bottom, right, top = card
    region_left, region_bottom, region_right, region_top = region
    x = (region_left + region_right) // 2
    anchor = max(left + 22, min(right - 22, x))
    above = bottom > region_top
    start = bottom if above else top
    tip = region_top - 12 if above else region_bottom + 12
    with alpha_blend():
        p.draw_circle(x, tip, 11, *POINTER_LIGHT, 43, filled=True)
    for offset in range(-2, 3):
        color = POINTER_EDGE if abs(offset) == 2 else POINTER_LIGHT
        p.draw_line(anchor + offset, start, x + offset, tip, *color)
    p.draw_circle(x, tip, 6, *POINTER_EDGE, filled=True)
    p.draw_circle(x, tip, 4, *POINTER_LIGHT, filled=True)


def draw_lesson(view, title, instruction_lines, region, card, page, total):
    dim_except(region)
    left, bottom, right, top = card
    draw_pointer(card, region)
    with alpha_blend():
        rounded((left - 5, bottom - 8, right + 5, top + 2), 21, (0, 0, 0, 48))
        rounded((left - 2, bottom - 5, right + 2, top), 19, (0, 0, 0, 87))
    rounded(card, 17, (66, 76, 73))
    rounded((left + 1, bottom + 1, right - 1, top - 1), 16, PANEL)
    p.draw_circle(left + 24, top - 26, 2, *AMBER, filled=True)
    view.text(left + 37, top - 26, title, 22, AMBER)
    for index, line in enumerate(instruction_lines):
        view.text(left + 22, top - 58 - index * INSTRUCTION_SPACING, line, 22, INK)
    p.draw_line(left + 18, bottom + 44, right - 18, bottom + 44, 54, 64, 62)
    if total > 1:
        for index in range(total):
            x = right - 22 - 11 * (total - index - 1)
            color = AMBER if index == page else (92, 105, 101)
            p.draw_rectangle(x - 5, top - 27, x, top - 26, *color, filled=True)


def draw_guide_buttons(view, buttons, selected):
    for index, button in enumerate(buttons):
        left, bottom, right, top = button.bounds
        y = (bottom + top) / 2
        if index == selected:
            rounded(button.bounds, 10, (49, 62, 58))
        if button.action == "guide_next":
            view.text(left + 12, y, button.label, 18, INK)
            p.draw_line(right - 18, y + 4, right - 13, y, *AMBER)
            p.draw_line(right - 13, y, right - 18, y - 4, *AMBER)
        else:
            rounded((left + 8, bottom + 6, left + 39, top - 6), 5, (42, 51, 50))
            view.centered(left + 23.5, y, "Esc", 13, MUTED)
            view.text(left + 46, y, button.label, 16, MUTED)
