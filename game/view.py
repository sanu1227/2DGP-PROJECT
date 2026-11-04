"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

import os
from pathlib import Path

import pico2d.pico2d as p

from game.model import Game

WIDTH, HEIGHT = 1280, 900
INK = (226, 230, 219)
MUTED = (158, 169, 166)
GOLD = (227, 187, 104)
TEAL = (104, 206, 184)
RED = (232, 119, 105)
ITEM_NAMES = {None: "빈손", "part": "함정 부품", "bone": "뼈 묶음", "soldier": "해골 병사"}


def font_path() -> str:
    """폰트를 배포하지 않고 로컬 한글 폰트를 사용한다."""
    override = os.environ.get("DUNGEON_FONT")
    if override:
        if not Path(override).is_file():
            raise OSError(f"DUNGEON_FONT 파일을 찾을 수 없습니다: {override}")
        return override
    candidates = (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/malgun.ttf",
        Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise OSError("한글 글꼴이 없습니다. DUNGEON_FONT에 한글 TTF/TTC 경로를 지정하세요.")


def box(x1, y1, x2, y2, color, filled=True):
    p.draw_rectangle(x1, y1, x2, y2, *color, filled=filled)


def line(x1, y1, x2, y2, color):
    p.draw_line(x1, y1, x2, y2, *color)


def diamond(x, y, half_width, half_height, color, outline=None):
    # pico2d의 기본 도형만 사용한다. 12x12 이하 한 화면 보드용이다.
    if color is not None:
        for offset in range(-half_height, half_height + 1):
            span = half_width * (1 - abs(offset) / half_height)
            line(x - span, y + offset, x + span, y + offset, color)
    if outline:
        points = ((x, y + half_height), (x + half_width, y),
                  (x, y - half_height), (x - half_width, y))
        for first, second in zip(points, points[1:] + points[:1]):
            line(*first, *second, outline)


class View:
    def __init__(self):
        path = font_path()
        self.fonts = {size: p.load_font(path, size) for size in (13, 16, 18, 22, 32)}

    def close(self):
        for font in self.fonts.values():
            p.TTF_CloseFont(font.font)
        self.fonts.clear()

    def text(self, x, y, value, size=18, color=INK):
        self.fonts[size].draw(x, y, str(value), color)

    def wrapped(self, x, y, value, width=300, size=16, color=MUTED):
        """UTF-8 실제 글꼴 폭을 기준으로 안내문을 줄바꿈한다."""
        import ctypes

        current = ""
        for character in value:
            measured = ctypes.c_int()
            p.TTF_SizeUTF8(self.fonts[size].font, (current + character).encode("utf-8"),
                          ctypes.byref(measured), None)
            if current and measured.value > width:
                self.text(x, y, current, size, color)
                current = ""
                y -= size + 9
            current += character
        if current:
            self.text(x, y, current, size, color)
        return y

    def item(self, kind, x, y):
        if kind == "part":
            box(x - 10, y - 6, x + 10, y + 10, GOLD)
            box(x - 4, y - 1, x + 4, y + 5, (75, 63, 44))
        elif kind == "bone":
            box(x - 12, y, x + 12, y + 4, INK)
            for end in (-12, 8):
                box(x + end, y - 3, x + end + 4, y + 7, INK)
        elif kind == "soldier":
            box(x - 9, y + 6, x + 9, y + 22, INK)
            box(x - 6, y - 10, x + 6, y + 5, (164, 172, 162))
            for eye in (-5, 3):
                box(x + eye, y + 13, x + eye + 2, y + 16, (33, 40, 43))
            line(x - 14, y - 8, x - 14, y + 18, GOLD)

    def draw(self, game, index, total):
        level, state = game.level, game.state
        box(0, 0, WIDTH, HEIGHT, (19, 27, 32))
        box(32, 790, 1248, 792, (65, 76, 77))
        self.text(42, 851, "용사가 지나간 자리", 32)
        self.text(44, 812, "던전 복구 작업실", 16, MUTED)
        self.text(927, 850, f"입문 {index + 1:02d} / {total:02d}", 22, GOLD)
        self.text(927, 815, "기초 프로토타입  0.1", 16, MUTED)

        half_width = int(760 / (level.width + level.height))
        half_height = half_width // 2
        origin_x = 445 - (level.width - level.height) * half_width / 2
        origin_y = 708
        for depth in range(level.width + level.height - 1):
            for y in range(level.height):
                x = depth - y
                if not 0 <= x < level.width:
                    continue
                position = (x, y)
                sx, sy = origin_x + (x - y) * half_width, origin_y - depth * half_height
                if position in level.walls:
                    diamond(sx, sy - 7, half_width - 1, half_height, (36, 46, 53))
                    diamond(sx, sy + 7, half_width - 1, half_height, (61, 74, 81), (80, 93, 97))
                    continue
                color = (59, 75, 76) if (x + y) % 2 else (64, 80, 80)
                if position in level.traps:
                    color = (123, 60, 54) if state.active else (105, 88, 57)
                elif position == level.exit:
                    color = (48, 99, 88)
                elif position in level.posts:
                    color = (76, 74, 101)
                diamond(sx, sy, half_width - 1, half_height - 1, color, (35, 47, 51))

                if position in level.traps:
                    for offset in (-12, 0, 12):
                        line(sx + offset - 4, sy - 4, sx + offset, sy + 5, RED if state.active else GOLD)
                        line(sx + offset, sy + 5, sx + offset + 4, sy - 4, RED if state.active else GOLD)
                    label = "가동" if state.active else "설치" if position in state.installed else "파손"
                    self.text(sx - 13, sy - 11, label, 13, INK)
                elif position in level.levers:
                    box(sx - 12, sy - 5, sx + 12, sy + 1, (125, 126, 104))
                    line(sx, sy, sx + (10 if state.active else -10), sy + 19, GOLD)
                    self.text(sx - 13, sy - 12, "레버", 13)
                elif position in level.benches:
                    box(sx - 20, sy - 3, sx + 20, sy + 8, (135, 99, 65))
                    self.text(sx - 20, sy - 11, f"조립 {state.bench_bones.get(position, 0)}/2", 13)
                elif position in level.posts:
                    self.text(sx - 13, sy - 9, "초소", 13)
                elif position == level.exit:
                    self.text(sx - 13, sy, "출구", 13, TEAL)

                if position in state.items:
                    self.item(state.items[position], sx, sy + 7)
                if position in state.soldiers:
                    self.item("soldier", sx + 10, sy + 8)
                if position == state.player:
                    diamond(sx, sy - 1, half_width - 4, half_height - 3, None, TEAL)
                    box(sx - 10, sy + 10, sx + 10, sy + 31, (50, 139, 132))
                    box(sx - 7, sy + 27, sx + 7, sy + 40, TEAL)
                    box(sx - 4, sy + 29, sx + 4, sy + 33, (30, 52, 54))
                    if state.carrying:
                        self.item(state.carrying, sx + 19, sy + 37)

        # 정보 패널은 보드 영역과 분리해 가림을 방지한다.
        box(894, 149, 1248, 768, (28, 39, 44))
        self.text(918, 737, level.title, 22)
        self.wrapped(918, 699, level.hint)
        self.text(918, 603, "복구 현황", 18, GOLD)
        self.text(918, 567, f"함정 설치  {len(state.installed)} / {len(level.traps)}")
        active_label = "완료" if state.active else "대기" if level.traps else "해당 없음"
        self.text(918, 533, f"함정 가동  {active_label}", 18, TEAL if state.active else INK)
        self.text(918, 499, f"병사 배치  {len(state.soldiers)} / {len(level.posts)}")
        self.text(918, 453, f"운반 중    {ITEM_NAMES[state.carrying]}", 18, GOLD)
        self.text(918, 418, f"행동 {state.moves}회    되돌리기 {len(game.history)}회", 16, MUTED)
        self.text(918, 375, "목표", 18, GOLD)
        self.wrapped(918, 343, "복구를 마친 뒤 빈손으로 출구에 돌아오세요.")
        self.text(918, 273, "현재 칸", 16, MUTED)
        self.wrapped(918, 242, game.context_action(), size=18, color=TEAL)
        if state.cleared:
            box(908, 159, 1233, 205, (46, 96, 81))
            label = "Enter  다음 방" if index + 1 < total else "Enter  처음부터 다시"
            self.text(924, 183, label, 18)

        self.text(44, 266, "이동 방향", 16, GOLD)
        self.text(44, 236, "W / 위: 오른쪽 위     D / 오른쪽: 오른쪽 아래", 16, MUTED)
        self.text(44, 210, "A / 왼쪽: 왼쪽 위     S / 아래: 왼쪽 아래", 16, MUTED)
        self.text(44, 174, "물건·장치와 같은 칸에서 E를 누르세요.", 18)
        box(32, 77, 1248, 133, (41, 55, 58))
        self.text(51, 106, "복구 완료!" if state.cleared else game.message, 18, TEAL if state.cleared else INK)
        self.text(42, 42, "WASD / 방향키  이동     E / Space  상호작용     Q  내려놓기     Z / Backspace  되돌리기     R  재시작     Esc  종료", 16, MUTED)


def run(levels, index=0, smoke_frames=None):
    # 글꼴 오류는 SDL 창을 열기 전에 보고한다.
    font_path()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        if not p.window or not p.renderer:
            raise RuntimeError("SDL 게임 창 또는 렌더러를 만들 수 없습니다.")
        view = View()
        game = Game(levels[index])
        actions = {
            p.SDLK_UP: "up", p.SDLK_w: "up", p.SDLK_DOWN: "down", p.SDLK_s: "down",
            p.SDLK_LEFT: "left", p.SDLK_a: "left", p.SDLK_RIGHT: "right", p.SDLK_d: "right",
            p.SDLK_e: "interact", p.SDLK_SPACE: "interact", p.SDLK_q: "drop",
        }
        running, frames = True, 0
        while running:
            for event in p.get_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_KEYDOWN:
                    if event.key == p.SDLK_ESCAPE:
                        running = False
                    elif event.key in (p.SDLK_z, p.SDLK_BACKSPACE):
                        game.undo()
                    elif event.key == p.SDLK_r:
                        game.restart()
                    elif event.key == p.SDLK_RETURN and game.state.cleared:
                        index = (index + 1) % len(levels)
                        game = Game(levels[index])
                    elif event.key in actions:
                        game.act(actions[event.key])
            view.draw(game, index, len(levels))
            p.update_canvas()
            p.SDL_SetWindowTitle(p.window, "용사가 지나간 자리 — 기초 프로토타입".encode("utf-8"))
            frames += 1
            if smoke_frames is not None and frames >= smoke_frames:
                running = False
    finally:
        if view:
            view.close()
        p.close_canvas()
