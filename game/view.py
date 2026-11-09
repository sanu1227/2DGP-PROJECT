"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

import os
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.model import Game
from game.art import Art
from game.scenery import draw_scars, draw_tinted, floor_style, wall_style
from game.navigation import ClickNavigator, IsoBoard, find_path
from game.themes import boundary_walls, low_wall_sprite, scene_for, themed_floor
from game.layout import WIDTH, HEIGHT, BOARD_BOTTOM, BOARD_TOP

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
        self.navigation = ClickNavigator()
        self.mouse_position = None
        self.show_coordinates = False
        self.hit_regions = []
        self.hit_masks = {}
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

    def pick_cell(self, game, x, y):
        """UI는 제외하고 앞에 그려진 물체부터 검사한 뒤 바닥 칸을 고른다."""
        if not BOARD_BOTTOM < y < BOARD_TOP:
            return None
        for pos, (left, bottom, right, top) in reversed(self.hit_regions):
            if left <= x < right and bottom <= y < top:
                mask = self.hit_masks.get((pos, (left, bottom, right, top)))
                if mask:
                    sprite, sx, sy, scale, flip = mask
                    if not self.art.hit_test(sprite, sx, sy, scale, (x, y), flip):
                        continue
                return pos
        return IsoBoard(game.level.width, game.level.height).pick(x, y)

    def sprite_hit_region(self, pos, sprite, sx, sy, scale, flip=False):
        region = (pos, self.art.bounds(sprite, sx, sy, scale, flip))
        self.hit_regions.append(region)
        self.hit_masks[region] = (sprite, sx, sy, scale, flip)

    def navigation_overlay(self, game, projection):
        target, path = self.navigation.target, self.navigation.path
        color = GOLD
        if not self.navigation.active:
            target = self.pick_cell(game, *self.mouse_position) if self.mouse_position else None
            path = find_path(game, target) if target is not None else None
            color = TEAL if path is not None else RED
        if target is None:
            return
        previous = projection.screen(game.state.player)
        for pos in path or []:
            point = projection.screen(pos)
            line(*previous, *point, color)
            diamond(*point, 3, 2, color)
            previous = point
        diamond(*projection.screen(target), projection.half_width - 5,
                int(projection.half_height) - 3, None, color)

    def gate(self, sx, sy, scale, status):
        """녹슨 문틀과 창살. 열린 문은 통행 공간을 비워 둔다."""
        color = TEAL if status == "open" else GOLD if status == "held" else RED
        left, right, height = sx - 80 * scale, sx + 80 * scale, 110 * scale
        rust, edge = (104, 80, 53), (158, 132, 89)
        for x, base in ((left, sy + 8 * scale), (right, sy - 8 * scale)):
            box(x - 4, base - 2, x + 4, base + height - 8 * scale, (49, 44, 37))
            box(x - 2, base, x + 2, base + height - 10 * scale, rust)
            line(x - 2, base, x - 2, base + height - 10 * scale, edge)
            box(x - 2, base + height - 15 * scale, x + 2, base + height - 8 * scale, color)
        for offset in range(-2, 3):
            line(left, sy + height + offset, right, sy + height - 16 * scale + offset, rust)
        line(left, sy + height + 3, right, sy + height - 16 * scale + 3, edge)
        if status != "open":
            for fraction in (0.2, 0.4, 0.6, 0.8):
                x = left + (right - left) * fraction
                y = sy + (8 - 16 * fraction) * scale
                line(x, y, x, y + height - 8 * scale, rust)
                line(x + 1, y, x + 1, y + height - 8 * scale, edge)

    def board(self, game):
        level, state = game.level, game.state
        scene = scene_for(level)
        if scene:
            for pack in scene["packs"]:
                self.art.load_theme(pack)
            self.art.load_walls(scene["packs"][0])
        # 기존 사선 비율로 바닥과 높은 외곽 벽을 함께 화면에 넣는다.
        projection = IsoBoard(level.width, level.height)
        half_width, half_height = projection.half_width, projection.half_height
        scale = half_width * 2 / self.art.manifest["coordinates"]["tile_footprint"]["width"]
        screen = projection.screen
        self.hit_regions.clear()
        self.hit_masks.clear()

        exit_ready = (state.installed == level.traps and (not level.traps or state.active)
                      and state.soldiers == level.posts and state.carrying is None)
        objects, labels, wall_tints = [], [], {}
        decor_draws = {}
        device_floor = (level.traps | level.posts | level.plates | level.gates.keys()
                        | level.chutes.keys() | set(level.chutes.values()) | level.belts.keys()
                        | level.benches | level.levers | {level.exit})
        for depth in range(level.width + level.height - 1):
            for y in range(level.height):
                x = depth - y
                if not 0 <= x < level.width:
                    continue
                pos = (x, y)
                sx, sy = screen(pos)
                near_trap = any(abs(x - tx) + abs(y - ty) <= 1 for tx, ty in level.traps)
                tile, tint = themed_floor(scene, pos, near_trap) if scene else floor_style(pos, near_trap)
                if pos in level.walls:
                    wall_sprite, wall_tint = wall_style(pos)
                    low_wall = low_wall_sprite(scene, pos, level)
                    if wall_sprite == "wall_low":
                        wall_sprite = low_wall
                    faces = boundary_walls(scene, pos, level) if scene else []
                    if scene:
                        wall_tint = tuple(scene["wall_tint"])
                    if faces:
                        for face in faces:
                            objects.append((depth, 0, face, sx, sy))
                        # 벽면은 칸 뒤쪽에만 서 있으므로 막힌 칸 전체를 석축으로 채운다.
                        # 일반 바닥만 남기면 외곽 벽 바로 앞도 걸을 수 있는 것처럼 보인다.
                        objects.append((depth, 0.1, low_wall, sx, sy))
                        wall_tints[(sx, sy)] = tuple(round(153 + channel * 0.4) for channel in wall_tint)
                    elif wall_sprite == "rubble":
                        tile, tint = wall_sprite, wall_tint
                    else:
                        objects.append((depth, 0, wall_sprite, sx, sy))
                        wall_tints[(sx, sy)] = wall_tint
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
                if tint:
                    draw_tinted(self.art, tile, sx, sy, scale, tint)
                else:
                    self.art.draw(tile, sx, sy, scale)
                if pos not in level.walls and pos not in device_floor and (not scene or near_trap):
                    draw_scars(pos, sx, sy, scale, near_trap)

                if pos in level.belts:
                    direction = level.belts[pos]
                    objects.append((depth, 0.5, f"belt_{direction}", sx, sy))
                    labels.append((pos, "벨트 " + {"up": "↗", "right": "↘", "down": "↙", "left": "↖"}[direction]))
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

        if scene:
            for mount in scene.get("wall_mounts", ()):
                pos = tuple(mount["cell"])
                sx, sy = screen(pos)
                sx += (-56 if pos[0] == 0 else 56) * scale
                sy += mount.get("height", 150) * scale
                sprite = mount["sprite"]
                objects.append((sum(pos), 0.25, sprite, sx, sy))
                decor_draws[(sprite, sx, sy)] = scale
            for decoration in scene["decorations"]:
                pos = tuple(decoration["cell"])
                sx, sy = screen(pos)
                sy += 8 * scale  # 낮은 벽/잔해 위에 올려 통행 불가 영역임을 유지한다.
                sprite = decoration["sprite"]
                objects.append((sum(pos), 1.5, sprite, sx, sy))
                decor_draws[(sprite, sx, sy)] = scale * decoration["scale"]

        # 바닥 전체를 먼저 그려 앞 칸의 바닥이 캐릭터 다리를 덮지 않게 한다.
        target_x, target_y = screen(state.player)
        diamond(target_x, target_y, half_width - 3, int(half_height) - 2, None, TEAL)
        now = perf_counter()
        player = self.player_position(state.player, now)
        px, py = screen(player)
        # 같은 칸의 작업대나 배치한 병사와 구별되도록 약간 앞쪽에 선다.
        if state.player in level.benches | level.levers | state.soldiers | level.plates | level.gates.keys() | level.chutes.keys():
            px -= 9
            py -= 7
        objects.append((sum(player), 3, "player", px, py))
        for _, _, sprite, sx, sy in sorted(objects, key=lambda obj: obj[:2]):
            pos = state.player if sprite == "player" else projection.pick(sx, sy)
            decor_scale = decor_draws.get((sprite, sx, sy))
            if decor_scale is not None:
                self.art.draw(sprite, sx, sy, decor_scale)
                # 장식의 위쪽 그림이 뒤의 이동 칸/장치 클릭을 가로채지 않는다.
                continue
            if sprite.startswith("belt_"):
                direction = sprite.removeprefix("belt_")
                name = "conveyor_ne" if direction in ("up", "left") else "conveyor_se"
                flip = direction in ("left", "down")
                self.art.draw(name, sx, sy, scale, flip=flip)
                self.sprite_hit_region(pos, name, sx, sy, scale, flip)
                continue
            if sprite.startswith("gate_"):
                self.gate(sx, sy, scale, sprite.removeprefix("gate_"))
                self.hit_regions.append((pos, (sx - 84 * scale, sy - 10 * scale,
                                              sx + 84 * scale, sy + 114 * scale)))
                continue
            if sprite != "player":
                if (sx, sy) in wall_tints and (sprite.startswith("wall_low") or "_wall_" in sprite):
                    draw_tinted(self.art, sprite, sx, sy, scale, wall_tints[(sx, sy)])
                else:
                    self.art.draw(sprite, sx, sy, scale)
                self.sprite_hit_region(pos, sprite, sx, sy, scale)
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
            self.sprite_hit_region(pos, f"worker_{self.facing}_{pose}", sx, sy, scale)
            if state.carrying and self.facing in ("se", "sw"):
                self.item(state.carrying, sx + offset_x, sy + 24, scale * 0.65)

        # 상태 문구를 바닥 아트와 함께 유지해 색이나 작은 그림에만 의존하지 않는다.
        for pos, label in labels:
            sx, sy = screen(pos)
            width = len(label) * 16 + 10
            box(sx - width / 2, sy - 28, sx + width / 2, sy - 6, (24, 35, 40))
            self.text(sx - width / 2 + 5, sy - 17, label, 16, TEAL if pos == level.exit and exit_ready else INK)
            self.hit_regions.append((pos, (sx - width / 2, sy - 28, sx + width / 2, sy - 6)))
        self.navigation_overlay(game, projection)
        if self.show_coordinates:
            self.coordinate_overlay(level, projection)

    def coordinate_overlay(self, level, projection):
        """벽과 물체 위에도 데이터의 (열, 행) 좌표를 표시한다."""
        for y in range(level.height):
            for x in range(level.width):
                sx, sy = projection.screen((x, y))
                label = f"({x},{y})"
                width = len(label) * 8 + 6
                box(sx - width / 2, sy, sx + width / 2, sy + 18, (19, 27, 32))
                self.text(sx - width / 2 + 3, sy + 9, label, 13, GOLD)

    def draw(self, game, index, total):
        level, state = game.level, game.state
        scene = scene_for(level)
        background = tuple(scene["background"]) if scene else (19, 27, 32)
        accent = tuple(scene["accent"]) if scene else MUTED
        box(0, 0, WIDTH, HEIGHT, background)
        self.text(32, HEIGHT - 36, "용사가 지나간 자리", 32)
        self.text(450, HEIGHT - 36, level.title, 22)
        self.text(WIDTH - 190, HEIGHT - 36, f"단계 {index + 1:02d} / {total:02d}", 22, GOLD)
        atmosphere = scene["name"] if scene else "던전 복구 작업실"
        self.text(34, HEIGHT - 72, f"{level.width}×{level.height}  {atmosphere}", 16, accent)
        self.wrapped(450, HEIGHT - 69, level.hint, width=WIDTH - 490, size=16)

        self.board(game)

        # 정보는 위·아래 띠에 모아 넓어진 지도 전체를 한 화면에 유지한다.
        box(32, BOARD_TOP, WIDTH - 32, BOARD_TOP + 34, (28, 39, 44))
        self.text(48, BOARD_TOP + 17, f"함정 설치 {len(state.installed)}/{len(level.traps)}", 18)
        active_label = "완료" if state.active else "대기" if level.traps else "해당 없음"
        self.text(260, BOARD_TOP + 17, f"가동 {active_label}", 18, TEAL if state.active else INK)
        self.text(470, BOARD_TOP + 17, f"병사 배치 {len(state.soldiers)}/{len(level.posts)}", 18)
        self.text(740, BOARD_TOP + 17, f"운반: {ITEM_NAMES[state.carrying]}", 18, GOLD)
        if state.carrying:
            self.item(state.carrying, 940, BOARD_TOP + 5, 0.19)
        self.text(WIDTH - 340, BOARD_TOP + 17, f"행동 {state.moves} · 되돌리기 {len(game.history)}", 16, MUTED)

        box(32, 48, WIDTH - 32, BOARD_BOTTOM, (41, 55, 58))
        self.text(48, 80, game.context_action(), 18, TEAL)
        self.text(48, 59, game.message, 16, INK)
        if state.cleared:
            box(WIDTH - 340, 53, WIDTH - 44, 89, (46, 96, 81))
            label = "Enter  다음 방" if index + 1 < total else "Enter  처음부터 다시"
            self.text(WIDTH - 323, 71, label, 18)
        else:
            status = f"자동 이동 · {len(self.navigation.path)}칸 남음" if self.navigation.active else "모든 복구 후 빈손으로 출구 복귀"
            self.text(WIDTH - 362, 71, status, 16, MUTED)

        self.text(34, 32, "좌클릭  이동    우클릭  취소    WASD / 방향키  이동    개발용 1~6 방 이동 · F2 좌표    (x,y): x 오른쪽 아래 / y 왼쪽 아래", 13, MUTED)
        self.text(34, 12, "E / Space  상호작용    Q  내려놓기    B  대기    Z / Backspace  되돌리기    R  재시작    Enter  다음 방(완료 후)    Esc  종료", 13, MUTED)


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
        stage_keys = {
            p.SDLK_1: 0, p.SDLK_2: 1, p.SDLK_3: 2,
            p.SDLK_4: 3, p.SDLK_5: 4, p.SDLK_6: 5,
        }
        running, frames = True, 0
        while running:
            for event in p.get_events():
                if event.type == p.SDL_QUIT:
                    running = False
                elif event.type == p.SDL_MOUSEMOTION:
                    view.mouse_position = (event.x, HEIGHT - 1 - event.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN:
                    view.mouse_position = (event.x, HEIGHT - 1 - event.y)
                    if event.button == p.SDL_BUTTON_RIGHT:
                        if view.navigation.active:
                            game.message = "자동 이동을 취소했습니다."
                        view.navigation.cancel()
                    elif event.button == p.SDL_BUTTON_LEFT:
                        target = view.pick_cell(game, *view.mouse_position)
                        if target is not None:
                            now = perf_counter()
                            ready_at = view.motion[2] + 0.18 if view.motion else now
                            view.navigation.start(game, target, now, ready_at=ready_at)
                elif event.type == p.SDL_KEYDOWN:
                    view.navigation.cancel()
                    if event.key == p.SDLK_ESCAPE:
                        running = False
                    elif event.key == p.SDLK_F2:
                        view.show_coordinates = not view.show_coordinates
                    elif event.key in stage_keys and stage_keys[event.key] < len(levels):
                        index = stage_keys[event.key]
                        game = Game(levels[index])
                        view.reset_player()
                        view.hit_regions.clear()
                        view.hit_masks.clear()
                        view.mouse_position = None
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
            # 이미 보간 중인 한 칸이 끝난 뒤에만 다음 자동 이동을 실행한다.
            now = perf_counter()
            if running and (view.motion is None or now >= view.motion[2] + 0.18):
                previous = game.state.player
                action = view.navigation.tick(game, now)
                if action is not None:
                    view.move_player(previous, game.state.player, action)
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
