"""현재 게임판의 장치만 밝게 남기는 설명 화면. 퍼즐 상태는 바꾸지 않는다."""

import ctypes

import pico2d.pico2d as p

from game.front_end import bevel
from game.layout import WIDTH, HEIGHT
from game.navigation import IsoBoard

INK = (239, 237, 219)
GOLD = (231, 190, 108)
TEAL = (112, 216, 190)
CARD_WIDTH, CARD_HEIGHT = 420, 430


def target_bounds(view, level, targets):
    projection = IsoBoard(level.width, level.height)
    result = {}
    for pos, _ in targets:
        x, y = projection.screen(pos)
        bounds = [(x - projection.half_width, y - projection.half_height,
                   x + projection.half_width, y + projection.half_height)]
        bounds.extend(rect for cell, rect in view.hit_regions if cell == pos)
        result[pos] = (max(12, int(min(b[0] for b in bounds) - 12)),
                       max(12, int(min(b[1] for b in bounds) - 12)),
                       min(WIDTH - 12, int(max(b[2] for b in bounds) + 12)),
                       min(HEIGHT - 90, int(max(b[3] for b in bounds) + 12)))
    return result


def outside_rectangles(holes):
    """겹치는 강조 영역도 보존하도록 바깥 화면을 중복 없는 사각형으로 나눈다."""
    rectangles = [(0, 0, WIDTH, HEIGHT)]
    for left, bottom, right, top in holes:
        remainder = []
        for x1, y1, x2, y2 in rectangles:
            a, b, c, d = max(x1, left), max(y1, bottom), min(x2, right), min(y2, top)
            if a >= c or b >= d:
                remainder.append((x1, y1, x2, y2))
                continue
            remainder.extend(rect for rect in ((x1, y1, x2, b), (x1, d, x2, y2),
                                               (x1, b, a, d), (c, b, x2, d))
                             if rect[0] < rect[2] and rect[1] < rect[3])
        rectangles = remainder
    return rectangles


def dim_except(holes):
    blend, rgba = ctypes.c_int(), [ctypes.c_ubyte() for _ in range(4)]
    p.SDL_GetRenderDrawBlendMode(p.renderer, ctypes.byref(blend))
    p.SDL_GetRenderDrawColor(p.renderer, *(ctypes.byref(v) for v in rgba))
    try:
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, 190)
        for left, bottom, right, top in outside_rectangles(holes):
            rect = p.SDL_Rect(left, HEIGHT - top, right - left, top - bottom)
            p.SDL_RenderFillRect(p.renderer, ctypes.byref(rect))
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, blend.value)
        p.SDL_SetRenderDrawColor(p.renderer, *(v.value for v in rgba))


def card_bounds(holes):
    def overlap(card):
        left, bottom, right, top = card
        return sum(max(0, min(right, r + 24) - max(left, l - 24)) *
                   max(0, min(top, t + 42) - max(bottom, b - 24)) for l, b, r, t in holes)
    candidates = [(x, y, x + CARD_WIDTH, y + CARD_HEIGHT)
                  for x in (32, WIDTH - CARD_WIDTH - 32) for y in (360, 180)]
    return min(candidates, key=overlap)


def draw_lesson(view, game, lesson, bounds, card, page, total):
    dim_except(bounds.values())
    projection = IsoBoard(game.level.width, game.level.height)
    for source, destination in lesson.links:
        x1, y1 = projection.screen(source)
        x2, y2 = projection.screen(destination)
        for i in range(0, 24, 2):
            a, b = i / 24, (i + 1) / 24
            p.draw_line(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a,
                        x1 + (x2 - x1) * b, y1 + (y2 - y1) * b, *TEAL)
    for pos, label in lesson.targets:
        left, bottom, right, top = bounds[pos]
        p.draw_rectangle(left, bottom, right, top, *TEAL)
        if label:
            width = len(label) * 20 + 28
            x = (left + right) / 2
            bevel((round(x - width / 2), top + 4, round(x + width / 2), top + 38), (24, 45, 45), TEAL)
            view.centered(x, top + 21, label, 18, INK)
    left, bottom, right, top = card
    bevel(card, (24, 39, 43), (103, 148, 132))
    view.text(left + 26, top - 30, "새 장치 안내", 18, TEAL)
    view.text(right - 78, top - 30, f"{page + 1} / {total}", 18, GOLD)
    view.text(left + 26, top - 80, lesson.title, 32, GOLD)
    y = view.wrapped(left + 26, top - 130, lesson.instruction, width=CARD_WIDTH - 52, size=18, color=INK)
    view.wrapped(left + 26, y - 47, lesson.reminder, width=CARD_WIDTH - 52, size=16, color=TEAL)
    view.centered(WIDTH / 2, 76, "안내 중에는 행동을 쓰지 않아요. Enter / Space 다음    Esc 건너뛰기", 18, INK)
