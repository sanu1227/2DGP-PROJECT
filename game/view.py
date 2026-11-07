"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

import os
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.model import Game
from game.art import Art
from game.projection import BoardProjection
from game.masonry import draw_wall
from game.devices_view import draw_belt, draw_plate
from game.motion import GridMotion
from game.scenery import draw_scars, draw_tinted, floor_style, wall_style

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
        self.motion = GridMotion()

    def player_position(self, fallback, now):
        return self.motion.position(fallback, now)

    def move_player(self, previous, destination, action):
        """논리 이동을 즉시 처리하되 표시 경로는 실제 통과한 칸 순서를 지킨다."""
        self.motion.start(previous, destination, perf_counter())
        self.facing = FACING[action]

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

    def gate(self, sx, sy, scale, status):
        """녹슨 문틀과 창살. 열린 문은 통행 공간을 비워 둔다."""
        color = TEAL if status == "open" else GOLD if status == "held" else RED
        left, right, height = sx - 80 * scale, sx + 80 * scale, 110 * scale
        rust, edge = (104, 80, 53), (158, 132, 89)
        for x, base in ((left, sy), (right, sy)):
            box(x - 4, base - 2, x + 4, base + height - 8 * scale, (49, 44, 37))
            box(x - 2, base, x + 2, base + height - 10 * scale, rust)
            line(x - 2, base, x - 2, base + height - 10 * scale, edge)
            box(x - 2, base + height - 15 * scale, x + 2, base + height - 8 * scale, color)
        for offset in range(-2, 3):
            line(left, sy + height - 8 * scale + offset, right, sy + height - 8 * scale + offset, rust)
        line(left, sy + height - 8 * scale + 3, right, sy + height - 8 * scale + 3, edge)
        if status != "open":
            for fraction in (0.2, 0.4, 0.6, 0.8):
                x = left + (right - left) * fraction
                y = sy
                line(x, y, x, y + height - 8 * scale, rust)
                line(x + 1, y, x + 1, y + height - 8 * scale, edge)

    def board(self, game):
        level, state = game.level, game.state
        projection = BoardProjection(level.width, level.height)
        scale = projection.cell_width / self.art.manifest["coordinates"]["tile_footprint"]["width"]
        screen = projection.screen

        exit_ready = (state.installed == level.traps and (not level.traps or state.active)
                      and state.soldiers == level.posts and state.carrying is None)
        objects, labels, walls = [], [], {}
        device_floor = (level.traps | level.posts | level.plates | level.gates.keys()
                        | level.chutes.keys() | set(level.chutes.values()) | level.belts.keys()
                        | level.benches | level.levers | {level.exit})
        for y in range(level.height):
            for x in range(level.width):
                depth = y
                pos = (x, y)
                sx, sy = screen(pos)
                near_trap = any(abs(x - tx) + abs(y - ty) <= 1 for tx, ty in level.traps)
                tile, tint = floor_style(pos, near_trap)
                if pos in level.walls:
                    wall_sprite, wall_tint = wall_style(pos)
                    objects.append((depth, 0, wall_sprite, sx, sy))
                    walls[(sx, sy)] = (pos, wall_tint)
                elif pos in level.traps:
                    tile = "trap_installed" if pos in state.installed else "trap_broken"
                    tint = None
                    if state.active:
                        objects.append((depth, 0, "trap_active", sx, sy))
                    labels.append((pos, "가동" if state.active else "설치" if pos in state.installed else "파손"))
                elif pos in level.posts:
                    tile = "post_empty"
                    tint = None
                    labels.append((pos, "배치" if pos in state.soldiers else "초소"))
                elif pos == level.exit:
                    tile = "exit_ready" if exit_ready else "exit_closed"
                    tint = None
                    labels.append((pos, "출구"))
                self.art.ground(tile, sx, sy, projection.cell_width, projection.cell_height, tint or (255, 255, 255))
                if pos not in level.walls and pos not in device_floor:
                    draw_scars(pos, sx, sy, scale, near_trap, projection=projection)

                if pos in level.belts:
                    direction = level.belts[pos]
                    objects.append((depth, 0.5, f"belt_{direction}", sx, sy))
                    labels.append((pos, "벨트 " + {"up": "↑", "right": "→", "down": "↓", "left": "←"}[direction]))
                if pos in level.chutes:
                    objects.append((depth, 1, "chute_inlet", sx, sy))
                    labels.append((pos, f"{level.device_labels[pos]} 투입"))
                elif pos in level.chutes.values():
                    objects.append((depth, 0.5, "chute_outlet", sx, sy))
                    if pos not in level.plates:
                        labels.append((pos, f"{level.device_labels[pos]} 배출"))
                if pos in level.plates:
                    pressed = game.plate_pressed(pos)
                    objects.append((depth, 1, "plate_down" if pressed else "plate_up", sx, sy))
                    labels.append((pos, f"{level.device_labels[pos]} 발판"))
                elif pos in level.gates:
                    status = game.gate_status(pos)
                    objects.append((depth, 1, f"gate_{status}", sx, sy))
                    labels.append((pos, f"{level.device_labels[pos]} " + {"open": "열림", "held": "대기", "closed": "닫힘"}[status]))
                elif pos in level.levers:
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
        box(*projection.bounds(state.player, inset=3), TEAL, filled=False)
        now = perf_counter()
        player = self.player_position(state.player, now)
        facing = FACING[self.motion.direction] if self.motion.moving else self.facing
        px, py = screen(player)
        # 발 위치는 항상 격자 중심에 둔다. 도착 장치에 따라 옆으로 튀지 않는다.
        objects.append((player[1], 3, "player", px, py))
        for _, _, sprite, sx, sy in sorted(objects, key=lambda obj: obj[:2]):
            if sprite.startswith("belt_"):
                direction = sprite.removeprefix("belt_")
                draw_belt(self.art, direction, sx, sy, projection.cell_width, projection.cell_height)
                continue
            if sprite in ("plate_up", "plate_down"):
                draw_plate(self.art, sprite == "plate_down", sx, sy, projection.cell_width, projection.cell_height)
                continue
            if sprite.startswith("gate_"):
                self.gate(sx, sy, scale, sprite.removeprefix("gate_"))
                continue
            if sprite != "player":
                if sprite == "wall_low":
                    pos, tint = walls[(sx, sy)]
                    draw_wall(self.art, pos, sx, sy, projection.cell_width, projection.cell_height, tint)
                elif sprite == "rubble":
                    draw_tinted(self.art, sprite, sx, sy, scale, walls[(sx, sy)][1])
                else:
                    self.art.draw(sprite, sx, sy, scale)
                continue
            pose = "idle"
            if self.motion.moving:
                pose = "walk_a" if self.motion.phase < 0.5 else "walk_b"
            if state.carrying:
                pose = "carry"
            # 뒤를 볼 때 운반물은 몸 뒤에, 앞을 볼 때는 손 위에 합성한다.
            offset_x = 12 if facing in ("ne", "se") else -12
            if state.carrying and facing in ("ne", "nw"):
                self.item(state.carrying, sx + offset_x, sy + 32, scale * 0.65)
            self.art.draw(f"worker_{facing}_{pose}", sx, sy, scale)
            if state.carrying and facing in ("se", "sw"):
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
        self.text(32, 857, "용사가 지나간 자리", 32)
        self.text(450, 857, level.title, 22)
        self.text(1090, 857, f"단계 {index + 1:02d} / {total:02d}", 22, GOLD)
        self.text(34, 820, f"{level.width}×{level.height}  정면 3/4 시점 · 프로토타입 0.5", 16, MUTED)
        self.wrapped(450, 825, level.hint, width=790, size=16)

        self.board(game)

        # 정보는 위·아래 띠에 모아 넓어진 지도 전체를 한 화면에 유지한다.
        box(32, 750, 1248, 788, (28, 39, 44))
        self.text(48, 769, f"함정 설치 {len(state.installed)}/{len(level.traps)}", 18)
        active_label = "완료" if state.active else "대기" if level.traps else "해당 없음"
        self.text(230, 769, f"가동 {active_label}", 18, TEAL if state.active else INK)
        self.text(420, 769, f"병사 배치 {len(state.soldiers)}/{len(level.posts)}", 18)
        self.text(620, 769, f"운반: {ITEM_NAMES[state.carrying]}", 18, GOLD)
        if state.carrying:
            self.item(state.carrying, 820, 757, 0.19)
        self.text(936, 769, f"행동 {state.moves} · 되돌리기 {len(game.history)}", 16, MUTED)

        box(32, 73, 1248, 132, (41, 55, 58))
        self.text(48, 113, game.context_action(), 18, TEAL)
        self.text(48, 88, game.message, 16, INK)
        if state.cleared:
            box(932, 82, 1236, 123, (46, 96, 81))
            label = "Enter  다음 방" if index + 1 < total else "Enter  처음부터 다시"
            self.text(949, 103, label, 18)
        else:
            self.text(918, 104, "모든 복구 후 빈손으로 출구 복귀", 16, MUTED)

        self.text(34, 51, "화면 기준 이동  W / ↑  위    A / ←  왼쪽    S / ↓  아래    D / →  오른쪽       무너진 벽·잔해는 통행 불가", 13, MUTED)
        self.text(34, 25, "E / Space  상호작용    Q  내려놓기    B  대기    Z / Backspace  되돌리기    R  재시작    Enter  다음 방(완료 후)    Esc  종료", 16, MUTED)


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
            p.SDLK_b: "wait",
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
                            view.motion.reset()
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
