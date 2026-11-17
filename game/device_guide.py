"""게임판에서 장치를 하나씩 가리키는 안내 말풍선."""

import pico2d.pico2d as p

from game.front_end import bevel
from game.layout import WIDTH, HEIGHT
from game.play_effects import alpha_blend

INK = (247, 241, 220)
GOLD = (255, 204, 110)
PANEL = (24, 37, 40)
CARD_WIDTH, CARD_HEIGHT = 460, 144
CARD_GAP = 34


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


def card_bounds(region):
    left, bottom, right, top = region
    x = max(24, min(WIDTH - CARD_WIDTH - 24, (left + right - CARD_WIDTH) // 2))
    y = top + CARD_GAP
    if y + CARD_HEIGHT > HEIGHT - 94:
        y = bottom - CARD_GAP - CARD_HEIGHT
    return x, y, x + CARD_WIDTH, y + CARD_HEIGHT


def dim_except(region):
    left, bottom, right, top = region
    with alpha_blend():
        for x, y, end_x, end_y in ((0, 0, WIDTH, bottom), (0, top, WIDTH, HEIGHT),
                                   (0, bottom, left, top), (right, bottom, WIDTH, top)):
            p.draw_rectangle(x, y, end_x - 1, end_y - 1, 0, 0, 0, 172, filled=True)


def draw_pointer(card, region):
    left, bottom, right, top = card
    region_left, _, region_right, region_top = region
    x = (region_left + region_right) // 2
    base_x = max(left + 34, min(right - 34, x))
    direction = -1 if bottom > region_top else 1
    base_y = bottom if direction == -1 else top
    tip_y = base_y + direction * (CARD_GAP - 5)
    for row in range(abs(tip_y - base_y) + 1):
        t = row / (CARD_GAP - 5)
        center = round(base_x + (x - base_x) * t)
        half = round(14 * (1 - t))
        y = base_y + direction * row
        p.draw_line(center - half, y, center + half, y, *PANEL)
    p.draw_line(base_x - 14, base_y, x, tip_y, *GOLD)
    p.draw_line(base_x + 14, base_y, x, tip_y, *GOLD)


def draw_lesson(view, lesson, region, card, page, total):
    dim_except(region)
    left, bottom, right, top = region
    for x in range(left + 3, right, 13):
        p.draw_circle(x, bottom, 2, *GOLD, filled=True)
        p.draw_circle(x, top, 2, *GOLD, filled=True)
    for y in range(bottom + 10, top - 3, 13):
        p.draw_circle(left, y, 2, *GOLD, filled=True)
        p.draw_circle(right, y, 2, *GOLD, filled=True)

    left, bottom, right, top = card
    bevel(card, PANEL, GOLD)
    draw_pointer(card, region)
    view.text(left + 20, top - 29, lesson.title, 26, GOLD)
    view.text(left + 20, top - 65, lesson.instruction, 22, INK)
    if total > 1:
        progress = f"{page + 1} / {total}"
        view.text(right - 20 - view.text_width(progress, 16), top - 29, progress, 16, INK)
