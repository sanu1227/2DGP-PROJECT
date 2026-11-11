"""플레이를 멈춘 상태에서 사용하는 메뉴와 조작 안내."""

import pico2d.pico2d as p

from game.front_end import Button, bevel
from game.layout import WIDTH, HEIGHT
from game.logo_mode import fade_to_black

INK = (239, 237, 219)
MUTED = (164, 182, 177)
GOLD = (231, 190, 108)
TEAL = (112, 216, 190)


class PlayClock:
    """메뉴에서 흐른 실제 시간을 모든 플레이 애니메이션에서 제외한다."""

    def __init__(self):
        self.offset = 0.0
        self.frozen = None

    def now(self, real_time):
        return self.frozen if self.frozen is not None else real_time - self.offset

    def pause(self, real_time):
        if self.frozen is None:
            self.frozen = self.now(real_time)

    def resume(self, real_time):
        if self.frozen is not None:
            self.offset = real_time - self.frozen
            self.frozen = None


class PlayMenu:
    def __init__(self):
        self.mode = None
        self.selected = 0

    @property
    def active(self):
        return self.mode is not None

    def open(self, view):
        self.mode, self.selected = "pause", 0
        view.pause()
        view.mouse_position = None

    def close(self, view):
        self.mode = None
        view.resume()
        view.mouse_position = None

    @property
    def buttons(self):
        if self.mode == "controls":
            return (Button("back", "메뉴로 돌아가기", (610, 224, 990, 282)),)
        return tuple(Button(action, label, (550, 574 - i * 80, 1050, 636 - i * 80))
                     for i, (action, label) in enumerate((
                         ("resume", "계속하기"), ("restart", "다시 시작"),
                         ("controls", "조작법"), ("title", "타이틀로"))))

    def activate(self, action):
        if action == "controls":
            self.mode, self.selected = "controls", 0
        elif action == "back":
            self.mode, self.selected = "pause", 2
        return action

    def handle(self, event):
        if event.type in (p.SDL_MOUSEMOTION, p.SDL_MOUSEBUTTONDOWN):
            point = event.x, HEIGHT - 1 - event.y
            for index, button in enumerate(self.buttons):
                if button.contains(point):
                    self.selected = index
                    if event.type == p.SDL_MOUSEBUTTONDOWN and event.button == p.SDL_BUTTON_LEFT:
                        return self.activate(button.action)
                    break
        elif event.type == p.SDL_KEYDOWN:
            if event.key == p.SDLK_ESCAPE:
                return self.activate("back" if self.mode == "controls" else "resume")
            if event.key in (p.SDLK_UP, p.SDLK_w, p.SDLK_DOWN, p.SDLK_s, p.SDLK_TAB):
                step = -1 if event.key in (p.SDLK_UP, p.SDLK_w) else 1
                self.selected = (self.selected + step) % len(self.buttons)
            elif event.key in (p.SDLK_RETURN, p.SDLK_SPACE):
                return self.activate(self.buttons[self.selected].action)
        return None

    def draw_buttons(self, view):
        for index, button in enumerate(self.buttons):
            chosen = index == self.selected
            bevel(button.bounds, (49, 91, 82) if chosen else (32, 48, 52), TEAL if chosen else (79, 100, 98))
            left, bottom, right, top = button.bounds
            view.centered((left + right) / 2, (bottom + top) / 2, button.label, 26, INK)

    def draw(self, view, game):
        fade_to_black(.72)
        bevel((380, 180, 1220, 800), (23, 36, 40), (104, 139, 127))
        if self.mode == "controls":
            view.centered(800, 742, "작업 조작법", 48, GOLD)
            controls = (
                ("이동", "좌클릭 / WASD / 방향키"),
                ("자동 이동 취소", "우클릭"),
                ("줍기 / 설치 / 내려놓기", "같은 칸에서 E / Space"),
                ("되돌리기", "Z / Backspace"),
                ("현재 방 다시 시작", "R"),
                ("일시정지 / 계속하기", "Esc"),
            )
            for i, (label, keys) in enumerate(controls):
                y = 648 - i * 53
                view.text(436, y, label, 22, INK)
                view.text(800, y, keys, 22, TEAL)
            view.centered(800, 315, "목표를 모두 복구한 뒤, 빈손으로 출구에 도착하세요.", 18, MUTED)
        else:
            view.centered(800, 742, "잠깐 휴식", 48, GOLD)
            view.centered(800, 686, game.level.title, 22, INK)
            hint = ("다시 시작하면 현재 방의 작업과 행동 횟수가 초기화됩니다." if self.selected == 1 else
                    "타이틀로 돌아가면 현재 방의 진행이 초기화됩니다." if self.selected == 3 else
                    "이동과 장치가 멈춰 있습니다. 천천히 쉬어 가세요.")
            view.centered(800, 278, hint, 18, MUTED)
        self.draw_buttons(view)
        view.centered(800, 130, "↑ ↓ 선택    Enter / Space 결정    Esc 돌아가기    마우스 클릭", 18, MUTED)
