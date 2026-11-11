"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

import os
from pathlib import Path
from time import perf_counter
from math import floor, sin, sqrt

import pico2d.pico2d as p

from game.model import Game
from game.art import Art
from game.scenery import draw_scars, draw_tinted, floor_style, wall_style
from game.navigation import ClickNavigator, IsoBoard, find_path
from game.themes import boundary_walls, low_wall_sprite, scene_for, themed_floor
from game.layout import WIDTH, HEIGHT, BOARD_BOTTOM, BOARD_TOP
from game.front_end import FrontEnd
from game.tutorial import first_room_hint
from game.transport import BeltAnimation

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
TUTORIAL_PANEL = (32, 600, 420, 810)


def font_path(size=18) -> str:
    """큰 대사는 주아체, 작은 안내는 기호가 풍부한 고운돋움으로 표시한다."""
    override = os.environ.get("DUNGEON_FONT")
    if override:
        if not Path(override).is_file():
            raise OSError(f"DUNGEON_FONT 파일을 찾을 수 없습니다: {override}")
        return override
    candidates = (
        Path(__file__).resolve().parents[1] / "assets/fonts" / (
            "Jua-Regular.ttf" if size >= 22 else "GowunDodum-Regular.ttf"),
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


def rounded_box(left, bottom, right, top, radius, color):
    """작은 UI 배지의 모서리를 별도 이미지 없이 둥글게 채운다."""
    for y in range(round(bottom), round(top) + 1):
        distance = max(bottom + radius - y, y - (top - radius), 0)
        inset = radius - sqrt(max(0, radius * radius - distance * distance))
        line(left + inset, y, right - inset, y, color)


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
        self.belt_animation = BeltAnimation()
        self.mouse_position = None
        self.show_coordinates = False
        self.tutorial = None
        self.hit_regions = []
        self.hit_masks = {}
        self.gate_hit_masks = {}
        self.plate_hit_masks = {}
        self.reset_gates()
        self.reset_plates()
        self.reset_player()
        try:
            for size in (13, 16, 18, 22, 26, 32, 48, 64):
                self.fonts[size] = p.load_font(font_path(size), size)
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
        self.gate_inlets = {}

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
        self.action_badge_bounds = None

    @staticmethod
    def fatigue(game):
        """행동 제한의 시각적 경고 단계. 퍼즐 규칙과 이동 속도는 바꾸지 않는다."""
        remaining = game.remaining_actions
        if remaining is None or game.state.cleared:
            return 0
        if remaining == 0:
            return 3
        if remaining <= 5:
            return 2
        return int(remaining <= max(5, game.level.action_limit // 5))

    def place_action_badge(self, game, x, head_top, now):
        value = "무제한" if game.remaining_actions is None else str(game.remaining_actions)
        width = max(88, len(value) * 22 + 24)
        x = min(WIDTH - 40 - width / 2, max(40 + width / 2, x))
        bottom = min(BOARD_TOP - 76, head_top + 16 + sin(now * 2.5) * 2)
        self.action_badge_bounds = (x - width / 2, bottom, x + width / 2, bottom + 64)

    def action_badge(self, game):
        """벽·장치보다 나중에 그려 남은 행동을 항상 머리 위에서 읽게 한다."""
        left, bottom, right, top = self.action_badge_bounds
        x = (left + right) / 2
        tired = self.fatigue(game)
        accent = ((58, 129, 113), (168, 110, 37), (190, 69, 66), (157, 54, 64))[tired]
        fill = ((238, 250, 225), (255, 242, 201), (255, 224, 215), (250, 215, 222))[tired]
        rounded_box(left + 2, bottom - 4, right + 2, top - 4, 18, (18, 32, 36))
        for offset in range(9):
            line(x - offset, bottom - 9 + offset, x + offset, bottom - 9 + offset, accent)
        rounded_box(left, bottom, right, top, 18, accent)
        rounded_box(left + 3, bottom + 3, right - 3, top - 3, 15, fill)
        self.centered(x, top - 15, "남은 행동", 13, accent)
        value = "무제한" if game.remaining_actions is None else str(game.remaining_actions)
        size = 22 if game.remaining_actions is None else 32
        self.centered(x, bottom + 23, value, size, accent)

    @staticmethod
    def worker_height(tired, now):
        """발은 지지면에 두고 상체를 낮추며, 남은 행동이 적을수록 숨을 가쁘게 쉰다."""
        if not tired:
            return 1.0
        base, amplitude, speed = ((.92, .018, 4.5), (.83, .028, 7), (.72, .012, 3))[tired - 1]
        return base + sin(now * speed) * amplitude

    def worker_effort(self, bounds, tired, now):
        if not tired:
            return
        left, bottom, right, top = bounds
        side = 1 if self.facing in ("ne", "se") else -1
        x = right + 6 if side == 1 else left - 6
        # 크기와 낙하 위상이 다른 물방울로 반복되는 땀을 표현한다.
        for index in range(1 if tired == 1 else 2):
            phase = (now * (.9 if tired == 1 else 1.3) + index * .5) % 1
            y = top - 8 - phase * 23
            radius = 2 + sin(phase * 3.14159) * 2
            dx = x + side * index * 11
            for offset in range(6):
                span = radius * offset / 5
                line(dx - span, y + 6 - offset, dx + span, y + 6 - offset, (119, 222, 244))
            rounded_box(dx - radius, y - radius, dx + radius, y + 1, radius, (119, 222, 244))
            line(dx - 1, y, dx - 1, y + 2, (235, 255, 255))
        value = ("후우…", "헉…", "털썩…")[tired - 1]
        tx = right + 14 if side == 1 else left - 61
        ty = max(bottom + 18, top - 38) + sin(now * 3) * 2
        self.text(tx + 1, ty - 1, value, 18, (23, 31, 36))
        self.text(tx, ty, value, 18, (255, 231, 178) if tired == 1 else (255, 187, 169))

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

    def transporting(self, game, now=None):
        return self.belt_animation.sample(game, perf_counter() if now is None else now) is not None

    def text(self, x, y, value, size=18, color=INK):
        self.fonts[size].draw(x, y, str(value), color)

    def centered(self, x, y, value, size=18, color=INK):
        import ctypes

        width = ctypes.c_int()
        p.TTF_SizeUTF8(self.fonts[size].font, str(value).encode("utf-8"), ctypes.byref(width), None)
        self.text(x - width.value / 2, y, value, size, color)

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
        left, bottom, right, top = TUTORIAL_PANEL
        if self.tutorial and left <= x <= right and bottom <= y <= top:
            return None
        if self.action_badge_bounds:
            left, bottom, right, top = self.action_badge_bounds
            if left <= x <= right and bottom - 9 <= y <= top:
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
                    # 반투명 문 너머 실제로 보이는 투입구를 클릭하면 그 칸을 고른다.
                    through_inlet = False
                    for inlet_region in self.gate_inlets.get((pos, (left, bottom, right, top)), ()):
                        if inlet_region not in self.hit_regions:
                            continue
                        inlet = self.hit_masks[inlet_region]
                        if self.art.hit_test(*inlet[:4], (x, y), *inlet[4:]):
                            through_inlet = True
                            break
                    if through_inlet:
                        # 문만 통과시켜 그 사이의 다른 불투명 물체는 정상적으로 판정한다.
                        continue
                    if not self.art.gate_hit_test(sx, sy, scale, (x, y), opening, flip):
                        continue
                    return pos
                if mask:
                    sprite, sx, sy, scale, flip, height_scale = mask
                    if not self.art.hit_test(sprite, sx, sy, scale, (x, y), flip, height_scale):
                        continue
                return pos
        return IsoBoard(game.level.width, game.level.height).pick(x, y)

    def sprite_hit_region(self, pos, sprite, sx, sy, scale, flip=False, height_scale=1.0):
        region = (pos, self.art.bounds(sprite, sx, sy, scale, flip, height_scale))
        self.hit_regions.append(region)
        self.hit_masks[region] = (sprite, sx, sy, scale, flip, height_scale)

    def navigation_overlay(self, game, projection):
        if game.failed or game.state.cleared:
            return
        target, path = self.navigation.target, self.navigation.path
        color = GOLD
        hovered = self.pick_cell(game, *self.mouse_position) if self.mouse_position else None
        if hovered is not None:
            target = hovered
            path = find_path(game, target)
            color = TEAL if path is not None else RED
            if path is not None and game.remaining_actions is not None and len(path) > game.remaining_actions:
                color = RED
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
        if hovered is not None:
            self.movement_cost_hint(game, path, color)

    def movement_cost_hint(self, game, path, color):
        """마우스를 올린 경로의 예상 행동 비용을 클릭 전에 보여준다."""
        import ctypes

        if path is None:
            labels = [("이동 불가", 18)]
        elif not path:
            labels = [("현재 칸 · 차감 0회", 18)]
        else:
            cost, remaining = len(path), game.remaining_actions
            labels = [(f"예상 차감 -{cost}회", 18)]
            if remaining is None:
                labels.append(("현재 경로 기준 · 행동 제한 없음", 13))
            elif cost > remaining:
                labels.append((f"남은 행동 {remaining}회 · {cost - remaining}회 부족", 13))
            else:
                labels.append((f"남은 행동 {remaining}회 · 이동 후 {remaining - cost}회 예상", 13))
        widths = []
        for label, size in labels:
            measured = ctypes.c_int()
            p.TTF_SizeUTF8(self.fonts[size].font, label.encode("utf-8"), ctypes.byref(measured), None)
            widths.append(measured.value)
        width, height = max(widths) + 24, 34 if len(labels) == 1 else 56
        x, y = self.mouse_position
        left = max(32, min(x + 18, WIDTH - 32 - width))
        bottom = max(BOARD_BOTTOM + 4, min(y + 22, BOARD_TOP - height - 4))
        box(left, bottom, left + width, bottom + height, (20, 32, 36))
        box(left, bottom, left + width, bottom + height, color, filled=False)
        self.text(left + 12, bottom + height - 18, labels[0][0], 18, color)
        if len(labels) == 2:
            self.text(left + 12, bottom + 12, labels[1][0], 13, color if color == RED else MUTED)

    def interaction_markers(self, game, projection):
        """작업 대상은 금색 표식, 현재 실행 가능한 행동은 E로 표시한다."""
        level, state = game.level, game.state
        self.interaction_regions = {}
        self.interaction_hint = None
        if state.cleared or game.failed:
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
            if pos == state.player and self.action_badge_bounds:
                sx = self.action_badge_bounds[2] + 18
                y = self.action_badge_bounds[1] + 22
            original_y = y
            # 사선상 앞뒤 물건의 표식이 겹치면 위아래로 나누고 연결선을 남긴다.
            for offset in (0, 28, -28, 56, -56, 84, -84, 112, -112):
                candidate = original_y + offset
                if not BOARD_BOTTOM + 15 < candidate < BOARD_TOP - 12:
                    continue
                if all(sx + 12 <= left or sx - 12 >= right
                       or candidate + 12 <= bottom or candidate - 12 >= upper
                       for left, bottom, right, upper in (
                           *self.interaction_regions.values(), self.action_badge_bounds)):
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
            self.interaction_hint = (f"상호작용 대상: {targets[hovered]} · 해당 칸에서 E"
                                     if level.id == "stage_01" else targets[hovered])

    def gate(self, level, pos, sx, sy, scale, status, opening=None):
        """문틀의 사선 축을 양옆 벽에 맞추고 열린 중앙은 클릭을 통과시킨다."""
        x, y = pos
        along_x = sum(cell in level.walls for cell in ((x - 1, y), (x + 1, y)))
        along_y = sum(cell in level.walls for cell in ((x, y - 1), (x, y + 1)))
        flip = along_x > along_y
        if opening is None:
            opening = 0 if status == "closed" else 1
        left, bottom, right, top = self.art.bounds("gate_closed", sx, sy, scale, flip)
        hidden_inlets = [region for region, mask in self.hit_masks.items()
                         if mask[0] == "chute_inlet"
                         and min(right, region[1][2]) - max(left, region[1][0]) > 12
                         and min(top, region[1][3]) - max(bottom, region[1][1]) > 12]
        atlas = self.art.atlases["gates"]
        # 앞쪽 문의 형체는 남기되, 뒤에 있는 필수 장치가 완전히 묻히지 않게 한다.
        atlas.opacify(.42 if hidden_inlets else 1)
        try:
            sprite = self.art.draw_gate(sx, sy, scale, opening, flip=flip)
        finally:
            atlas.opacify(1)
        self.sprite_hit_region(pos, sprite, sx, sy, scale, flip)
        self.gate_hit_masks[self.hit_regions[-1]] = (sx, sy, scale, opening, flip)
        if hidden_inlets:
            self.gate_inlets[self.hit_regions[-1]] = hidden_inlets

    def board(self, game):
        level, state = game.level, game.state
        now = perf_counter()
        transport = self.belt_animation.sample(game, now)
        moving_items = {}
        moving_sources = set()
        if transport:
            state, moves, fraction = transport
            moving_sources = {source for source, _, _ in moves}
        if self.gate_game is not game:
            self.reset_gates()
            self.reset_plates()
            self.gate_game = game
        gate_openings = {pos: self.gate_opening(pos, 0 if game.gate_status(pos, state) == "closed" else 1, now)
                         for pos in level.gates}
        self.plate_depths = {pos: self.device_progress(self.plate_motions, pos, float(game.plate_pressed(pos, state)), now, PLATE_SECONDS)
                             for pos in level.plates}
        if level.gates:
            self.art.load_gates()
        scene = scene_for(level)
        if scene:
            for pack in scene["packs"]:
                self.art.load_theme(pack)
            self.art.load_walls(scene.get("wall_pack", scene["packs"][0]))
        # 기존 사선 비율로 바닥과 높은 외곽 벽을 함께 화면에 넣는다.
        projection = IsoBoard(level.width, level.height)
        half_width, half_height = projection.half_width, projection.half_height
        scale = half_width * 2 / self.art.manifest["coordinates"]["tile_footprint"]["width"]
        screen = projection.screen
        self.hit_regions.clear()
        self.hit_masks.clear()
        self.gate_hit_masks.clear()
        self.gate_inlets.clear()
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
                    if pos in state.soldiers:
                        tile, tint = "post_empty", None
                    else:
                        # 발판까지 포함한 통합 그림을 깊이 순서에 맞춰 한 번만 그린다.
                        objects.append((depth, 1, "post_rack", sx, sy))
                    labels.append((pos, "배치 완료" if pos in state.soldiers else "몬스터 배치"))
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
                    labels.append((pos, "뼈 투입구"))
                elif pos in level.chutes.values():
                    objects.append((depth, 0.5, "chute_outlet", sx, sy))
                    if pos not in level.plates:
                        labels.append((pos, f"{level.device_labels[pos]} 배출"))
                if pos in level.plates:
                    pressed = game.plate_pressed(pos, state)
                    objects.append((depth, 1, "plate_down" if pressed else "plate_up", sx, sy))
                    labels.append((pos, f"{level.device_labels[pos]} " + ("눌림" if pressed else "발판")))
                elif pos in level.gates:
                    status = game.gate_status(pos, state)
                    objects.append((depth, 1, f"gate_{status}", sx, sy))
                    labels.append((pos, f"{level.device_labels[pos]} " + {"open": "열림", "held": "닫힘 대기", "closed": "닫힘"}[status]))
                elif pos in level.levers:
                    objects.append((depth, 1, "lever_on" if state.active else "lever_off", sx, sy))
                    labels.append((pos, "레버"))
                elif pos in level.benches:
                    stored = state.bench_bones.get(pos, 0)
                    objects.append((depth, 1, "bench_one_bone" if stored else "bench_empty", sx, sy))
                    labels.append((pos, f"조립 {stored}/2"))
                if pos in state.items and pos not in moving_sources:
                    objects.append((depth, 2, ITEM_SPRITES[state.items[pos]], sx, sy))
                if pos in state.soldiers:
                    objects.append((depth, 2, "soldier_deployed", sx, sy))

        if transport:
            for source, destination, kind in moves:
                position = tuple(a + (b - a) * fraction for a, b in zip(source, destination))
                sx, sy = screen(position)
                sprite = ITEM_SPRITES[kind]
                objects.append((sum(position), 2, sprite, sx, sy))
                moving_items[(sprite, sx, sy)] = (position, source)

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
            moving = moving_items.get((sprite, sx, sy))
            if moving:
                pos = moving[1]
            decor_scale = decor_draws.get((sprite, sx, sy))
            if decor_scale is not None:
                self.art.draw(sprite, sx, sy, decor_scale)
                # 장식의 위쪽 그림이 뒤의 이동 칸/장치 클릭을 가로채지 않는다.
                continue
            # 논리 칸은 높이를 더하기 전에 결정해야 클릭 대상이 옆 칸으로 밀리지 않는다.
            if sprite == "player":
                sy += self.player_support_height(game, player) * scale
            elif sprite in ITEM_SPRITES.values():
                sy += (self.player_support_height(game, moving[0]) if moving
                       else self.support_height(game, pos)) * scale
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
            tired = self.fatigue(game)
            height_scale = self.worker_height(tired, now)
            # 뒤를 볼 때 운반물은 몸 뒤에, 앞을 볼 때는 손 위에 합성한다.
            offset_x = 12 if self.facing in ("ne", "se") else -12
            if state.carrying and self.facing in ("ne", "nw"):
                self.item(state.carrying, sx + offset_x, sy + 32 * height_scale, scale * 0.65)
            self.art.draw(f"worker_{self.facing}_{pose}", sx, sy, scale, height_scale=height_scale)
            self.sprite_hit_region(pos, f"worker_{self.facing}_{pose}", sx, sy, scale, height_scale=height_scale)
            self.place_action_badge(game, sx, self.hit_regions[-1][1][3], now)
            self.worker_effort(self.hit_regions[-1][1], tired, now)
            if state.carrying and self.facing in ("se", "sw"):
                self.item(state.carrying, sx + offset_x, sy + 24 * height_scale, scale * 0.65)

        # 상태 문구를 바닥 아트와 함께 유지해 색이나 작은 그림에만 의존하지 않는다.
        for pos, label in labels:
            sx, sy = screen(pos)
            # 큰 방의 인접 장치 이름표는 배치별 여백으로 분리한다.
            dx, dy = scene.get("label_offsets", {}).get(f"{pos[0]},{pos[1]}", (0, 0)) if scene else (0, 0)
            if pos in level.posts:
                # 발판의 해골·발자국 문양을 이름표가 덮지 않게 한다.
                dy -= 18
            sx, sy = sx + dx, sy + dy
            width = len(label) * 16 + 10
            box(sx - width / 2, sy - 28, sx + width / 2, sy - 6, (24, 35, 40))
            color = TEAL if pos == level.exit and exit_ready else INK
            if pos in level.posts:
                color = TEAL if pos in state.soldiers else (218, 174, 255)
            elif pos in level.gates:
                color = {"open": TEAL, "held": GOLD, "closed": RED}[game.gate_status(pos, state)]
            elif pos in level.plates:
                color = TEAL if game.plate_pressed(pos, state) else GOLD
            self.text(sx - width / 2 + 5, sy - 17, label, 16, color)
            self.hit_regions.append((pos, (sx - width / 2, sy - 28, sx + width / 2, sy - 6)))
        if transport:
            self.interaction_regions = {}
            self.interaction_hint = None
        else:
            self.interaction_markers(game, projection)
        if self.show_coordinates:
            self.coordinate_overlay(level, projection)
        if not transport:
            self.navigation_overlay(game, projection)
        self.action_badge(game)

    def coordinate_overlay(self, level, projection):
        """벽과 물체 위에도 데이터의 (열, 행) 좌표를 표시한다."""
        for y in range(level.height):
            for x in range(level.width):
                sx, sy = projection.screen((x, y))
                label = f"({x},{y})"
                width = len(label) * 8 + 6
                box(sx - width / 2, sy, sx + width / 2, sy + 18, (19, 27, 32))
                self.text(sx - width / 2 + 3, sy + 9, label, 13, GOLD)

    def tutorial_overlay(self, game):
        hint = self.tutorial
        if hint is None:
            return
        if hint.target is not None:
            projection = IsoBoard(game.level.width, game.level.height)
            sx, sy = projection.screen(hint.target)
            color = TEAL if game.state.player == hint.target else GOLD
            for inset in (3, 5):
                diamond(sx, sy, projection.half_width - inset,
                        int(projection.half_height) - inset // 2, None, color)
            # 목표 안내도 해당 타일로 이동하는 클릭 영역이다.
            bounds = (sx - 66, sy - 59, sx + 66, sy - 33)
            box(*bounds, (25, 40, 42))
            box(*bounds, color, filled=False)
            self.centered(sx, sy - 46, hint.target_label, 16, color)
            self.hit_regions.append((hint.target, bounds))
        box(*TUTORIAL_PANEL, (25, 39, 42))
        box(*TUTORIAL_PANEL, (101, 120, 104), filled=False)
        self.text(52, 786, "첫 근무 · 튜토리얼", 16, GOLD)
        self.text(344, 786, f"{hint.step} / 5", 16, TEAL)
        for index in range(5):
            completed = hint.complete or index < hint.step - 1
            color = TEAL if completed else GOLD if index == hint.step - 1 else (59, 77, 77)
            box(52 + index * 70, 762, 112 + index * 70, 765, color)
        self.text(52, 730, hint.title, 22, INK)
        self.wrapped(52, 690, hint.instruction, width=344, size=16, color=INK)
        self.text(52, 619, "행동 무제한 · Z 되돌리기 · R 다시 시작", 13, MUTED)

    def play_context(self, game):
        """입문방 이후에는 지금 필요한 작업과 피드백만 한 줄로 표시한다."""
        if game.failed:
            return game.context_action(), RED
        if game.state.cleared:
            return "복구 완료", TEAL
        if self.transporting(game):
            return "벨트 자동 운반 중", TEAL
        if game.repair_percent == 100:
            return "복구 완료 · 출구로 돌아가세요", TEAL
        if self.interaction_hint:
            return self.interaction_hint, GOLD
        level = game.level
        targets = level.traps | level.benches | level.posts | level.levers | level.chutes.keys() | game.state.items.keys()
        if game.can_interact() or game.state.player in targets:
            return game.context_action(), TEAL if game.can_interact() else MUTED
        quiet = {
            "물건이나 장치 위에서 E를 누르세요.", "현재 서 있는 칸입니다.",
            "선택한 칸으로 이동합니다. 우클릭으로 취소할 수 있습니다.",
            "자동 이동을 취소했습니다.", "직전 행동을 되돌렸습니다.",
        }
        if game.message not in quiet and not game.message.startswith("한 칸 이동했습니다."):
            return game.message, MUTED
        return "", MUTED

    def repair_progress(self, game, left, width):
        percent = game.repair_percent
        color = TEAL if percent == 100 else GOLD
        self.text(left, BOARD_TOP + 25, f"복구율 {percent}%", 16, color)
        box(left, BOARD_TOP + 5, left + width, BOARD_TOP + 9, (59, 77, 77))
        if percent:
            box(left, BOARD_TOP + 5, left + width * percent / 100, BOARD_TOP + 9, color)

    def draw_play(self, game, index, total):
        """2번 방부터 사용하는 간결한 플레이 HUD. 게임판 좌표는 유지한다."""
        level, state = game.level, game.state
        scene = scene_for(level)
        background = tuple(scene["background"]) if scene else (19, 27, 32)
        box(0, 0, WIDTH, HEIGHT, background)
        self.text(40, HEIGHT - 48, f"{index + 1:02d} / {total:02d}", 18, GOLD)
        self.text(150, HEIGHT - 48, level.title, 26, INK)
        self.board(game)

        box(32, BOARD_TOP, WIDTH - 32, BOARD_TOP + 40, (28, 39, 44))
        x = 48
        if level.traps:
            self.text(x, BOARD_TOP + 20, f"함정 {len(state.installed)} / {len(level.traps)}", 18)
            self.text(x + 150, BOARD_TOP + 20, "가동 완료" if state.active else "미가동", 16,
                      TEAL if state.active else MUTED)
            x += 300
        if level.posts:
            self.text(x, BOARD_TOP + 20, f"병사 {len(state.soldiers)} / {len(level.posts)}", 18)
        self.text(740, BOARD_TOP + 20, f"운반: {ITEM_NAMES[state.carrying]}", 18, GOLD if state.carrying else MUTED)
        if state.carrying:
            self.item(state.carrying, 940, BOARD_TOP + 8, 0.19)
        self.repair_progress(game, 1000, 200)

        context, color = self.play_context(game)
        if context:
            box(32, 32, WIDTH - 32, 78, (28, 39, 44))
            self.text(48, 55, context, 18, color)
        if state.cleared:
            label = "E / Space  다음 방" if index + 1 < total else "E / Space  처음부터 다시"
            self.text(WIDTH - 323, 55, label, 18, TEAL)

    def draw(self, game, index, total):
        level, state = game.level, game.state
        self.tutorial = first_room_hint(game)
        if game.failed:
            self.navigation.cancel()
        if level.id != "stage_01":
            self.draw_play(game, index, total)
            return
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
        self.tutorial_overlay(game)

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
        self.repair_progress(game, 1120, 110)

        box(32, 48, WIDTH - 32, BOARD_BOTTOM, (41, 55, 58))
        transporting = self.transporting(game)
        context = "벨트 자동 운반 중 · Z 되돌리기 / R 재시작" if transporting else self.interaction_hint or game.context_action()
        self.text(48, 80, context, 18, RED if game.failed else TEAL)
        self.text(48, 59, "운반이 끝나면 다음 행동을 할 수 있습니다." if transporting else game.message, 16, INK)
        if state.cleared:
            box(WIDTH - 340, 53, WIDTH - 44, 89, (46, 96, 81))
            label = "E / Space  다음 방" if index + 1 < total else "E / Space  처음부터 다시"
            self.text(WIDTH - 323, 71, label, 18)
        elif game.failed:
            box(WIDTH - 362, 53, WIDTH - 44, 89, (96, 45, 39))
            self.text(WIDTH - 348, 71, "행동 소진 · 되돌리기 / 재시작", 16, INK)
        else:
            status = f"자동 이동 · {len(self.navigation.path)}칸 남음" if self.navigation.active else "모든 복구 후 빈손으로 출구 복귀"
            self.text(WIDTH - 362, 71, status, 16, MUTED)

        self.text(34, 32, f"좌클릭  이동    우클릭  취소    WASD / 방향키  이동    개발용 1~{total} 방 이동 · F2 좌표    (x,y): x 오른쪽 아래 / y 왼쪽 아래", 13, MUTED)
        self.text(34, 12, "E / Space  상호작용·내려놓기·다음 방(완료 후)    Z / Backspace  되돌리기    R  재시작    Esc  종료", 13, MUTED)


def run(levels, index=0, smoke_frames=None, *, show_title=True):
    # 글꼴 오류는 SDL 창을 열기 전에 보고한다.
    font_path()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    front_end = None
    try:
        if not p.window or not p.renderer:
            raise RuntimeError("SDL 게임 창 또는 렌더러를 만들 수 없습니다.")
        view = View()
        front_end = FrontEnd(show_title)
        game = Game(levels[index])
        actions = {
            p.SDLK_UP: "up", p.SDLK_w: "up", p.SDLK_DOWN: "down", p.SDLK_s: "down",
            p.SDLK_LEFT: "left", p.SDLK_a: "left", p.SDLK_RIGHT: "right", p.SDLK_d: "right",
            p.SDLK_e: "interact", p.SDLK_SPACE: "interact",
        }
        stage_keys = {
            p.SDLK_1: 0, p.SDLK_2: 1, p.SDLK_3: 2,
            p.SDLK_4: 3, p.SDLK_5: 4, p.SDLK_6: 5, p.SDLK_7: 6, p.SDLK_8: 7,
        }
        running, frames = True, 0
        while running:
            screen_changed = False
            for event in p.get_events():
                if event.type == p.SDL_QUIT:
                    running = False
                    break
                elif screen_changed:
                    continue
                elif (front_end.screen == "title" and event.type == p.SDL_KEYDOWN
                      and event.key in stage_keys and stage_keys[event.key] < len(levels)):
                    index = stage_keys[event.key]
                    game = Game(levels[index])
                    front_end.screen = "playing"
                    view.reset_player()
                    view.navigation.cancel()
                    view.mouse_position = None
                    screen_changed = True
                elif front_end.screen != "playing":
                    result = front_end.handle(event)
                    if result == "quit":
                        running = False
                    elif result == "start":
                        index = 0
                        game = Game(levels[index])
                        view.reset_player()
                        view.navigation.cancel()
                        view.mouse_position = None
                    if result is not None:
                        # 전환 뒤 입력은 무시하되 같은 묶음의 창 닫기는 처리한다.
                        screen_changed = True
                elif event.type == p.SDL_MOUSEMOTION:
                    view.mouse_position = (event.x, HEIGHT - 1 - event.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN:
                    view.mouse_position = (event.x, HEIGHT - 1 - event.y)
                    if event.button == p.SDL_BUTTON_RIGHT:
                        if view.navigation.active:
                            game.message = "자동 이동을 취소했습니다."
                        view.navigation.cancel()
                    elif event.button == p.SDL_BUTTON_LEFT and not view.transporting(game):
                        target = view.pick_cell(game, *view.mouse_position)
                        if target is not None:
                            now = perf_counter()
                            ready_at = view.motion[2] + 0.18 if view.motion else now
                            view.navigation.start(game, target, now, ready_at=ready_at)
                elif event.type == p.SDL_KEYDOWN:
                    if event.key in (p.SDLK_b, p.SDLK_q):
                        continue
                    if view.transporting(game) and event.key not in (
                            p.SDLK_ESCAPE, p.SDLK_F2, p.SDLK_z, p.SDLK_BACKSPACE, p.SDLK_r, *stage_keys):
                        continue
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
                    elif event.key in (p.SDLK_e, p.SDLK_SPACE) and game.state.cleared:
                        index = (index + 1) % len(levels)
                        game = Game(levels[index])
                        view.reset_player()
                        screen_changed = True
                    elif event.key in actions:
                        action = actions[event.key]
                        previous = game.state.player
                        changed = game.act(action)
                        if action in FACING and changed:
                            view.move_player(previous, game.state.player, action)
                        elif changed:
                            # 도착 직후 상호작용하면 그 칸에 바로 정렬한다.
                            view.motion = None
                        if changed:
                            view.belt_animation.start(game, perf_counter())
            # 이미 보간 중인 한 칸이 끝난 뒤에만 다음 자동 이동을 실행한다.
            now = perf_counter()
            front_end.update(now)
            if (running and front_end.screen == "playing" and not view.transporting(game, now)
                    and (view.motion is None or now >= view.motion[2] + 0.18)):
                previous = game.state.player
                action = view.navigation.tick(game, now)
                if action is not None:
                    view.move_player(previous, game.state.player, action)
                    view.belt_animation.start(game, now)
            if front_end.screen == "playing":
                view.draw(game, index, len(levels))
            else:
                front_end.draw(view)
            p.update_canvas()
            p.SDL_SetWindowTitle(p.window, "용사가 지나간 자리 — 기초 프로토타입".encode("utf-8"))
            frames += 1
            if smoke_frames is not None and frames >= smoke_frames:
                running = False
    finally:
        if front_end:
            front_end.close()
        if view:
            view.close()
        p.close_canvas()
