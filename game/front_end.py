"""그림 타이틀, 야근 코미디 프롤로그, 그림과 연결된 복구·조작 안내."""

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.layout import WIDTH, HEIGHT
from game.story import ENDING, ENDING_DURATIONS, MIDPOINT, MIDPOINT_DURATIONS, STORY, ComicPlayback, REVEAL_SECONDS
from game.comic import COMIC_PAGES, draw_comic_page
from game.comic_motion import MOTION_IMAGES
from game.story_audio import StoryAudio
from game.title_motion import TITLE_IMAGES, draw_title
from game.logo_mode import LOGO_IMAGES, LogoPlayback, draw_logos, fade_to_black, smooth, FADE_SECONDS


INK = (250, 239, 209)
MUTED = (188, 200, 191)
GOLD = (239, 193, 103)
TEAL = (126, 224, 201)
ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "menu_v2"
STORY_ROOT = ART_ROOT.parent / "story_overtime_v1"
STORY_IMAGES = {"overtime_01": STORY_ROOT / "act_01.png",
                "overtime_02": STORY_ROOT / "act_02.png", **MOTION_IMAGES, **TITLE_IMAGES, **LOGO_IMAGES}
STORY_IMAGES.update({page.atlas: ART_ROOT.parent / f"{scene}_v1" / f"{page.atlas}.jpg"
                     for scene, pages in (("midpoint", MIDPOINT), ("ending", ENDING)) for page in pages})
STORY_IMAGES["midpoint_light_off"] = ART_ROOT.parent / "midpoint_v1" / "midpoint_light_off.jpg"


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
    def __init__(self, show_title=True, audio=None):
        self.screen = "logo" if show_title else "playing"
        self.logos = LogoPlayback()
        self.logo_clock = None
        self.selected = 0
        self.comic = ComicPlayback()
        self.ending = ComicPlayback(durations=ENDING_DURATIONS)
        self.comics = {
            "story": self.comic,
            "midpoint": ComicPlayback(durations=MIDPOINT_DURATIONS),
            "ending": self.ending,
        }
        self.ending_return = "title"
        self.story_clock = None
        self.guide_page = 0
        self.images = {}
        self.audio = audio if audio is not None else StoryAudio()
        self.title_elapsed = 0.0
        self.title_clock = None
        self.title_fade_in = False
        self.progress = None
        self.levels = ()

    def close(self):
        self.audio.close()
        self.images.clear()

    @property
    def story_page(self):
        return self.active_comic.index

    @property
    def active_comic(self):
        return self.comics.get(self.screen, self.comic)

    @property
    def ending_return_label(self):
        return "방 선택으로" if self.ending_return == "rooms" else "타이틀로"

    def update(self, now):
        if self.screen == "logo":
            if self.logo_clock is not None:
                self.logos.update(now - self.logo_clock)
            self.logo_clock = now
            if self.logos.finished:
                self.finish_logos(now)
        comic_screen = self.screen in self.comics
        if comic_screen and self.story_clock is not None:
            self.active_comic.update(now - self.story_clock)
            if self.screen == "story":
                self.audio.update(self.story_page, self.comic.elapsed, self.comic.paused)
        elif self.screen != "story":
            self.audio.stop()
        self.story_clock = now if comic_screen else None
        if self.screen == "title" and self.title_clock is not None:
            self.title_elapsed += max(0, now - self.title_clock)
        self.title_clock = now if self.screen == "title" else None

    def finish_logos(self, now):
        self.screen = "title"
        self.logo_clock = None
        self.selected = 0
        self.title_elapsed = 0.0
        self.title_clock = now
        self.title_fade_in = True

    def image(self, name):
        if name not in self.images:
            path = STORY_IMAGES[name] if name in STORY_IMAGES else ART_ROOT / f"{name}.png"
            self.images[name] = p.load_image(str(path))
            p.SDL_SetTextureScaleMode(self.images[name].texture, p.SDL_ScaleModeLinear)
        return self.images[name]

    @property
    def buttons(self):
        if self.screen == "title":
            start = Button("story", "게임 시작", (600, 188, 1000, 266))
            quit_button = Button("quit", "게임 종료", (650, 100, 950, 162))
            if not self.cleared_rooms:
                return start, quit_button
            options = [start]
            if self.progress.checkpoint is not None:
                options.insert(0, Button("continue", "이어하기", (330, 196, 580, 258)))
            options.append(Button("rooms", "방 선택", (1020, 196, 1270, 258)))
            return (*options, quit_button)
        if self.screen == "rooms":
            return tuple(
                Button(f"room:{index}", f"{index + 1:02d}   {level.title}",
                       (400, 760 - row * 65, 1200, 816 - row * 65))
                for row, (index, level) in enumerate(self.cleared_rooms)
            ) + (Button("title", "타이틀로", (650, 106, 950, 162)),)
        if self.screen in self.comics:
            comic = self.active_comic
            next_label, back_label = {
                "story": ("작업 안내", "타이틀로"),
                "midpoint": ("5번 방으로", "건너뛰기"),
                "ending": (self.ending_return_label, self.ending_return_label),
            }[self.screen]
            buttons = [
                Button("story_next", next_label if comic.index == len(comic.durations) - 1 else "다음 컷", (1260, 30, 1520, 78)),
                Button("story_back", back_label if comic.index == 0 else "이전 컷", (80, 30, 340, 78)),
            ]
            if self.screen == "story":
                buttons.append(Button("controls", "건너뛰기", (1370, 876, 1540, 924)))
            buttons.append(Button("story_play", "다시 보기" if comic.finished else
                                  "자동재생" if comic.paused else "일시정지", (680, 34, 920, 76)))
            return tuple(buttons)
        if self.screen == "controls":
            return (
                Button("guide_next", "1번 방 시작" if self.guide_page == 1 else "조작과 복귀", (1260, 44, 1520, 100)),
                Button("guide_back", "이전 안내" if self.guide_page else "이야기로", (80, 44, 340, 100)),
            )
        return ()

    @property
    def cleared_rooms(self):
        if self.progress is None:
            return ()
        return tuple((index, level) for index, level in enumerate(self.levels)
                     if level.id in self.progress.completed)

    def activate(self, action):
        if action == "logo_next":
            self.logos.advance()
            if self.logos.finished:
                self.finish_logos(perf_counter())
            else:
                self.logo_clock = perf_counter()
            return action
        self.selected = 0
        comic = self.active_comic
        comic_return = self.ending_return if self.screen == "ending" else "title"
        resuming_story = action == "story_play" and not comic.finished
        if action == "title":
            self.screen = "title"
            self.comic.reset()
            self.guide_page = 0
            self.title_elapsed = 0.0
        elif action in self.comics:
            self.screen = action
            self.active_comic.reset()
        elif action == "rooms":
            self.screen = "rooms"
        elif action == "continue" or action.startswith("room:"):
            self.screen = "playing"
        elif action == "midpoint_continue":
            self.screen = "playing"
        elif action in ("story_next", "story_back"):
            forward = action == "story_next"
            if not (comic.advance() if forward else comic.back()):
                if self.screen == "midpoint":
                    self.screen, action = "playing", "midpoint_continue"
                elif forward and self.screen == "story":
                    self.screen, self.guide_page = "controls", 0
                else:
                    self.screen = comic_return
        elif action == "story_play":
            if comic.finished:
                comic.reset()
            else:
                comic.paused = not comic.paused
        elif action == "controls":
            self.screen, self.guide_page = "controls", 0
        elif action == "guide_next":
            if self.guide_page == 0:
                self.guide_page = 1
            else:
                self.screen = "playing"
                self.audio.stop()
                return "start"
        elif action == "guide_back":
            if self.guide_page:
                self.guide_page -= 1
            else:
                self.screen = "story"
                self.comic.index = len(STORY) - 1
                self.comic.elapsed = min(REVEAL_SECONDS, self.comic.duration)
                self.comic.paused = True
        self.story_clock = perf_counter() if self.screen in self.comics else None
        if self.screen == "story":
            if resuming_story:
                self.audio.set_paused(self.comic.paused)
            else:
                self.audio.seek(self.story_page, self.comic.elapsed, self.comic.paused)
        else:
            self.audio.stop()
        if self.screen == "title":
            self.title_elapsed = 0.0
            self.title_clock = perf_counter()
            self.title_fade_in = False
        else:
            self.title_clock = None
        if self.screen != "logo":
            self.logo_clock = None
        return action

    def handle(self, event):
        if self.screen == "logo":
            if event.type == p.SDL_KEYDOWN:
                if event.key in (p.SDLK_RETURN, p.SDLK_SPACE):
                    return self.activate("logo_next")
                if event.key == p.SDLK_ESCAPE:
                    return self.activate("title")
            elif event.type == p.SDL_MOUSEBUTTONDOWN and event.button == p.SDL_BUTTON_LEFT:
                return self.activate("logo_next")
            return None
        if event.type in (p.SDL_MOUSEMOTION, p.SDL_MOUSEBUTTONDOWN):
            point = (event.x, HEIGHT - 1 - event.y)
            for index, button in enumerate(self.buttons):
                if button.contains(point):
                    self.selected = index
                    if event.type == p.SDL_MOUSEBUTTONDOWN and event.button == p.SDL_BUTTON_LEFT:
                        return self.activate(button.action)
                    break
            else:
                if (self.screen in self.comics and event.type == p.SDL_MOUSEBUTTONDOWN
                        and event.button == p.SDL_BUTTON_LEFT):
                    _, panels, _ = COMIC_PAGES[self.screen]
                    left, bottom, right, top = panels[self.story_page]
                    if left <= point[0] <= right and bottom <= point[1] <= top:
                        return self.activate("story_next")
        elif event.type == p.SDL_KEYDOWN:
            if event.key == p.SDLK_ESCAPE:
                if self.screen == "midpoint":
                    return self.activate("midpoint_continue")
                if self.screen == "ending":
                    return self.activate(self.ending_return)
                return self.activate("quit" if self.screen == "title" else "title")
            if self.screen in self.comics and event.key in (p.SDLK_LEFT, p.SDLK_RIGHT):
                return self.activate("story_back" if event.key == p.SDLK_LEFT else "story_next")
            if self.screen in self.comics and event.key == p.SDLK_SPACE:
                return self.activate("story_next")
            if event.key in (p.SDLK_TAB, p.SDLK_DOWN, p.SDLK_RIGHT, p.SDLK_UP, p.SDLK_LEFT):
                delta = -1 if event.key in (p.SDLK_UP, p.SDLK_LEFT) else 1
                self.selected = (self.selected + delta) % len(self.buttons)
            elif event.key in (p.SDLK_RETURN, p.SDLK_SPACE):
                return self.activate(self.buttons[self.selected].action)
        return None

    def draw(self, view):
        if self.screen == "logo":
            draw_logos(self.image, self.logos)
        elif self.screen == "title":
            self.draw_title(view)
        elif self.screen in self.comics:
            draw_comic_page(view, self.active_comic, self.image, scene=self.screen)
        elif self.screen == "rooms":
            panel((0, 0, WIDTH - 1, HEIGHT - 1), (14, 24, 26))
            view.centered(800, 895, "복구한 방", 48, GOLD)
            view.centered(920, 841, "내 최고 기록", 16, MUTED)
            view.centered(1090, 841, "최단 횟수", 16, MUTED)
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
            size = 32 if button.action == "story" else 22
            x, y = (left + right) / 2, (bottom + top) / 2
            if self.screen == "rooms" and button.action.startswith("room:"):
                level = self.levels[int(button.action.split(":")[1])]
                best = self.progress.records[level.id]
                minimum = level.minimum_actions
                view.text(left + 30, y, button.label, 22, INK)
                view.centered(920, y, f"{best}회" if best is not None else "기록 없음", 18,
                              TEAL if best is not None else MUTED)
                view.centered(1090, y, f"{minimum}회" if minimum is not None else "—", 18, GOLD)
                continue
            view.centered(x + 1, y - 2, button.label, size, (10, 21, 22))
            view.centered(x, y, button.label, size, INK if focused else MUTED)
        if self.screen == "title" and self.title_fade_in:
            fade_to_black(1 - smooth(self.title_elapsed / FADE_SECONDS))
        if self.screen in ("title", "rooms") and self.progress and self.progress.notice:
            view.centered(800, 60, self.progress.notice, 18, GOLD)

    def draw_title(self, view):
        draw_title(self.image, self.title_elapsed)

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
            self.key_hint(view, 1440, 636, "새 장치", "연속 반사 · 잔해 · 인부")
            self.key_hint(view, 1440, 527, "Z / Backspace", "직전 행동 되돌리기")
            self.key_hint(view, 1440, 418, "R", "현재 방 다시 시작")
