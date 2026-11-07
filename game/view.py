"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

import os
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.model import Game
from game.art import Art

WIDTH, HEIGHT = 1280, 900
INK = (226, 230, 219)
MUTED = (158, 169, 166)
GOLD = (227, 187, 104)
TEAL = (104, 206, 184)
RED = (232, 119, 105)
ITEM_NAMES = {None: "빈손", "part": "함정 부품", "bone": "뼈 묶음", "soldier": "해골 병사"}
ITEM_SPRITES = {"part": "part", "bone": "bone_bundle", "soldier": "soldier_carried"}
FACING = {"up": "ne", "right": "se", "down": "sw", "left": "nw"}


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
    # 에셋 위의 선택 칸 윤곽에도 사용하는 2:1 마름모.
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
        self.fonts = {}
        self.art = None
        self.reset_player()
        try:
            path = font_path()
            for size in (13, 16, 18, 22, 32):
                self.fonts[size] = p.load_font(path, size)
            self.art = Art()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.art:
            self.art.close()
            self.art = None
        for font in self.fonts.values():
            p.TTF_CloseFont(font.font)
        self.fonts.clear()

    def reset_player(self):
        self.facing = "se"
        self.motion = None

    def player_position(self, fallback, now):
        if self.motion is None:
            return fallback
        start, target, began = self.motion
        progress = min(1.0, (now - began) / 0.18)
        if progress >= 1:
            self.motion = None
            return fallback
        return tuple(a + (b - a) * progress for a, b in zip(start, target))

    def move_player(self, previous, destination, action):
        """논리 이동은 즉시 완료하고 표시 위치만 짧게 보간한다."""
        now = perf_counter()
        start = self.player_position(previous, now)
        self.facing = FACING[action]
        self.motion = (start, destination, now)

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

    def item(self, kind, x, y, scale):
        self.art.draw(ITEM_SPRITES[kind], x, y, scale)

    def board(self, game):
        level, state = game.level, game.state
        half_width = int(760 / (level.width + level.height))
        half_height = half_width / 2
        scale = half_width * 2 / self.art.manifest["coordinates"]["tile_footprint"]["width"]
        origin_x = 445 - (level.width - level.height) * half_width / 2

        def screen(position):
            x, y = position
            return origin_x + (x - y) * half_width, 708 - (x + y) * half_height

        exit_ready = (state.installed == level.traps and (not level.traps or state.active)
                      and state.soldiers == level.posts and state.carrying is None)
        objects, labels = [], []
        for depth in range(level.width + level.height - 1):
            for y in range(level.height):
                x = depth - y
                if not 0 <= x < level.width:
                    continue
                pos = (x, y)
                sx, sy = screen(pos)
                tile = ("floor_plain", "floor_cracked", "floor_plain", "floor_moss")[(x + y * 3) % 4]
                if pos in level.walls:
                    objects.append((depth, 0, "wall_low", sx, sy))
                elif pos in level.traps:
                    tile = "trap_installed" if pos in state.installed else "trap_broken"
                    if state.active:
                        objects.append((depth, 0, "trap_active", sx, sy))
                    labels.append((pos, "가동" if state.active else "설치" if pos in state.installed else "파손"))
                elif pos in level.posts:
                    tile = "post_empty"
                    labels.append((pos, "배치" if pos in state.soldiers else "초소"))
                elif pos == level.exit:
                    tile = "exit_ready" if exit_ready else "exit_closed"
                    labels.append((pos, "출구"))
                self.art.draw(tile, sx, sy, scale)

                if pos in level.levers:
                    objects.append((depth, 1, "lever_on" if state.active else "lever_off", sx, sy))
                    labels.append((pos, "레버"))
                elif pos in level.benches:
                    stored = state.bench_bones.get(pos, 0)
                    objects.append((depth, 1, "bench_one_bone" if stored else "bench_empty", sx, sy))
                    labels.append((pos, f"조립 {stored}/2"))
                if pos in state.items:
                    objects.append((depth, 2, ITEM_SPRITES[state.items[pos]], sx, sy))
                if pos in state.soldiers:
                    objects.append((depth, 2, "soldier_deployed", sx + 10, sy))

        # 바닥 전체를 먼저 그려 앞 칸의 바닥이 캐릭터 다리를 덮지 않게 한다.
        target_x, target_y = screen(state.player)
        diamond(target_x, target_y, half_width - 3, int(half_height) - 2, None, TEAL)
        now = perf_counter()
        player = self.player_position(state.player, now)
        px, py = screen(player)
        # 같은 칸의 작업대나 배치한 병사와 구별되도록 약간 앞쪽에 선다.
        if state.player in level.benches | level.levers | state.soldiers:
            px -= 9
            py -= 7
        objects.append((sum(player), 3, "player", px, py))
        for _, _, sprite, sx, sy in sorted(objects, key=lambda obj: obj[:2]):
            if sprite != "player":
                self.art.draw(sprite, sx, sy, scale)
                continue
            pose = "idle"
            if self.motion:
                pose = "walk_a" if now - self.motion[2] < 0.09 else "walk_b"
            if state.carrying:
                pose = "carry"
            # 뒤를 볼 때 운반물은 몸 뒤에, 앞을 볼 때는 손 위에 합성한다.
            offset_x = 12 if self.facing in ("ne", "se") else -12
            if state.carrying and self.facing in ("ne", "nw"):
                self.item(state.carrying, sx + offset_x, sy + 32, scale * 0.65)
            self.art.draw(f"worker_{self.facing}_{pose}", sx, sy, scale)
            if state.carrying and self.facing in ("se", "sw"):
                self.item(state.carrying, sx + offset_x, sy + 24, scale * 0.65)

        # 상태 문구를 바닥 아트와 함께 유지해 색이나 작은 그림에만 의존하지 않는다.
        for pos, label in labels:
            sx, sy = screen(pos)
            width = len(label) * 13 + 8
            box(sx - width / 2, sy - 24, sx + width / 2, sy - 7, (24, 35, 40))
            self.text(sx - width / 2 + 4, sy - 16, label, 13, TEAL if pos == level.exit and exit_ready else INK)

    def draw(self, game, index, total):
        level, state = game.level, game.state
        box(0, 0, WIDTH, HEIGHT, (19, 27, 32))
        box(32, 790, 1248, 792, (65, 76, 77))
        self.text(42, 851, "용사가 지나간 자리", 32)
        self.text(44, 812, "던전 복구 작업실", 16, MUTED)
        self.text(927, 850, f"입문 {index + 1:02d} / {total:02d}", 22, GOLD)
        self.text(927, 815, "프로토타입  0.2", 16, MUTED)

        self.board(game)

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
        if state.carrying:
            self.item(state.carrying, 1214, 449, 0.28)
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
                        view.reset_player()
                    elif event.key == p.SDLK_r:
                        game.restart()
                        view.reset_player()
                    elif event.key == p.SDLK_RETURN and game.state.cleared:
                        index = (index + 1) % len(levels)
                        game = Game(levels[index])
                        view.reset_player()
                    elif event.key in actions:
                        action = actions[event.key]
                        previous = game.state.player
                        changed = game.act(action)
                        if action in FACING and changed:
                            view.move_player(previous, game.state.player, action)
                        elif changed:
                            # 도착 직후 상호작용하면 그 칸에 바로 정렬한다.
                            view.motion = None
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
