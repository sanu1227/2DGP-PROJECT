"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

import os
from pathlib import Path
from time import perf_counter
from math import floor

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
GATE_SECONDS = 0.36
PLATE_SECONDS = 0.24


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
        self.gate_hit_masks = {}
        self.plate_hit_masks = {}
        self.reset_gates()
        self.reset_plates()
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

    def reset_gates(self):
        self.gate_game = None
        self.gate_motions = {}

    def reset_plates(self):
        self.plate_motions = {}
        self.plate_depths = {}

    @staticmethod
    def device_progress(motions, pos, target, now, seconds):
        motion = motions.get(pos)
        if motion is None:
            motions[pos] = (target, target, now, 0)
            return target
        start, end, began, duration = motion
        t = min(1, max(0, (now - began) / duration)) if duration else 1
        value = start + (end - start) * t * t * (3 - 2 * t)
        if end != target:
            motions[pos] = (value, target, now, seconds * abs(target - value))
        return value

    def gate_opening(self, pos, target, now):
        return self.device_progress(self.gate_motions, pos, target, now, GATE_SECONDS)

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
        sprite = ITEM_SPRITES[kind]
        entry = self.art.manifest["sprites"][sprite]
        self.art.draw(sprite, x, y, scale, anchor=entry.get("display_anchor", entry["anchor"]))

    def support_height(self, game, pos):
        """벨트·발판 위 물건과 캐릭터의 접점을 지지면에 맞춘다."""
        if pos in game.level.plates:
            pressed = self.plate_depths.get(pos, float(game.plate_pressed(pos))) if self.gate_game is game else float(game.plate_pressed(pos))
            up, down = self.art.surface_height("plate_up"), self.art.surface_height("plate_down")
            return up + (down - up) * pressed
        if pos in game.level.belts:
            direction = game.level.belts[pos]
            return self.art.surface_height("conveyor_ne" if direction in ("up", "left") else "conveyor_se")
        return 0

    def player_support_height(self, game, position):
        """걸어서 올라가거나 내려올 때도 이동 중 발 높이가 끊기지 않게 한다."""
        x, y = position
        left, top = floor(x), floor(y)
        u, v = x - left, y - top
        return sum(self.support_height(game, pos) * weight for pos, weight in (
            ((left, top), (1 - u) * (1 - v)), ((left + 1, top), u * (1 - v)),
            ((left, top + 1), (1 - u) * v), ((left + 1, top + 1), u * v)))

    def pick_cell(self, game, x, y):
        """UI는 제외하고 앞에 그려진 물체부터 검사한 뒤 바닥 칸을 고른다."""
        if not BOARD_BOTTOM < y < BOARD_TOP:
            return None
        for pos, (left, bottom, right, top) in reversed(self.hit_regions):
            if left <= x < right and bottom <= y < top:
                mask = self.hit_masks.get((pos, (left, bottom, right, top)))
                gate_mask = self.gate_hit_masks.get((pos, (left, bottom, right, top)))
                plate_mask = self.plate_hit_masks.get((pos, (left, bottom, right, top)))
                if plate_mask:
                    sx, sy, scale, pressed = plate_mask
                    if not self.art.plate_hit_test(sx, sy, scale, (x, y), pressed):
                        continue
                    return pos
                if gate_mask:
                    sx, sy, scale, opening, flip = gate_mask
                    if not self.art.gate_hit_test(sx, sy, scale, (x, y), opening, flip):
                        continue
                    return pos
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

    def interaction_markers(self, game, projection):
        """작업 대상은 금색 표식, 현재 실행 가능한 행동은 E로 표시한다."""
        level, state = game.level, game.state
        self.interaction_regions = {}
        self.interaction_hint = None
        if state.cleared:
            return
        targets = {pos: "함정 설치" for pos in level.traps - state.installed}
        targets.update({pos: "병사 배치" for pos in level.posts - state.soldiers})
        targets.update({pos: "병사 조립" for pos in level.benches})
        targets.update({pos: "뼈 투입구" for pos in level.chutes})
        if not state.active:
            targets.update({pos: "레버 가동" for pos in level.levers})
        targets.update({pos: ITEM_NAMES[kind] for pos, kind in state.items.items()})
        for pos in sorted(targets, key=lambda cell: (sum(cell), cell)):
            sx, sy = projection.screen(pos)
            # 같은 칸 캐릭터까지 포함해 표식이 머리나 물건에 가려지지 않게 한다.
            top = max((rect[3] for cell, rect in self.hit_masks if cell == pos), default=sy + 8)
            y = min(top + 15, BOARD_TOP - 15)
            original_y = y
            # 사선상 앞뒤 물건의 표식이 겹치면 위아래로 나누고 연결선을 남긴다.
            for offset in (0, 28, -28, 56, -56, 84, -84, 112, -112):
                candidate = original_y + offset
                if not BOARD_BOTTOM + 15 < candidate < BOARD_TOP - 12:
                    continue
                if all(sx + 12 <= left or sx - 12 >= right
                       or candidate + 12 <= bottom or candidate - 12 >= upper
                       for left, bottom, right, upper in self.interaction_regions.values()):
                    y = candidate
                    break
            if y != original_y:
                line(sx, original_y, sx, y, GOLD)
            ready = pos == state.player and game.can_interact()
            if ready:
                box(sx - 11, y - 11, sx + 11, y + 11, (24, 35, 40))
                box(sx - 11, y - 11, sx + 11, y + 11, TEAL, filled=False)
                self.text(sx - 5, y, "E", 16, TEAL)
            else:
                diamond(sx, y, 9, 9, (24, 35, 40), GOLD)
                diamond(sx, y, 3, 3, GOLD)
            rect = (sx - 12, y - 12, sx + 12, y + 12)
            self.interaction_regions[pos] = rect
            self.hit_regions.append((pos, rect))
        hovered = self.pick_cell(game, *self.mouse_position) if self.mouse_position else None
        if hovered in targets and hovered != state.player:
            self.interaction_hint = f"상호작용 대상: {targets[hovered]} · 해당 칸에서 E"

    def gate(self, level, pos, sx, sy, scale, status, opening=None):
        """문틀의 사선 축을 양옆 벽에 맞추고 열린 중앙은 클릭을 통과시킨다."""
        x, y = pos
        along_x = sum(cell in level.walls for cell in ((x - 1, y), (x + 1, y)))
        along_y = sum(cell in level.walls for cell in ((x, y - 1), (x, y + 1)))
        flip = along_x > along_y
        if opening is None:
            opening = 0 if status == "closed" else 1
        sprite = self.art.draw_gate(sx, sy, scale, opening, flip=flip)
        self.sprite_hit_region(pos, sprite, sx, sy, scale, flip)
        self.gate_hit_masks[self.hit_regions[-1]] = (sx, sy, scale, opening, flip)

    def board(self, game):
        level, state = game.level, game.state
        now = perf_counter()
        if self.gate_game is not game:
            self.reset_gates()
            self.reset_plates()
            self.gate_game = game
        gate_openings = {pos: self.gate_opening(pos, 0 if game.gate_status(pos) == "closed" else 1, now)
                         for pos in level.gates}
        self.plate_depths = {pos: self.device_progress(self.plate_motions, pos, float(game.plate_pressed(pos)), now, PLATE_SECONDS)
                             for pos in level.plates}
        if level.gates:
            self.art.load_gates()
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
        self.gate_hit_masks.clear()
        self.plate_hit_masks.clear()

        exit_ready = (state.installed == level.traps and (not level.traps or state.active)
                      and state.soldiers == level.posts and state.carrying is None)
        objects, labels, wall_tints = [], [], {}
        decor_draws = {}
        decoration_cells = {tuple(entry["cell"]) for entry in scene["decorations"]} if scene else set()
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
                    if pos in decoration_cells:
                        # 소품 아래는 속이 빈 코너나 잔해 대신 평평한 받침을 둔다.
                        wall_sprite = low_wall = "wall_low_pier"
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
                    labels.append((pos, f"{level.device_labels[pos]} " + ("눌림" if pressed else "발판")))
                elif pos in level.gates:
                    status = game.gate_status(pos)
                    objects.append((depth, 1, f"gate_{status}", sx, sy))
                    labels.append((pos, f"{level.device_labels[pos]} " + {"open": "열림", "held": "닫힘 대기", "closed": "닫힘"}[status]))
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
                    objects.append((depth, 2, "soldier_deployed", sx, sy))

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
                sy += self.art.surface_height("wall_low_pier") * scale
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
            # 논리 칸은 높이를 더하기 전에 결정해야 클릭 대상이 옆 칸으로 밀리지 않는다.
            if sprite == "player":
                sy += self.player_support_height(game, player) * scale
            elif sprite in ITEM_SPRITES.values():
                sy += self.support_height(game, pos) * scale
            if sprite in ("plate_up", "plate_down"):
                pressed = self.plate_depths[pos]
                self.art.draw_plate(sx, sy, scale, pressed)
                self.sprite_hit_region(pos, "plate_up", sx, sy, scale)
                self.plate_hit_masks[self.hit_regions[-1]] = (sx, sy, scale, pressed)
                continue
            if sprite.startswith("belt_"):
                direction = sprite.removeprefix("belt_")
                name = "conveyor_ne" if direction in ("up", "left") else "conveyor_se"
                flip = direction in ("left", "down")
                self.art.draw(name, sx, sy, scale, flip=flip)
                self.sprite_hit_region(pos, name, sx, sy, scale, flip)
                continue
            if sprite.startswith("gate_"):
                self.gate(level, pos, sx, sy, scale, sprite.removeprefix("gate_"), gate_openings[pos])
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
            color = TEAL if pos == level.exit and exit_ready else INK
            if pos in level.gates:
                color = {"open": TEAL, "held": GOLD, "closed": RED}[game.gate_status(pos)]
            elif pos in level.plates:
                color = TEAL if game.plate_pressed(pos) else GOLD
            self.text(sx - width / 2 + 5, sy - 17, label, 16, color)
            self.hit_regions.append((pos, (sx - width / 2, sy - 28, sx + width / 2, sy - 6)))
        self.interaction_markers(game, projection)
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
        diamond(982, BOARD_TOP + 17, 6, 6, None, GOLD)
        self.text(997, BOARD_TOP + 17, "상호작용 대상", 13, GOLD)
        self.text(WIDTH - 340, BOARD_TOP + 17, f"행동 {state.moves} · 되돌리기 {len(game.history)}", 16, MUTED)

        box(32, 48, WIDTH - 32, BOARD_BOTTOM, (41, 55, 58))
        self.text(48, 80, self.interaction_hint or game.context_action(), 18, TEAL)
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
                        view.reset_gates()
                        view.reset_plates()
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
