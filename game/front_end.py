"""그림 타이틀, 야근 코미디 프롤로그, 그림과 연결된 복구·조작 안내."""

from dataclasses import dataclass
from math import sin
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.layout import WIDTH, HEIGHT
from game.story import STORY


INK = (250, 239, 209)
MUTED = (188, 200, 191)
GOLD = (239, 193, 103)
TEAL = (126, 224, 201)
ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "menu_v2"
STORY_ROOT = ART_ROOT.parent / "story_overtime_v1"
STORY_IMAGES = {"overtime_01": STORY_ROOT / "act_01.png",
                "overtime_02": STORY_ROOT / "act_02.png"}
DIALOGUE_BOUNDS = ((258, 750, 658, 900), (936, 750, 1336, 900))
DIALOGUE_SIZE = 26


def panel(bounds, color, filled=True):
    p.draw_rectangle(*bounds, *color, filled=filled)


def bevel(bounds, fill, edge):
    """모서리를 깎은 게임 버튼. 그리는 영역과 클릭 영역을 공유한다."""
    left, bottom, right, top = bounds
    cut = 10
    for y in range(bottom, top + 1):
        inset = max(0, cut - min(y - bottom, top - y))
        p.draw_line(left + inset, y, right - inset, y, *fill)
    points = ((left + cut, bottom), (right - cut, bottom), (right, bottom + cut),
              (right, top - cut), (right - cut, top), (left + cut, top),
              (left, top - cut), (left, bottom + cut))
    for start, end in zip(points, points[1:] + points[:1]):
        p.draw_line(*start, *end, *edge)


@dataclass(frozen=True)
class Button:
    action: str
    label: str
    bounds: tuple[int, int, int, int]

    def contains(self, point):
        x, y = point
        left, bottom, right, top = self.bounds
        return (left <= x <= right and bottom <= y <= top
                and min(x - left, right - x) + min(y - bottom, top - y) >= 10)


class FrontEnd:
    def __init__(self, show_title=True):
        self.screen = "title" if show_title else "playing"
        self.selected = 0
        self.story_page = 0
        self.guide_page = 0
        self.images = {}

    def close(self):
        self.images.clear()

    def image(self, name):
        if name not in self.images:
            path = STORY_IMAGES[name] if name in STORY_IMAGES else ART_ROOT / f"{name}.png"
            self.images[name] = p.load_image(str(path))
            p.SDL_SetTextureScaleMode(self.images[name].texture, p.SDL_ScaleModeLinear)
        return self.images[name]

    @property
    def buttons(self):
        if self.screen == "title":
            return (
                Button("story", "게임 시작", (600, 188, 1000, 266)),
                Button("quit", "게임 종료", (650, 100, 950, 162)),
            )
        if self.screen == "story":
            return (
                Button("story_next", "작업 안내" if self.story_page == len(STORY) - 1 else "다음 이야기", (1260, 44, 1520, 100)),
                Button("story_back", "타이틀로" if self.story_page == 0 else "이전 이야기", (80, 44, 340, 100)),
                Button("controls", "건너뛰기", (1370, 876, 1540, 924)),
            )
        if self.screen == "controls":
            return (
                Button("guide_next", "1번 방 시작" if self.guide_page == 1 else "조작과 복귀", (1260, 44, 1520, 100)),
                Button("guide_back", "이전 안내" if self.guide_page else "이야기로", (80, 44, 340, 100)),
            )
        return ()

    def activate(self, action):
        self.selected = 0
        if action == "title":
            self.screen = "title"
            self.story_page = self.guide_page = 0
        elif action == "story":
            self.screen, self.story_page = "story", 0
        elif action == "story_next":
            if self.story_page < len(STORY) - 1:
                self.story_page += 1
            else:
                self.screen, self.guide_page = "controls", 0
        elif action == "story_back":
            if self.story_page:
                self.story_page -= 1
            else:
                self.screen = "title"
        elif action == "controls":
            self.screen, self.guide_page = "controls", 0
        elif action == "guide_next":
            if self.guide_page == 0:
                self.guide_page = 1
            else:
                self.screen = "playing"
                return "start"
        elif action == "guide_back":
            if self.guide_page:
                self.guide_page -= 1
            else:
                self.screen, self.story_page = "story", len(STORY) - 1
        return action

    def handle(self, event):
        if event.type in (p.SDL_MOUSEMOTION, p.SDL_MOUSEBUTTONDOWN):
            point = (event.x, HEIGHT - 1 - event.y)
            for index, button in enumerate(self.buttons):
                if button.contains(point):
                    self.selected = index
                    if event.type == p.SDL_MOUSEBUTTONDOWN and event.button == p.SDL_BUTTON_LEFT:
                        return self.activate(button.action)
                    break
        elif event.type == p.SDL_KEYDOWN:
            if event.key == p.SDLK_ESCAPE:
                return self.activate("quit" if self.screen == "title" else "title")
            if self.screen == "story" and event.key in (p.SDLK_LEFT, p.SDLK_RIGHT):
                return self.activate("story_back" if event.key == p.SDLK_LEFT else "story_next")
            if event.key in (p.SDLK_TAB, p.SDLK_DOWN, p.SDLK_RIGHT, p.SDLK_UP, p.SDLK_LEFT):
                delta = -1 if event.key in (p.SDLK_UP, p.SDLK_LEFT) else 1
                self.selected = (self.selected + delta) % len(self.buttons)
            elif event.key in (p.SDLK_RETURN, p.SDLK_SPACE):
                return self.activate(self.buttons[self.selected].action)
        return None

    def draw(self, view):
        if self.screen == "title":
            self.draw_title(view)
        elif self.screen == "story":
            page = STORY[self.story_page]
            self.draw_comic(page.cell, page.atlas, footer_height=112)
            self.draw_dialogue(view)
            self.page_mark(view, "오늘도 야근", self.story_page + 1, len(STORY))
        else:
            self.draw_controls(view)
        for index, button in enumerate(self.buttons):
            focused = index == self.selected
            fill = (52, 89, 76) if focused else (27, 43, 43)
            edge = GOLD if focused else (123, 123, 99)
            left, bottom, right, top = button.bounds
            bevel((left, bottom - 5, right, top - 5), (13, 20, 20), (61, 49, 33))
            bevel(button.bounds, fill, edge)
            p.draw_line(left + 12, top - 3, right - 12, top - 3, *edge)
            size = 32 if self.screen == "title" and index == 0 else 22
            x, y = (left + right) / 2, (bottom + top) / 2
            view.centered(x + 1, y - 2, button.label, size, (10, 21, 22))
            view.centered(x, y, button.label, size, INK if focused else MUTED)

    def draw_title(self, view):
        self.image("title").draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
        for index in range(14):
            t = perf_counter() * 0.28 + index * 2.1
            x = 120 + index * 103 + sin(t) * 13
            y = 310 + (index * 79) % 520 + sin(t * 0.8) * 19
            panel((x, y, x + 2, y + 2), GOLD)
        view.centered(WIDTH / 2, 54, "1~6  원하는 방 바로 시작", 16, GOLD)

    def draw_comic(self, page, image_name="story", *, footer_height=238):
        atlas = self.image(image_name)
        width, height = atlas.w // 2, atlas.h // 2
        left = (page % 2) * width
        bottom = (1 - page // 2) * height
        # 같은 컷을 어둡게 확장한 배경 위에 원래 비율의 그림을 놓는다.
        p.SDL_SetTextureColorMod(atlas.texture, 40, 52, 53)
        try:
            atlas.clip_draw(left, bottom, width, height, 800, 480, 1600, 1200)
        finally:
            p.SDL_SetTextureColorMod(atlas.texture, 255, 255, 255)
        picture_height = HEIGHT - footer_height - 2
        picture_width = picture_height * width / height
        atlas.clip_draw(left, bottom, width, height, WIDTH / 2, HEIGHT - picture_height / 2,
                        picture_width, picture_height)
        panel(((WIDTH - picture_width) / 2 - 2, footer_height,
               (WIDTH + picture_width) / 2 + 2, HEIGHT), (144, 119, 75), False)
        # 스토리는 버튼 높이만 남겨 그림을 키우고, 작업 안내는 설명 공간을 확보한다.
        panel((0, 0, WIDTH, footer_height), (14, 25, 28))
        p.draw_line(80, footer_height - 1, 1520, footer_height - 1, *GOLD)

    def draw_dialogue(self, view):
        # 자막은 그림에 굽지 않아 작은 글자도 선명하게 읽고 수정할 수 있다.
        page = STORY[self.story_page]
        for bounds, words in zip(DIALOGUE_BOUNDS, page.dialogue):
            left, bottom, right, top = bounds
            fill, outline = (255, 249, 225), (31, 37, 36)
            bevel((left + 4, bottom - 4, right + 4, top - 4), outline, outline)
            bevel(bounds, fill, outline)
            anchor = left + 285 if left < WIDTH / 2 else left + 175
            tip = anchor + 27
            for row in range(29):
                t = row / 28
                x1 = anchor - 12 + (tip - anchor + 12) * t
                x2 = anchor + 12 + (tip - anchor - 12) * t
                p.draw_line(x1, bottom - row, x2, bottom - row, *fill)
            p.draw_line(anchor - 12, bottom, tip, bottom - 28, *outline)
            p.draw_line(anchor + 12, bottom, tip, bottom - 28, *outline)
            view.text(left + 18, top - 18, words[0], 13, (109, 93, 61))
            for index, value in enumerate(words[1:]):
                view.centered((left + right) / 2, top - 50 - index * 33, value, DIALOGUE_SIZE, outline)
        x, y, effect = page.effect
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            view.centered(x + dx, y + dy, effect, 32, (22, 31, 31))
        view.centered(x, y, effect, 32, GOLD)

    @staticmethod
    def caption(view, title, first, second):
        view.centered(800, 202, title, 32, GOLD)
        view.centered(800, 158, first, 22, INK)
        view.centered(800, 124, second, 22, INK)
        view.centered(800, 28, "클릭 / Enter 선택     Tab 버튼 이동     Esc 타이틀", 13, MUTED)

    @staticmethod
    def page_mark(view, label, page, total):
        panel((685, 918, 915, 952), (20, 35, 37))
        view.centered(800, 935, f"{label}  ·  {page} / {total}", 16, GOLD)

    @staticmethod
    def key_hint(view, x, y, key, description):
        view.centered(x, y, key, 22, TEAL)
        view.centered(x, y - 34, description, 16, INK)

    def draw_controls(self, view):
        self.draw_comic(2 + self.guide_page)
        self.page_mark(view, "작업 안내", self.guide_page + 1, 2)
        if self.guide_page == 0:
            self.caption(view, "당신은 던전의 수리공",
                         "방마다 요구하는 함정과 병사를 모두 복구하세요.",
                         "부품과 뼈는 하나씩 운반합니다. 같은 칸에서 E / Space로 작업하세요.")
            view.centered(160, 837, "함정 복구", 32, GOLD)
            view.item("part", 160, 725, 0.48)
            view.centered(160, 669, "부품을 운반하고", 18, INK)
            view.art.draw("trap_installed", 160, 553, 0.65)
            view.centered(160, 503, "함정에 설치", 18, INK)
            self.key_hint(view, 160, 414, "E / Space", "빈손으로 레버 가동")
            view.centered(1440, 837, "병사 복구", 32, GOLD)
            view.item("bone", 1440, 725, 0.48)
            view.centered(1440, 669, "뼈 묶음 2개를 작업대로", 18, INK)
            view.art.draw("soldier_deployed", 1440, 515, 0.46)
            view.centered(1440, 465, "병사로 조립한 뒤", 18, INK)
            self.key_hint(view, 1440, 384, "E / Space", "초소에 배치")
        else:
            self.caption(view, "돌아올 길까지가 복구입니다",
                         "가동한 함정과 배치한 병사는 길을 막습니다. 빈손으로 출구에 돌아오세요.",
                         "1번 방은 행동 무제한. 2번 방부터 제한이 있어도 Z로 되돌릴 수 있습니다.")
            view.centered(160, 837, "이동과 작업", 32, GOLD)
            self.key_hint(view, 160, 745, "좌클릭", "목표 칸까지 이동")
            self.key_hint(view, 160, 636, "WASD / 방향키", "한 칸 이동")
            self.key_hint(view, 160, 527, "우클릭", "자동 이동 취소")
            self.key_hint(view, 160, 418, "E / Space", "현재 칸에서 작업")
            view.centered(1440, 837, "차근차근 복구", 32, GOLD)
            self.key_hint(view, 1440, 745, "E / Space", "빈 바닥에 내려놓기")
            self.key_hint(view, 1440, 636, "벨트", "끝까지 자동 운반")
            self.key_hint(view, 1440, 527, "Z / Backspace", "직전 행동 되돌리기")
            self.key_hint(view, 1440, 418, "R", "현재 방 다시 시작")
