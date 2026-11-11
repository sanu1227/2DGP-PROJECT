"""기존 만화 아틀라스를 이용한 네 컷 모션 코믹 렌더링."""

from ctypes import byref
from math import sin, sqrt

import pico2d.pico2d as p

from game.layout import HEIGHT, WIDTH
from game.story import BALLOON_DELAYS, PANEL_SECONDS, STORY
from game.comic_motion import draw_actors
from game.character_motion import EXHALE_START


PANEL_BOUNDS = ((254, 516, 790, 918), (810, 516, 1346, 918),
                (254, 94, 790, 496), (810, 94, 1346, 496))
DIALOGUE_SIZE = 22
INK = (29, 35, 35)
PAPER = (239, 227, 201)
GOLD = (239, 193, 103)


def ease(value):
    return 1 - (1 - min(1.0, max(0.0, value))) ** 3


def dialogue_bounds(index):
    left, _, _, top = PANEL_BOUNDS[index]
    return ((left + 12, top - 100, left + 262, top - 12),
            (left + 274, top - 100, left + 524, top - 12))


def rounded(bounds, radius, color):
    left, bottom, right, top = bounds
    for y in range(round(bottom), round(top) + 1):
        distance = max(bottom + radius - y, y - (top - radius), 0)
        inset = radius - sqrt(max(0, radius * radius - distance * distance))
        p.draw_line(left + inset, y, right - inset, y, *color)


def bubble(view, bounds, words, progress, side):
    left, bottom, right, top = bounds
    offset = round((1 - ease(progress)) * 7)
    bottom, top = bottom + offset, top + offset
    rounded((left + 3, bottom - 3, right + 3, top - 3), 14, INK)
    rounded((left - 2, bottom - 2, right + 2, top + 2), 14, INK)
    rounded((left, bottom, right, top), 12, (255, 251, 231))
    anchor = left + (90 if side == 0 else 150)
    tip = anchor + (14 if side == 0 else -14)
    for row in range(19):
        t = row / 18
        p.draw_line(anchor - 10 + (tip - anchor + 10) * t, bottom - row,
                    anchor + 10 + (tip - anchor - 10) * t, bottom - row, 255, 251, 231)
    p.draw_line(anchor - 10, bottom, tip, bottom - 18, *INK)
    p.draw_line(anchor + 10, bottom, tip, bottom - 18, *INK)
    view.text(left + 12, top - 15, words[0], 13, (107, 80, 48))
    for line, text in enumerate(words[1:]):
        view.centered((left + right) / 2, top - 41 - line * 27, text, DIALOGUE_SIZE, INK)


def draw_picture(load_image, bounds, age, index):
    left, bottom, right, top = bounds
    width, height = right - left, top - bottom
    entrance = ease(age / 0.6)
    image = load_image("motion_backgrounds")
    clip = p.SDL_Rect(left, HEIGHT - top, width, height)
    previous = p.SDL_Rect()
    enabled = p.SDL_RenderIsClipEnabled(p.renderer)
    p.SDL_RenderGetClipRect(p.renderer, byref(previous))
    p.SDL_RenderSetClipRect(p.renderer, byref(clip))
    try:
        image.opacify(0.18 + 0.82 * entrance)
        cw, ch = image.w // 2, image.h // 2
        image.clip_draw((index % 2) * cw + 2, (1 - index // 2) * ch + 2,
                        cw - 4, ch - 4, (left + right) / 2, (bottom + top) / 2,
                        width, height)
        draw_actors(load_image, bounds, age, index, 0.18 + 0.82 * entrance)
    finally:
        image.opacify(1)
        p.SDL_RenderSetClipRect(p.renderer, byref(previous) if enabled else None)


def draw_comic_page(view, playback, load_image):
    p.draw_rectangle(0, 0, WIDTH, HEIGHT, 17, 30, 34, filled=True)
    # 넓은 여백과 굵은 먹선으로 한 장의 만화책처럼 묶는다.
    p.draw_rectangle(241, 82, 1369, 932, 7, 17, 20, filled=True)
    p.draw_rectangle(234, 88, 1362, 934, *PAPER, filled=True)
    view.centered(800, 946, "오늘도 야근", 22, GOLD)
    for index, (page, bounds) in enumerate(zip(STORY, PANEL_BOUNDS)):
        left, bottom, right, top = bounds
        p.draw_rectangle(left - 4, bottom - 4, right + 4, top + 4, *INK, filled=True)
        p.draw_rectangle(*bounds, 248, 239, 220, filled=True)
        age = playback.age(index)
        if age is None:
            continue
        draw_picture(load_image, bounds, age, index)
        if index == playback.index:
            p.draw_rectangle(left - 2, bottom - 2, right + 2, top + 2, *GOLD)
        for side, (bounds, words, delay) in enumerate(zip(dialogue_bounds(index), page.dialogue, BALLOON_DELAYS)):
            if age >= delay:
                bubble(view, bounds, words, (age - delay) / 0.3, side)
        if age >= 0.2:
            effect = "하아..." if index == 2 and age >= EXHALE_START else page.effect
            pop = ease((age - 0.2) / 0.35)
            x = left + (right - left) * 0.58
            y = bottom + 54 + (1 - pop) * 14
            if index == playback.index and age < 1.0:
                x += sin(age * 35) * (1 - pop) * 5
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                view.centered(x + dx, y + dy, effect, 26, INK)
            view.centered(x, y, effect, 26, GOLD)
    # 이야기 설명문 대신 현재 컷과 다음 컷까지의 진행만 표시한다.
    for index in range(4):
        x = 716 + index * 46
        color = GOLD if index <= playback.index else (66, 83, 82)
        p.draw_rectangle(x, 18, x + 30, 23, *color, filled=True)
        if index == playback.index and not playback.finished:
            p.draw_rectangle(x, 18, x + 30 * playback.elapsed / PANEL_SECONDS, 23,
                             126, 224, 201, filled=True)
