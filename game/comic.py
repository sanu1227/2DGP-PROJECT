"""기존 만화 아틀라스를 이용한 네 컷 모션 코믹 렌더링."""

from ctypes import byref
from math import sin, sqrt

import pico2d.pico2d as p

from game.layout import HEIGHT, WIDTH
from game.story import BALLOON_DELAYS, ENDING, MIDPOINT, STORY
from game.comic_motion import draw_actors
from game.comic_effects import (
    CAMERA_MARGIN, PANEL_BEATS, Impact, draw_effects, draw_panel_beat, impact_at, panel_frames, sample_impact,
)
from game.character_motion import EXHALE_START


PANEL_BOUNDS = ((254, 516, 790, 918), (810, 516, 1346, 918),
                (254, 94, 790, 496), (810, 94, 1346, 496))
WIDE_BOUNDS = ((90, 529, 790, 879), (810, 529, 1510, 879),
               (90, 159, 790, 509), (810, 159, 1510, 509))
COMIC_PAGES = {
    "story": (STORY, PANEL_BOUNDS, "오늘도 야근"),
    "midpoint": (MIDPOINT, WIDE_BOUNDS, "퇴근까지 절반"),
    "ending": (ENDING, WIDE_BOUNDS, "오늘의 야근은 여기까지"),
}
DIALOGUE_SIZE = 22
INK = (29, 35, 35)
PAPER = (239, 227, 201)
GOLD = (239, 193, 103)


def ease(value):
    return 1 - (1 - min(1.0, max(0.0, value))) ** 3


def dialogue_bounds(index, panels=PANEL_BOUNDS):
    left, _, right, top = panels[index]
    return ((left + 12, top - 100, left + 262, top - 12),
            (right - 262, top - 100, right - 12, top - 12))


def rounded(bounds, radius, color):
    left, bottom, right, top = bounds
    for y in range(round(bottom), round(top) + 1):
        distance = max(bottom + radius - y, y - (top - radius), 0)
        inset = radius - sqrt(max(0, radius * radius - distance * distance))
        p.draw_line(left + inset, y, right - inset, y, *color)


def bubble(view, bounds, words, progress, side, *, point_right=False):
    left, bottom, right, top = bounds
    offset = round((1 - ease(progress)) * 7)
    bottom, top = bottom + offset, top + offset
    rounded((left + 3, bottom - 3, right + 3, top - 3), 14, INK)
    rounded((left - 2, bottom - 2, right + 2, top + 2), 14, INK)
    rounded((left, bottom, right, top), 12, (255, 251, 231))
    anchor = right - 28 if point_right else left + (90 if side == 0 else 150)
    tip = anchor + (18 if point_right else 14 if side == 0 else -14)
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
    impact = sample_impact(index, age)
    dx, dy = round(impact.x), round(impact.y)
    camera_bounds = (left + dx, bottom + dy, right + dx, top + dy)
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
                        cw - 4, ch - 4, (left + right) / 2 + dx, (bottom + top) / 2 + dy,
                        width + CAMERA_MARGIN * 2, height + CAMERA_MARGIN * 2)
        draw_actors(load_image, camera_bounds, age, index, 0.18 + 0.82 * entrance)
        draw_effects(camera_bounds, age, index, impact)
    finally:
        image.opacify(1)
        p.SDL_RenderSetClipRect(p.renderer, byref(previous) if enabled else None)


def draw_full_panel(load_image, image_name, bounds, age, impact=Impact(), mix=1.0):
    left, bottom, right, top = bounds
    image = load_image(image_name)
    width, height = right - left, top - bottom
    scale = 1 - .035 * ease(age / 4) - .035 * impact.strength
    source_width = round(min(image.w, image.h * width / height) * scale)
    source_height = round(min(image.h, image.w * height / width) * scale)
    margin_x, margin_y = image.w - source_width, image.h - source_height
    source_x = round(max(0, min(margin_x, margin_x / 2 - impact.x * source_width / width)))
    source_y = round(max(0, min(margin_y, margin_y / 2 - impact.y * source_height / height)))
    image.opacify((.25 + .75 * ease(age / .6)) * mix)
    try:
        image.clip_draw(source_x, source_y, source_width, source_height,
                        (left + right) / 2, (bottom + top) / 2, width, height)
    finally:
        image.opacify(1)


def draw_comic_page(view, playback, load_image, *, scene="story"):
    story, panels, title = COMIC_PAGES[scene]
    page_left, page_right = panels[0][0] - 20, panels[1][2] + 16
    page_bottom, page_top = panels[-1][1] - 6, panels[0][3] + 16
    p.draw_rectangle(0, 0, WIDTH, HEIGHT, 17, 30, 34, filled=True)
    # 넓은 여백과 굵은 먹선으로 한 장의 만화책처럼 묶는다.
    p.draw_rectangle(page_left + 7, page_bottom - 6, page_right + 7, page_top - 2, 7, 17, 20, filled=True)
    p.draw_rectangle(page_left, page_bottom, page_right, page_top, *PAPER, filled=True)
    view.centered(800, page_top + 12, title, 22, GOLD)
    for index, (page, bounds) in enumerate(zip(story, panels)):
        left, bottom, right, top = bounds
        p.draw_rectangle(left - 4, bottom - 4, right + 4, top + 4, *INK, filled=True)
        p.draw_rectangle(*bounds, 248, 239, 220, filled=True)
        age = playback.age(index)
        if age is None:
            continue
        beat = PANEL_BEATS.get(page.atlas)
        if beat is None:
            draw_picture(load_image, bounds, age, index)
        else:
            p.draw_rectangle(*bounds, 47, 57, 53, filled=True)
            impact = impact_at(((beat.time, .46, beat.shake),), age) if beat.shake else Impact()
            for image_name, opacity in panel_frames(page.atlas, beat, age):
                draw_full_panel(load_image, image_name, bounds, age, impact, opacity)
            draw_panel_beat(view, bounds, beat, age, impact)
        if index == playback.index:
            p.draw_rectangle(left - 2, bottom - 2, right + 2, top + 2, *GOLD)
        delays = (beat.time + .25,) if beat and beat.effect == "fizzle" else BALLOON_DELAYS
        for side, (bounds, words, delay) in enumerate(zip(dialogue_bounds(index, panels), page.dialogue, delays)):
            if age >= delay:
                point_right = scene != "story" and index == 1 and side == 1
                if point_right:
                    # 화면 오른쪽 위의 병사·용사 얼굴을 비워 둔다.
                    bx1, by1, bx2, by2 = bounds
                    bounds = (bx1 - 152, by1, bx2 - 152, by2)
                bubble(view, bounds, words, (age - delay) / 0.3, side, point_right=point_right)
        effect_delay = beat.time if beat else .2
        if age >= effect_delay:
            effect = "하아..." if scene == "story" and index == 2 and age >= EXHALE_START else page.effect
            pop = ease((age - effect_delay) / 0.35)
            x = left + (right - left) * 0.58
            y = bottom + 54 + (1 - pop) * 14
            wobble_age = age - effect_delay if beat else age
            if index == playback.index and wobble_age < 1.0:
                x += sin(wobble_age * 35) * (1 - pop) * 5
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                view.centered(x + dx, y + dy, effect, 26, INK)
            view.centered(x, y, effect, 26, GOLD)
    # 이야기 설명문 대신 현재 컷과 다음 컷까지의 진행만 표시한다.
    progress_y = panels[-1][1] - 76
    for index in range(4):
        x = 716 + index * 46
        color = GOLD if index <= playback.index else (66, 83, 82)
        p.draw_rectangle(x, progress_y, x + 30, progress_y + 5, *color, filled=True)
        if index == playback.index and not playback.finished:
            p.draw_rectangle(x, progress_y, x + 30 * min(1, playback.elapsed / playback.duration), progress_y + 5,
                             126, 224, 201, filled=True)
