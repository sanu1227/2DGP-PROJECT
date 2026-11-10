"""타이틀과 조작 설명. 메뉴 입력은 게임 행동으로 전달하지 않는다."""

from dataclasses import dataclass
from math import sin
from time import perf_counter

import pico2d.pico2d as p

from game.layout import WIDTH, HEIGHT


INK = (236, 231, 211)
MUTED = (157, 174, 173)
GOLD = (227, 187, 104)
TEAL = (104, 206, 184)


def panel(bounds, color, filled=True):
    p.draw_rectangle(*bounds, *color, filled=filled)


@dataclass(frozen=True)
class Button:
    action: str
    label: str
    bounds: tuple[int, int, int, int]

    def contains(self, point):
        x, y = point
        left, bottom, right, top = self.bounds
        return left <= x <= right and bottom <= y <= top


class FrontEnd:
    def __init__(self, show_title=True):
        self.screen = "title" if show_title else "playing"
        self.selected = 0

    @property
    def buttons(self):
        if self.screen == "title":
            return (
                Button("controls", "게임 시작", (112, 288, 532, 364)),
                Button("quit", "게임 종료", (112, 204, 532, 264)),
            )
        if self.screen == "controls":
            return (
                Button("start", "1번 방 시작", (1060, 90, 1488, 166)),
                Button("title", "타이틀로", (112, 100, 356, 156)),
            )
        return ()

    def activate(self, action):
        if action in ("title", "controls"):
            self.screen = action
            self.selected = 0
        elif action == "start":
            self.screen = "playing"
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
                return self.activate("title" if self.screen == "controls" else "quit")
            if event.key in (p.SDLK_TAB, p.SDLK_DOWN, p.SDLK_RIGHT, p.SDLK_UP, p.SDLK_LEFT):
                delta = -1 if event.key in (p.SDLK_UP, p.SDLK_LEFT) else 1
                self.selected = (self.selected + delta) % len(self.buttons)
            elif event.key in (p.SDLK_RETURN, p.SDLK_SPACE):
                return self.activate(self.buttons[self.selected].action)
        return None

    def draw(self, view):
        # 청록색 석재와 황동 테두리를 기존 던전 색상에 맞춘다.
        for y in range(0, HEIGHT, 4):
            blend = y / HEIGHT
            panel((0, y, WIDTH, y + 4), (int(13 + 8 * blend), int(23 + 10 * blend), int(28 + 10 * blend)))
        panel((36, 36, WIDTH - 36, HEIGHT - 36), (67, 77, 70), False)
        panel((44, 44, WIDTH - 44, HEIGHT - 44), (32, 48, 49), False)
        if self.screen == "title":
            self.draw_title(view)
        else:
            self.draw_controls(view)
        for index, button in enumerate(self.buttons):
            focused = index == self.selected
            panel(button.bounds, (60, 87, 79) if focused else (27, 42, 45))
            panel(button.bounds, GOLD if focused else (84, 103, 99), False)
            left, bottom, right, top = button.bounds
            if focused:
                panel((left, bottom, left + 5, top), GOLD)
            view.centered((left + right) / 2, (bottom + top) / 2, button.label, 22, INK)

    def draw_title(self, view):
        view.text(112, 807, "DUNGEON RESTORATION", 16, GOLD)
        view.text(108, 700, "용사가", 64, INK)
        view.text(108, 612, "지나간 자리", 64, INK)
        panel((112, 548, 190, 551), GOLD)
        view.text(112, 497, "용사가 떠난 뒤, 우리의 일이 시작된다.", 22, INK)
        view.text(112, 449, "흩어진 부품을 모으고, 던전에 다시 숨을 불어넣으세요.", 18, MUTED)
        view.text(112, 148, "클릭 또는 Enter로 선택 · 방향키 / Tab으로 이동", 16, MUTED)
        view.text(112, 92, "2.5D 던전 복구 퍼즐", 16, GOLD)

        # 게임에 쓰이는 실제 에셋으로 작은 정비실을 구성한다.
        art = view.art
        for depth in range(7):
            for row in range(4):
                col = depth - row
                if not 0 <= col < 4:
                    continue
                x, y = 1114 + (col - row) * 84, 640 - (col + row) * 42
                art.draw("floor_cracked" if (col + row) % 3 == 0 else "floor_plain", x, y, 0.75)
                if row == 0 or col == 0:
                    art.draw("wall_low_chipped" if col == row else "wall_low", x, y, 0.75)
                sprite = {(1, 1): "brazier", (2, 1): "trap_broken", (1, 2): "worker_se_idle",
                          (2, 2): "part", (3, 1): "lever_off", (3, 3): "rubble"}.get((col, row))
                if sprite:
                    art.draw(sprite, x, y, 0.75)
        for index in range(14):
            t = perf_counter() * 0.25 + index * 1.9
            x = 858 + (index * 53) % 460 + sin(t) * 9
            y = 370 + (index * 71) % 340 + sin(t * 0.7) * 12
            panel((x, y, x + 2, y + 2), (113, 103, 70))
        view.centered(1114, 255, "부품을 옮기고 · 장치를 복구하고 · 돌아올 길을 남기세요", 16, MUTED)

    def draw_controls(self, view):
        view.text(112, 840, "작업 전 안내", 48, INK)
        view.text(114, 786, "던전 수리공의 첫 근무입니다. 1번 방에서 하나씩 연습해 보세요.", 22, MUTED)
        cards = (
            (112, "01", "이동", "클릭 / WASD / 방향키", (
                "바닥이나 물건을 클릭하면 그 칸까지 이동합니다.",
                "우클릭하면 자동 이동을 멈춥니다.",
                "W / ↑  오른쪽 위    D / →  오른쪽 아래",
                "S / ↓  왼쪽 아래    A / ←  왼쪽 위",
            )),
            (580, "02", "복구", "E / Space", (
                "물건과 같은 칸에 선 뒤 눌러 주세요.",
                "줍기 · 함정 설치 · 레버 가동에 사용합니다.",
                "한 번에 물건 하나만 들 수 있습니다.",
                "Q  내려놓기    B  한 차례 대기",
            )),
            (1048, "03", "다시 시도", "Z / Backspace · R", (
                "Z / Backspace  직전 행동 되돌리기",
                "R  현재 방 처음부터 다시 시작",
                "2번 방부터 행동 횟수가 제한됩니다.",
                "횟수가 소진되어도 되돌리거나 재시작하세요.",
            )),
        )
        for x, number, title, keys, lines in cards:
            panel((x, 380, x + 440, 714), (28, 43, 47))
            panel((x, 380, x + 440, 714), (63, 83, 81), False)
            view.text(x + 24, 675, number, 18, GOLD)
            view.text(x + 76, 674, title, 32, INK)
            view.text(x + 24, 613, keys, 22, TEAL)
            for y, value in zip((550, 512, 468, 430), lines):
                view.text(x + 24, y, value, 16, MUTED)
        panel((112, 226, 1488, 336), (37, 54, 53))
        view.text(140, 304, "첫 임무 · 함정 복구", 22, GOLD)
        view.text(140, 266, "부품 줍기 / 함정에 설치 / 건너편 레버 가동 / 빈손으로 출구 복귀", 22, INK)
        view.text(420, 134, "1번 방은 행동 무제한 · 완료 후 Enter로 다음 방", 18, TEAL)
        view.text(420, 100, "게임 중 Esc는 종료 · 이 화면에서는 타이틀로 복귀", 16, MUTED)
