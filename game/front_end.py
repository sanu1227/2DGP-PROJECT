"""그림 타이틀, 네 컷 프롤로그, 그림과 연결된 복구·조작 안내."""

from dataclasses import dataclass
from math import sin
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.layout import WIDTH, HEIGHT


INK = (250, 239, 209)
MUTED = (188, 200, 191)
GOLD = (239, 193, 103)
TEAL = (126, 224, 201)
ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "menu_v2"
STORY = (
    ("용사는 승리하고 떠났다.",
     "깊은 던전을 돌파한 용사의 발걸음이 멀어진다.",
     "남은 것은 부서진 함정과, 뿔뿔이 흩어진 해골 병사들."),
    ("누군가는, 그 뒤를 고쳐야 한다.",
     "던전 수리공인 당신의 근무는 이제 시작이다.",
     "쓸 만한 부품을 모으고, 흩어진 동료들을 다시 일으켜 세우자."),
    ("다시 움직일 수 있도록.",
     "부품은 함정으로, 뼈는 작업대로.",
     "텅 빈 초소에 병사가 돌아오면 던전도 조금씩 제 모습을 찾는다."),
    ("마지막으로, 돌아올 길을 남겨라.",
     "레버를 당기면 함정이 깨어나고, 익숙한 통로는 막힌다.",
     "수리를 끝내는 것만큼 중요한 일. 무사히 출구로 돌아오기."),
)


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
            self.images[name] = p.load_image(str(ART_ROOT / f"{name}.png"))
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
                Button("story_next", "작업 안내" if self.story_page == 3 else "다음 이야기", (1260, 44, 1520, 100)),
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
            self.draw_comic(self.story_page)
            self.caption(view, *STORY[self.story_page])
            self.page_mark(view, "프롤로그", self.story_page + 1, 4)
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
        for offset in (-1, 1):
            view.centered(800 + offset, 311 - offset, "용사가 떠난 뒤, 우리의 일이 시작된다.", 22, (12, 25, 28))
        view.centered(800, 311, "용사가 떠난 뒤, 우리의 일이 시작된다.", 22, INK)
        view.centered(800, 43, "클릭 / Enter 선택     방향키 / Tab 이동", 16, MUTED)

    def draw_comic(self, page):
        atlas = self.image("story")
        width, height = atlas.w // 2, atlas.h // 2
        left = (page % 2) * width
        bottom = (1 - page // 2) * height
        # 같은 컷을 어둡게 확장한 배경 위에 원래 비율의 그림을 놓는다.
        p.SDL_SetTextureColorMod(atlas.texture, 40, 52, 53)
        try:
            atlas.clip_draw(left, bottom, width, height, 800, 480, 1600, 1200)
        finally:
            p.SDL_SetTextureColorMod(atlas.texture, 255, 255, 255)
        atlas.clip_draw(left, bottom, width, height, 800, 600, 960, 720)
        panel((318, 238, 1282, 960), (144, 119, 75), False)
        # 그림 아래 자막을 분리해 복구 동작이 글자에 가리지 않게 한다.
        panel((0, 0, WIDTH, 238), (14, 25, 28))
        p.draw_line(80, 237, 1520, 237, *GOLD)

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
            self.key_hint(view, 1440, 745, "Q", "물건 내려놓기")
            self.key_hint(view, 1440, 636, "B", "한 차례 대기")
            self.key_hint(view, 1440, 527, "Z / Backspace", "직전 행동 되돌리기")
            self.key_hint(view, 1440, 418, "R", "현재 방 다시 시작")
