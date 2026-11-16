"""pico2d 화면과 키 입력. 퍼즐 판정은 model.Game이 전담한다."""

from ctypes import byref
import os
from pathlib import Path
from time import perf_counter
from math import floor, pi, sin, sqrt

import pico2d.pico2d as p

from game.model import DIRECTIONS, INTERACTION_HELP, PUSH_ACTIONS, Game
from game.art import Art, MAGIC_BEAM_HEIGHT
from game.scenery import draw_scars, draw_tinted, floor_style, wall_style
from game.navigation import ClickNavigator, IsoBoard, TopDownBoard, find_path
from game.themes import boundary_walls, low_wall_sprite, scene_for, themed_floor
from game.layout import WIDTH, HEIGHT, BOARD_BOTTOM, BOARD_TOP
from game.front_end import FrontEnd
from game.tutorial import first_room_hint
from game.mechanics import fixed_devices, mirror_cells, trace_magic
from game.optics import TOPDOWN_SOURCE_REACH, trace_display_magic
from game.play_menu import PlayClock, PlayMenu
from game.stage_feedback import StageFeedback
from game.receiver_feedback import ReceiverFeedback
from game.room_debris import RoomDebris
from game.room_atmosphere import RoomAtmosphere, prop_kind
from game.play_effects import ChuteFeedback, WorkFeedback, WORK_SECONDS, beam_contacts, dust, ring, rubble_scrape, trap_motion
from game.topdown import ITEMS as TOPDOWN_ITEMS, TopDownArt, draw_board as draw_topdown_board
from game.worker_view import EchoMotion, draw_echo_marks, draw_echo_turn, draw_worker_status, recording_label
from game.worker_animation import GESTURES, WorkerAction, sample_pose
from game.music import BackgroundMusic

INK = (226, 230, 219)
MUTED = (158, 169, 166)
GOLD = (227, 187, 104)
TEAL = (104, 206, 184)
RED = (232, 119, 105)
ITEM_NAMES = {None: "빈손", "part": "함정 부품", "bone": "뼈 묶음", "soldier": "해골 병사"}
ITEM_SPRITES = {"part": "part", "bone": "bone_bundle", "soldier": "soldier_carried"}
FACING = {"up": "ne", "right": "se", "down": "sw", "left": "nw"}
FACING_DIRECTION = {sprite: direction for direction, sprite in FACING.items()}
GATE_SECONDS = 0.36
PLATE_SECONDS = 0.24
PUSH_SECONDS = 0.28
MIRROR_SECONDS = 0.30
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
        self.clock = PlayClock()
        self.fonts = {}
        self.art = None
        self.topdown_art = None
        self.top_down = False
        self.navigation = ClickNavigator()
        self.mouse_position = None
        self.show_coordinates = False
        self.tutorial = None
        self.tutorial_hidden = False
        self.hit_regions = []
        self.hit_masks = {}
        self.gate_hit_masks = {}
        self.plate_hit_masks = {}
        self.receiver_feedback = ReceiverFeedback()
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

    def now(self):
        return self.clock.now(perf_counter())

    def projection(self, level):
        if self.top_down:
            return TopDownBoard(level.width, level.height, tutorial=level.id == "stage_01")
        return IsoBoard(level.width, level.height)

    @staticmethod
    def tile_outline(projection, x, y, width, height, color):
        if isinstance(projection, TopDownBoard):
            box(x - width, y - height, x + width, y + height, color, filled=False)
        else:
            diamond(x, y, width, height, None, color)

    def pause(self):
        self.clock.pause(perf_counter())

    def resume(self):
        self.clock.resume(perf_counter())

    def close(self):
        if self.topdown_art:
            self.topdown_art.close()
            self.topdown_art = None
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
        self.receiver_feedback.reset()
        self.mirror_game = None
        self.mirror_motions = {}
        self.facing = "se"
        self.motion = None
        self.move_seconds = 0.18
        self.rubble_motions = {}
        self.rubble_impulses = []
        self.pushing = False
        self.board_offset = (0, 0)
        self.mirror_pushes = {}
        self.plate_delays = {}
        self.echo_motion = EchoMotion()
        self.chute_feedback = ChuteFeedback()
        self.work_feedback = WorkFeedback()
        self.worker_action = None
        self.action_badge_bounds = None

    def mirror_rotation(self, game, pos, now):
        """정수 논리 방향과 별개인 표시 각도. 마지막 방향에서 첫 방향도 계속 같은 쪽으로 돈다."""
        motion = self.mirror_motions.get(pos) if self.mirror_game is game else None
        if motion is None:
            return game.state.mirror_rotations.get(pos, 0)
        start, target, began, duration = motion
        t = max(0, min(1, (now - began) / duration))
        if t >= 1:
            self.mirror_motions.pop(pos)
            return game.state.mirror_rotations.get(pos, 0)
        return start + (target - start) * t * t * (3 - 2 * t)

    def animate_devices(self, game, previous):
        """성공한 행동 이벤트에만 연결한다. 연타는 현재 각도에서 이어지며 입력을 막지 않는다."""
        now = self.now()
        self.echo_motion.change(game, previous, now)
        work = self.work_feedback.changed(game, previous, now)
        if work:
            kind, target = work
            if kind in GESTURES:
                self.start_worker_action(game, previous, kind, target, now)
        outlet = self.chute_feedback.transferred(game, previous, now)
        if outlet in game.level.plates and not game.plate_pressed(outlet, previous):
            self.plate_motions.setdefault(outlet, (0, 0, now, 0))
            self.plate_delays[outlet] = (now + self.chute_feedback.arrival, 0)
        if self.mirror_game is not game:
            self.mirror_game, self.mirror_motions = game, {}
        for pos in mirror_cells(game.level, previous) & mirror_cells(game.level, game.state):
            old, new = previous.mirror_rotations.get(pos, 0), game.state.mirror_rotations.get(pos, 0)
            if old == new:
                continue
            motion = self.mirror_motions.get(pos)
            if motion and now < motion[2] + motion[3]:
                start = self.mirror_rotation(game, pos, now)
                target = motion[1] + (new - old) % 4
            else:
                start, target = old, old + (new - old) % 4
            duration = min(.5, MIRROR_SECONDS * (target - start))
            self.mirror_motions[pos] = (start, target, now, duration)

    def draw_mirror_stop(self, board, pos, point, now):
        motion = self.mirror_motions.get(pos)
        if motion:
            t = (now - motion[2]) / motion[3]
            if .72 < t < 1:
                x, y = point
                ring(x, y, board.half_width * (.45 + (t - .72) * .6), GOLD, 170 * (1 - t) / .28)

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
        progress = min(1.0, max(0, (now - began) / self.move_seconds))
        if progress >= 1:
            self.motion = None
            return fallback
        if self.move_seconds == PUSH_SECONDS:
            progress = progress * progress * (3 - 2 * progress)
        return tuple(a + (b - a) * progress for a, b in zip(start, target))

    def move_player(self, previous, destination, action, seconds=0.18):
        """논리 이동은 즉시 완료하고 표시 위치만 짧게 보간한다."""
        now = self.now()
        start = self.player_position(previous, now)
        self.facing = FACING[action]
        self.worker_action = None
        self.move_seconds = seconds
        self.motion = (start, destination, now)

    def rubble_pose(self, game, destination, now):
        """논리 칸과 별개인 잔해의 위치·밑면 높이. 발판 턱을 타고 올라간다."""
        target_height = self.support_height(game, destination)
        motion = self.rubble_motions.get(destination)
        if motion is None:
            return destination, target_height
        start, height, began = motion
        t = min(1, max(0, (now - began) / PUSH_SECONDS))
        if t >= 1:
            self.rubble_motions.pop(destination)
            return destination, target_height
        travel = t * t * (3 - 2 * t)
        position = tuple(a + (b - a) * travel for a, b in zip(start, destination))
        # 이동의 마지막 부분은 상판에 얹힌 채 함께 내려온다. 공중으로 튀지 않는다.
        climb = min(1, travel / .65)
        climb = climb * climb * (3 - 2 * climb)
        return position, height + (target_height - height) * climb

    def mirror_position(self, destination, now):
        motion = self.mirror_pushes.get(destination)
        if motion is None:
            return destination
        start, began = motion
        t = min(1, max(0, (now - began) / PUSH_SECONDS))
        if t >= 1:
            self.mirror_pushes.pop(destination)
            return destination
        travel = t * t * (3 - 2 * t)
        return tuple(a + (b - a) * travel for a, b in zip(start, destination))

    def animate_move(self, game, previous, action):
        """성공한 이동 이벤트에서만 표시 동작을 시작한다. 연속 입력은 현 위치에서 잇는다."""
        if (previous.recording and game.state.recording is None
                and previous.recording.origin not in game.state.replay_workers):
            self.motion = None
            self.facing = FACING[action]
            return
        removed = previous.rubble - game.state.rubble
        added = game.state.rubble - previous.rubble
        pushing = len(removed) == len(added) == 1
        if pushing:
            source, destination = next(iter(removed)), next(iter(added))
            now = self.now()
            position, height = self.rubble_pose(game, source, now)
            self.rubble_motions.pop(source, None)
            self.rubble_motions[destination] = (position, height, now)
            self.rubble_impulses.append(now)
            if destination in game.level.plates:
                was_pressed = float(game.plate_pressed(destination, previous))
                self.plate_motions.setdefault(destination, (was_pressed, was_pressed, now, 0))
                self.plate_delays[destination] = (now + PUSH_SECONDS * .65, was_pressed)
        moved_mirrors = game.state.movable_mirrors - previous.movable_mirrors
        if moved_mirrors:
            now = self.now()
            source = game.state.player
            destination = next(iter(moved_mirrors))
            position = self.mirror_position(source, now)
            self.mirror_pushes.pop(source, None)
            self.mirror_pushes[destination] = (position, now)
            if source in self.mirror_motions:
                self.mirror_motions[destination] = self.mirror_motions.pop(source)
        self.pushing = pushing or bool(moved_mirrors)
        self.move_player(previous.player, game.state.player, action,
                         PUSH_SECONDS if self.pushing else .18)

    def start_worker_action(self, game, previous, kind, target, now):
        action = WorkerAction(kind, previous.player, target, previous.carrying,
                              game.state.carrying, now, WORK_SECONDS[kind])
        self.worker_action = action
        if action.direction:
            self.facing = FACING[action.direction]
        elif kind == "lever":
            self.facing = FACING["down"]
        if kind == "drop" and target in game.level.plates and not game.plate_pressed(target, previous):
            self.plate_motions.setdefault(target, (0, 0, now, 0))
            self.plate_delays[target] = (now + action.contact * action.seconds, 0)

    def current_worker_action(self, game, now):
        action = self.worker_action
        if action and action.origin == game.state.player and action.progress(now) < 1:
            return action
        return None

    def character_pose(self, game, board, feet, now, body_size):
        walk = "idle"
        if self.motion:
            walk = "walk_a" if now - self.motion[2] < self.move_seconds / 2 else "walk_b"
        action = self.current_worker_action(game, now)
        pose = sample_pose(FACING_DIRECTION[self.facing], body_size, self.worker_height(self.fatigue(game), now),
                           walk, game.state.carrying, action, now, top_down=self.top_down,
                           push=bool(self.pushing and self.motion))
        if action and action.kind == "lever":
            x, y = board.screen(action.target)
            _, reach = action.reaches(now)
            progress = action.progress(now)
            if self.top_down:
                handle = (x, y + body_size * (.32 if progress >= action.contact else -.32))
            else:
                handle = (x + body_size * (.16 if progress >= action.contact else -.16), y + body_size * .42)
            pose = pose.reach_toward(feet, handle, reach, body_size)
        return pose

    def item_is_in_hands(self, game, pos, now):
        action = self.current_worker_action(game, now)
        return action and action.kind == "drop" and action.target == pos and action.progress(now) < action.contact

    def draw_iso_worker(self, game, board, sx, sy, scale, now):
        state = game.state
        pose = self.character_pose(game, board, (sx, sy), now, 256 * scale)
        action = self.current_worker_action(game, now)

        def draw_item():
            kind = pose.item
            if kind is None:
                return
            sprite = ITEM_SPRITES[kind]
            data = self.art.manifest["sprites"][sprite]
            rect = data["content_rect"]
            center = {"x": rect["left"] + rect["width"] / 2, "y": rect["top"] + rect["height"] / 2}
            target = action.target if action else state.player
            x, y = board.screen(target)
            y += (self.support_height(game, target) + data["anchor"]["y"] - center["y"]) * scale
            x, y = pose.item_position((sx, sy), (x, y))
            self.art.draw(sprite, x, y, scale * (.65 + .35 * pose.item_floor_scale), anchor=center)

        back = self.facing in ("ne", "nw")
        if back:
            draw_item()
        for part, dx, dy, rows in pose.layers(False):
            sprite = f"worker_{self.facing}_{part}"
            self.art.draw(sprite, sx + dx, sy + dy, scale, height_scale=pose.height, rows=rows)
            self.sprite_hit_region(state.player, sprite, sx + dx, sy + dy, scale, height_scale=pose.height, rows=rows)
        if not back:
            draw_item()
        body_bounds = self.hit_regions[-1][1]
        self.place_action_badge(game, sx, body_bounds[3], now)
        self.worker_effort(body_bounds, self.fatigue(game), now)

    def draw_rubble_scrape(self, board, pos, position, now):
        motion = self.rubble_motions.get(pos)
        if motion:
            start, _, began = motion
            rubble_scrape(board, start, pos, position, min(1, max(0, (now - began) / PUSH_SECONDS)))

    def draw_gate_dust(self, board, pos, now):
        motion = self.gate_motions.get(pos)
        if motion is None:
            return
        start, end, began, duration = motion
        age = now - (began + duration * .85)
        if duration and end > start and 0 <= age < .26:
            x, y = board.screen(pos)
            dust(x, y + board.half_height * .25, age / .26, size=.85)

    def plate_pressure(self, game, pos, now):
        target = float(game.plate_pressed(pos))
        delayed = self.plate_delays.get(pos)
        if delayed:
            until, previous = delayed
            if now < until:
                target = previous
            else:
                self.plate_delays.pop(pos)
                self.device_progress(self.plate_motions, pos, target, until, PLATE_SECONDS)
        return self.device_progress(self.plate_motions, pos, target, now, PLATE_SECONDS)

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

    def hud_item(self, kind, x, y):
        if self.top_down:
            self.topdown_art.draw(TOPDOWN_ITEMS[kind], x, y + 11, 24)
        else:
            self.item(kind, x, y, 0.19)

    def draw_worker_completion(self, x, y, elapsed):
        phase = min(1, elapsed / .43)
        reach = sin(pi * phase)
        if self.top_down:
            self.topdown_art.draw("worker_down_idle", x, y + 24, 52, height_scale=1 - reach * .12)
        else:
            self.art.draw("worker_sw_idle", x, y, .34, height_scale=1 - reach * .12)
        if phase < 1:
            for side in (-1, 1):
                dust(x + side * (9 + reach * 12), y + 24, phase, direction=(side, 0), size=.65)

    def support_height(self, game, pos):
        """발판 위 물건과 캐릭터의 접점을 지지면에 맞춘다."""
        if pos in game.level.plates:
            pressed = self.plate_depths.get(pos, float(game.plate_pressed(pos))) if self.gate_game is game else float(game.plate_pressed(pos))
            up, down = self.art.surface_height("plate_up"), self.art.surface_height("plate_down")
            return up + (down - up) * pressed
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
        dx, dy = self.board_offset
        x, y = x - dx, y - dy
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
                    if not self.art.hit_test(*mask[:4], (x, y), *mask[4:]):
                        continue
                return pos
        return self.projection(game.level).pick(x, y)

    def sprite_hit_region(self, pos, sprite, sx, sy, scale, flip=False, height_scale=1.0, rotation=0, rows=None):
        region = (pos, self.art.bounds(sprite, sx, sy, scale, flip, height_scale, rotation, rows))
        self.hit_regions.append(region)
        mask = (sprite, sx, sy, scale, flip, height_scale, rotation)
        self.hit_masks[region] = (*mask, rows) if rows else mask

    def navigation_overlay(self, game, projection):
        if game.failed or game.state.cleared:
            return
        target, path = self.navigation.target, self.navigation.path
        color = GOLD
        hovered = self.pick_cell(game, *self.mouse_position) if self.mouse_position else None
        if hovered is not None:
            target = hovered
            path = find_path(game, target, approach_device=True)
            if path is not None and target in game.level.solid_devices:
                target = path[-1] if path else game.state.player
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
        self.tile_outline(projection, *projection.screen(target), projection.half_width - 5,
                          int(projection.half_height) - 3, color)
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
        dx, dy = self.board_offset
        left, bottom = left - dx, bottom - dy
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
        ready_target = game.interaction_target()
        solid_devices = level.solid_devices
        targets = {pos: "함정 설치" for pos in level.traps - state.installed}
        targets.update({pos: "병사 배치" for pos in level.posts - state.soldiers})
        targets.update({pos: "병사 조립" for pos in level.benches})
        targets.update({pos: "뼈 투입구" for pos in level.chutes})
        mirrors = mirror_cells(level, state)
        targets.update({pos: "이동 거울 · Shift+방향키" if pos in state.movable_mirrors else "거울 회전"
                        for pos in mirrors})
        targets.update({pos: "인부 회수" if pos in state.workers else "인부 배치"
                        for pos in level.jobs - level.echo_links.keys()})
        targets.update({pos: "발걸음 기록" for pos in level.echo_links})
        if not state.active:
            targets.update({pos: "레버 가동" for pos in level.levers})
        targets.update({pos: ITEM_NAMES[kind] for pos, kind in state.items.items()})
        for pos in sorted(targets, key=lambda cell: (sum(cell), cell)):
            # 탑다운 기록 발판의 표시등을 금색 표식으로 가리지 않는다.
            if self.top_down and pos in level.echo_links:
                continue
            sx, sy = projection.screen(pos)
            # 같은 칸 캐릭터까지 포함해 표식이 머리나 물건에 가려지지 않게 한다.
            top = max((rect[3] for cell, rect in self.hit_masks if cell == pos), default=sy + 8)
            y = min(top + 15, BOARD_TOP - 15)
            if self.top_down and pos in mirrors:
                sx += projection.half_width * .70
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
            ready = pos == ready_target
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
            if hovered in solid_devices:
                self.interaction_hint = f"{targets[hovered]} · 옆 칸에서 E"
            elif level.id == "stage_01":
                self.interaction_hint = f"상호작용 대상: {targets[hovered]} · 해당 칸에서 E"
            else:
                self.interaction_hint = targets[hovered]

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

    def push_shake_offset(self, now):
        """짧은 흔들림을 겹쳐도 최대 변위를 제한하고 새 밀기 시작점에서 튀지 않게 한다."""
        self.rubble_impulses = [start for start in self.rubble_impulses if now - start < PUSH_SECONDS]
        x, y = 0.0, 0.0
        for start in self.rubble_impulses:
            age = max(0, now - start)
            strength = (1 - age / PUSH_SECONDS) ** 2
            x += 4.5 * strength * sin(age * 66)
            y += 2.8 * strength * sin(age * 87)
        return round(max(-4, min(4, x))), round(max(-3, min(3, y)))

    def board(self, game):
        now = self.now()
        self.board_offset = self.push_shake_offset(now)
        if self.board_offset == (0, 0):
            self._draw_board(game, now)
            return
        dx, dy = self.board_offset
        viewport = p.SDL_Rect()
        p.SDL_RenderGetViewport(p.renderer, byref(viewport))
        # SDL은 위쪽이 원점이다. 바닥, 광원 메시와 스프라이트를 함께 이동한다.
        shifted = p.SDL_Rect(viewport.x + dx, viewport.y - dy, viewport.w, viewport.h)
        p.SDL_RenderSetViewport(p.renderer, shifted)
        try:
            self._draw_board(game, now)
        finally:
            p.SDL_RenderSetViewport(p.renderer, viewport)

    def _draw_board(self, game, now):
        level, state = game.level, game.state
        if self.mirror_game is not game:
            self.mirror_game, self.mirror_motions = game, {}
        mirrors = mirror_cells(level, state)
        mirror_positions = {pos: self.mirror_position(pos, now) for pos in mirrors}
        mirror_rotations = {pos: self.mirror_rotation(game, pos, now) for pos in mirrors}
        rubble_positions = {self.rubble_pose(game, pos, now)[0] for pos in state.rubble}
        rubble_contacts = []
        beam_segments, powered_receivers = trace_display_magic(
            level, state, mirror_rotations, mirrors=mirror_positions, rubble=rubble_positions,
            source_reach=TOPDOWN_SOURCE_REACH if self.top_down else None, rubble_contacts=rubble_contacts)
        self.receiver_feedback.observe(game, powered_receivers, now)
        logical_power = trace_magic(level, state)[1]
        gate_statuses = {pos: (('open' if control in logical_power else
                               'held' if pos == state.player or pos in state.items else 'closed')
                              if control in level.receivers else game.gate_status(pos, state))
                         for pos, control in level.gates.items()}
        if self.gate_game is not game:
            self.reset_gates()
            self.reset_plates()
            self.gate_game = game
            self.room_debris = RoomDebris(game, now)
            self.room_atmosphere = RoomAtmosphere(level, now)
        gate_openings = {}
        self.plate_depths = {pos: self.plate_pressure(game, pos, now) for pos in level.plates}
        for pos, control in level.gates.items():
            opening = float(gate_statuses[pos] != "closed")
            if control in level.receivers:
                opening = float(control in powered_receivers or gate_statuses[pos] == "held")
            if gate_statuses[pos] == "open" and control in self.plate_delays:
                # 블록이 발판에 닿기 전까지 격자의 표시 위치를 유지한다.
                opening = self.plate_delays[control][1]
            gate_openings[pos] = (opening if control in level.timed_echoes
                                  else self.gate_opening(pos, opening, now))
        if self.top_down:
            if self.topdown_art is None:
                self.topdown_art = TopDownArt()
            draw_topdown_board(self, game, self.projection(level), now, beam_segments, powered_receivers,
                               mirror_rotations, mirror_positions, gate_statuses, gate_openings, rubble_contacts)
            return
        rubble_draws = {}
        mirror_draws = {}
        if level.gates:
            self.art.load_gates()
        scene = scene_for(level)
        if scene:
            for pack in scene["packs"]:
                self.art.load_theme(pack)
            self.art.load_walls(scene.get("wall_pack", scene["packs"][0]))
            for mount in scene.get("wall_mounts", ()):
                self.art.load_walls(mount["sprite"].split("_", 1)[0])
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
                        | fixed_devices(level, state) | set(level.chutes.values())
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
                    installed = pos in state.installed and self.work_feedback.contacted(pos, "install", now)
                    tile = "trap_installed" if installed else "trap_broken"
                    tint = None
                    if state.active and self.work_feedback.contacted(pos, "trap", now):
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

                for cells, sprite, label in (
                        (mirrors, "mirror", "이동 거울" if pos in state.movable_mirrors
                         else f"거울 {state.mirror_rotations.get(pos, 0) + 1}/4"),
                        (level.sources, "mana_source", "광원"),
                        (level.receivers, "mana_receiver", level.device_labels.get(pos, "") + (" 수신 완료" if pos in powered_receivers else " 수신 대기")),
                        (state.rubble, "push_rubble", "밀기 · 방향키"),
                        (level.jobs - level.echo_links.keys(), "helper_work" if pos in state.workers else "winch", level.device_labels.get(pos, "") + (" 인부 회수" if pos in state.workers else " 인부 배치"))):
                    if pos in cells:
                        # 잔해는 발판 상판을 그린 다음 얹는다. 같은 깊이의 장치보다 앞이다.
                        if sprite == "push_rubble":
                            position, height = self.rubble_pose(game, pos, now)
                            rx, ry = screen(position)
                            rubble_draws[(rx, ry)] = (pos, position, height)
                            draw_depth = max(sum(position), depth) if pos in level.plates else sum(position)
                            objects.append((draw_depth, 2, sprite, rx, ry))
                        elif sprite == "mirror":
                            position = mirror_positions[pos]
                            mx, my = screen(position)
                            mirror_draws[(mx, my)] = pos
                            objects.append((sum(position), 1, sprite, mx, my))
                        else:
                            objects.append((depth, 1, sprite, sx, sy))
                        if sprite != "push_rubble" or pos not in level.plates:
                            labels.append((pos, label))
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
                    plate_label = "잔해 적재" if pos in state.rubble else "눌림" if pressed else "발판"
                    labels.append((pos, f"{level.device_labels[pos]} {plate_label}"))
                elif pos in level.gates:
                    status = gate_statuses[pos]
                    objects.append((depth, 1, f"gate_{status}", sx, sy))
                    label = {"open": "열림", "held": "닫힘 대기", "closed": "닫힘"}[status]
                    if status == "open" and level.gates[pos] in level.timed_echoes:
                        label = "지금 통과"
                    labels.append((pos, f"{level.device_labels[pos]} {label}"))
                elif pos in level.levers:
                    objects.append((depth, 1, "lever_on" if state.active else "lever_off", sx, sy))
                    labels.append((pos, "레버"))
                elif pos in level.benches:
                    stored = state.bench_bones.get(pos, 0)
                    objects.append((depth, 1, "bench_one_bone" if stored else "bench_empty", sx, sy))
                    labels.append((pos, f"조립 {stored}/2"))
                if pos in state.items and not self.item_is_in_hands(game, pos, now):
                    objects.append((depth, 2, ITEM_SPRITES[state.items[pos]], sx, sy))
                if pos in state.soldiers:
                    objects.append((depth, 2, "soldier_deployed", sx, sy))

        draw_echo_marks(game, projection)
        for station, (seals, _) in level.echo_links.items():
            labels.append((station, recording_label(level, station)))
            if len(seals) > 1:
                labels.extend((seal, level.device_labels[gate]) for gate, seal in seals.items())
        for origin, pos in state.replay_workers.items():
            if state.echo is None or state.echo.origin != origin:
                sx, sy = screen(pos)
                objects.append((sum(pos), 2, "resting_recorded_worker", sx, sy))
        echo_pose = self.echo_motion.pose(game, now)
        if echo_pose:
            position, direction = echo_pose
            sx, sy = screen(position)
            objects.append((sum(position), 2, "echo_actor", sx, sy))

        if scene:
            for mount in scene.get("wall_mounts", ()):
                pos = tuple(mount["cell"])
                dx, dy = DIRECTIONS[mount["facing"]]
                sx, sy = screen((pos[0] + dx * .43, pos[1] + dy * .43))
                tall_wall = (pos[0] == 0 and dx == 1) or (pos[1] == 0 and dy == 1)
                sy += (140 if tall_wall else self.art.surface_height("wall_low_pier") + 25) * scale
                sprite = mount["sprite"]
                objects.append((sum(pos), 0.25, sprite, sx, sy))
                decor_draws[(sprite, sx, sy)] = scale * (.83 if tall_wall else .58)
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
        player = self.player_position(state.player, now)
        px, py = screen(player)
        # 같은 칸의 작업대나 배치한 병사와 구별되도록 약간 앞쪽에 선다.
        if state.player in state.soldiers | level.plates | level.gates.keys() | fixed_devices(level, state):
            px -= 9
            py -= 7
        objects.append((sum(player), 3, "player", px, py))
        for _, _, sprite, sx, sy in sorted(objects, key=lambda obj: obj[:2]):
            pos = state.player if sprite == "player" else projection.pick(sx, sy)
            if sprite == "push_rubble":
                pos, position, height = rubble_draws[(sx, sy)]
            decor_scale = decor_draws.get((sprite, sx, sy))
            if decor_scale is not None:
                kind = prop_kind(sprite)
                size = min(projection.half_width, self.art.manifest["sprites"][sprite]["height"] * decor_scale)
                height = 1 + self.room_atmosphere.banner(now) if kind == "treasure_banner" else 1
                if kind == "boss_throne":
                    self.room_atmosphere.throne_shadow(sx, sy, size, now)
                self.art.draw(sprite, sx, sy, decor_scale, height_scale=height)
                self.room_atmosphere.draw(kind, sx, sy, size, now, top_down=False)
                # 장식의 위쪽 그림이 뒤의 이동 칸/장치 클릭을 가로채지 않는다.
                continue
            # 논리 칸은 높이를 더하기 전에 결정해야 클릭 대상이 옆 칸으로 밀리지 않는다.
            if sprite == "player":
                sy += self.player_support_height(game, player) * scale
            elif sprite == "push_rubble":
                sy += height * scale
                self.draw_rubble_scrape(projection, pos, position, now)
            elif sprite in ITEM_SPRITES.values():
                sy += self.support_height(game, pos) * scale
                sy += self.chute_feedback.item_lift(pos, now) * 28 * scale
                sy += self.work_feedback.drop_lift(pos, now) * 22 * scale
            if sprite in ("plate_up", "plate_down"):
                pressed = self.plate_depths[pos]
                self.art.draw_plate(sx, sy, scale, pressed)
                self.sprite_hit_region(pos, "plate_up", sx, sy, scale)
                self.plate_hit_masks[self.hit_regions[-1]] = (sx, sy, scale, pressed)
                continue
            if sprite == "mirror":
                pos = mirror_draws[(sx, sy)]
                rotation = mirror_rotations[pos]
                self.art.draw(sprite, sx, sy, scale, rotation=rotation)
                self.draw_mirror_stop(projection, pos, (sx, sy + 56 * scale), now)
                self.sprite_hit_region(pos, sprite, sx, sy, scale, rotation=rotation)
                continue
            if sprite == 'mana_source':
                source_sprite, flip = self.art.source_pose(level.sources[pos])
                self.art.draw(source_sprite, sx, sy, scale, flip=flip)
                self.sprite_hit_region(pos, source_sprite, sx, sy, scale, flip=flip)
                continue
            if sprite.startswith("gate_"):
                self.gate(level, pos, sx, sy, scale, sprite.removeprefix("gate_"), gate_openings[pos])
                self.draw_gate_dust(projection, pos, now)
                continue
            if sprite == "resting_recorded_worker":
                self.art.draw(ITEM_SPRITES["soldier"], sx, sy, scale)
                continue
            if sprite == "echo_actor":
                if state.echo.origin in state.replay_workers:
                    self.art.draw("soldier_deployed", sx, sy, scale * .87, height_scale=self.echo_motion.stride(now))
                else:
                    draw_tinted(self.art, f"worker_{FACING[direction]}_idle", sx, sy, scale, (206, 150, 255))
                continue
            if sprite != "player":
                height = 1
                if sprite == "soldier_deployed":
                    height = self.work_feedback.soldier_height(pos, now)
                elif sprite == "lever_on":
                    progress = self.work_feedback.progress(pos, "lever", now)
                    if not self.work_feedback.contacted(pos, "lever", now):
                        sprite = "lever_off"
                    height = 1 - .11 * sin(pi * progress)
                if (sx, sy) in wall_tints and (sprite.startswith("wall_low") or "_wall_" in sprite):
                    draw_tinted(self.art, sprite, sx, sy, scale, wall_tints[(sx, sy)])
                else:
                    self.art.draw(sprite, sx, sy, scale, height_scale=height)
                if sprite == "trap_active":
                    trap_motion(sx, sy + projection.half_height * .32, projection.half_width, now)
                if sprite == "mana_receiver" and pos in powered_receivers:
                    self.receiver_feedback.draw(game, pos, sx, sy, scale, now)
                self.sprite_hit_region(pos, sprite, sx, sy, scale, height_scale=height)
                continue
            self.draw_iso_worker(game, projection, sx, sy, scale, now)

        self.room_debris.draw(projection, now)
        self.work_feedback.draw(projection, now)
        self.chute_feedback.draw(projection, now, lambda x, y, ratio: self.item("bone", x, y, scale * ratio),
                                 top_down=False)
        draw_echo_turn(game, projection, self.echo_motion, now)
        # 광선은 물체와 구별되는 높은 선으로 그리고 끝점도 현재 상태에서 계산한다.
        for start, end in beam_segments:
            x1,y1=screen(start); x2,y2=screen(end)
            edge, core = (157, 72, 216), (244, 185, 255)
            for offset,color in ((-1,edge),(0,core),(1,edge)):
                line(x1,y1+MAGIC_BEAM_HEIGHT*scale+offset,x2,y2+MAGIC_BEAM_HEIGHT*scale+offset,color)
        beam_contacts(projection, rubble_contacts, now, height=MAGIC_BEAM_HEIGHT * scale)
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
                color = {"open": TEAL, "held": GOLD, "closed": RED}[gate_statuses[pos]]
            elif pos in level.plates:
                color = TEAL if game.plate_pressed(pos, state) else GOLD
            elif pos in level.receivers:
                color = TEAL if pos in powered_receivers else MUTED
                if pos in powered_receivers:
                    box(sx - width / 2, sy - 28, sx + width / 2, sy - 6, TEAL, filled=False)
            self.text(sx - width / 2 + 5, sy - 17, label, 16, color)
            self.hit_regions.append((pos, (sx - width / 2, sy - 28, sx + width / 2, sy - 6)))
        self.interaction_markers(game, projection)
        if self.show_coordinates:
            self.coordinate_overlay(level, projection)
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
        if hint is None or self.tutorial_hidden:
            return
        if hint.target is not None:
            projection = self.projection(game.level)
            sx, sy = projection.screen(hint.target)
            dx, dy = self.board_offset
            sx, sy = sx + dx, sy + dy
            color = TEAL if game.state.player == hint.target else GOLD
            for inset in (3, 5):
                self.tile_outline(projection, sx, sy, projection.half_width - inset,
                                  int(projection.half_height) - inset // 2, color)
            # 목표 안내도 해당 타일로 이동하는 클릭 영역이다.
            bounds = (sx - 66, sy - 59, sx + 66, sy - 33)
            box(*bounds, (25, 40, 42))
            box(*bounds, color, filled=False)
            self.centered(sx, sy - 46, hint.target_label, 16, color)
            self.hit_regions.append((hint.target, (bounds[0] - dx, bounds[1] - dy,
                                                   bounds[2] - dx, bounds[3] - dy)))
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
        if game.state.recording:
            return game.context_action(), GOLD
        if game.repair_percent == 100:
            return "복구 완료 · 출구로 돌아가세요", TEAL
        if self.interaction_hint:
            return self.interaction_hint, GOLD
        level = game.level
        targets = (level.traps | level.benches | level.posts | level.levers | level.jobs
                   | level.chutes.keys() | game.state.items.keys())
        if game.can_interact() or game.state.player in targets:
            return game.context_action(), TEAL if game.can_interact() else MUTED
        quiet = {
            INTERACTION_HELP, "현재 서 있는 칸입니다.",
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
            self.hud_item(state.carrying, 940, BOARD_TOP + 8)
        self.repair_progress(game, 1000, 200)

        context, color = self.play_context(game)
        if not draw_worker_status(self, game, context, color) and context:
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
        box(0, 0, WIDTH, HEIGHT, background)
        self.text(32, HEIGHT - 36, "용사가 지나간 자리", 32)
        self.text(450, HEIGHT - 36, level.title, 22)
        self.text(WIDTH - 190, HEIGHT - 36, f"단계 {index + 1:02d} / {total:02d}", 22, GOLD)
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
            self.hud_item(state.carrying, 940, BOARD_TOP + 5)
        diamond(982, BOARD_TOP + 17, 6, 6, None, GOLD)
        self.text(997, BOARD_TOP + 17, "상호작용 대상", 13, GOLD)
        self.repair_progress(game, 1120, 110)

        box(32, 48, WIDTH - 32, BOARD_BOTTOM, (41, 55, 58))
        context = self.interaction_hint or game.context_action()
        self.text(48, 80, context, 18, RED if game.failed else TEAL)
        self.text(48, 59, game.message, 16, INK)
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

        axes = "x 오른쪽 / y 아래" if self.top_down else "x 오른쪽 아래 / y 왼쪽 아래"
        self.text(34, 32, f"좌클릭  이동    우클릭  취소    WASD / 방향키  이동    개발용 1~{total} 방 이동 · F2 좌표    (x,y): {axes}", 13, MUTED)
        self.text(34, 12, "E / Space  상호작용·내려놓기·다음 방(완료 후)    Z / Backspace  되돌리기    R  재시작    Esc  일시정지", 13, MUTED)


def run(levels, index=0, smoke_frames=None, *, show_title=True, top_down=False):
    # 글꼴 오류는 SDL 창을 열기 전에 보고한다.
    font_path()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    front_end = None
    music = None
    try:
        if not p.window or not p.renderer:
            raise RuntimeError("SDL 게임 창 또는 렌더러를 만들 수 없습니다.")
        view = View()
        view.top_down = top_down
        front_end = FrontEnd(show_title)
        music = BackgroundMusic()
        play_menu = PlayMenu()
        feedback = StageFeedback()
        game = Game(levels[index])

        def next_room():
            nonlocal game, index
            index = (index + 1) % len(levels)
            game = Game(levels[index])
            view.reset_player()
            view.navigation.cancel()
            view.mouse_position = None
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
            if front_end.screen == "playing":
                play_menu.offer(game, view)
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
                        play_menu.seen_devices.clear()
                        view.reset_player()
                        view.navigation.cancel()
                        view.mouse_position = None
                    if result is not None:
                        # 전환 뒤 입력은 무시하되 같은 묶음의 창 닫기는 처리한다.
                        screen_changed = True
                elif play_menu.active:
                    result = play_menu.handle(event)
                    if result in ("resume", "restart", "title"):
                        play_menu.close(view)
                        if result != "resume":
                            view.navigation.cancel()
                            view.reset_player()
                            view.reset_gates()
                            view.reset_plates()
                            if result == "restart":
                                game.restart()
                                feedback.enter(game, view.now())
                            else:
                                front_end.activate("title")
                    if result is not None:
                        screen_changed = True
                elif event.type == p.SDL_KEYDOWN and event.key == p.SDLK_ESCAPE:
                    play_menu.open(view)
                    screen_changed = True
                elif event.type == p.SDL_MOUSEMOTION:
                    view.mouse_position = (event.x, HEIGHT - 1 - event.y)
                elif event.type == p.SDL_MOUSEBUTTONDOWN:
                    view.mouse_position = (event.x, HEIGHT - 1 - event.y)
                    if event.button == p.SDL_BUTTON_RIGHT:
                        if view.navigation.active:
                            game.message = "자동 이동을 취소했습니다."
                        view.navigation.cancel()
                    elif event.button == p.SDL_BUTTON_LEFT:
                        if game.state.cleared:
                            if feedback.next_button(index, len(levels)).contains(view.mouse_position):
                                next_room()
                                screen_changed = True
                        else:
                            target = view.pick_cell(game, *view.mouse_position)
                            if target is not None:
                                now = view.now()
                                ready_at = view.motion[2] + view.move_seconds if view.motion else now
                                view.navigation.start(game, target, now, ready_at=ready_at)
                elif event.type == p.SDL_KEYDOWN:
                    if event.key in (p.SDLK_b, p.SDLK_q):
                        continue
                    view.navigation.cancel()
                    if event.key == p.SDLK_F2:
                        view.show_coordinates = not view.show_coordinates
                    elif event.key in stage_keys and stage_keys[event.key] < len(levels):
                        index = stage_keys[event.key]
                        game = Game(levels[index])
                        view.reset_player()
                        view.hit_regions.clear()
                        view.hit_masks.clear()
                        view.mouse_position = None
                        screen_changed = True
                    elif event.key in (p.SDLK_z, p.SDLK_BACKSPACE):
                        if game.undo():
                            view.reset_player()
                            view.gate_motions.clear()
                            view.reset_plates()
                    elif event.key == p.SDLK_r:
                        game.restart()
                        feedback.enter(game, view.now())
                        view.reset_player()
                        view.reset_gates()
                        view.reset_plates()
                    elif event.key in (p.SDLK_e, p.SDLK_SPACE) and game.state.cleared:
                        next_room()
                        screen_changed = True
                    elif event.key in actions:
                        action = actions[event.key]
                        if action in DIRECTIONS and p.SDL_GetModState() & p.KMOD_SHIFT:
                            action = f"push_{action}"
                        previous = game.state
                        changed = game.act(action)
                        direction = PUSH_ACTIONS.get(action, action)
                        if direction in FACING and changed:
                            view.animate_move(game, previous, direction)
                        if changed:
                            view.animate_devices(game, previous)
                            if game.state.cleared:
                                screen_changed = True
                        elif action == "interact":
                            view.chute_feedback.blocked(game, view.now())
            # 이미 보간 중인 한 칸이 끝난 뒤에만 다음 자동 이동을 실행한다.
            if front_end.screen == "playing":
                play_menu.offer(game, view)
            now = view.now()
            front_end.update(perf_counter())
            if running:
                music.update(front_end.screen, quiet=play_menu.active)
            if (running and front_end.screen == "playing" and not play_menu.active
                    and (view.motion is None or now >= view.motion[2] + view.move_seconds)):
                previous = game.state
                action = view.navigation.tick(game, now)
                if action is not None:
                    view.animate_move(game, previous, action)
                    view.animate_devices(game, previous)
            if front_end.screen == "playing":
                feedback.update(game, now)
                view.tutorial_hidden = play_menu.mode == "device"
                view.draw(game, index, len(levels))
                if play_menu.active:
                    play_menu.draw(view, game)
                else:
                    feedback.draw(view, game, index, len(levels))
            else:
                front_end.draw(view)
            p.update_canvas()
            p.SDL_SetWindowTitle(p.window, "용사가 지나간 자리 — 기초 프로토타입".encode("utf-8"))
            frames += 1
            if smoke_frames is not None and frames >= smoke_frames:
                running = False
    finally:
        if music:
            music.close()
        if front_end:
            front_end.close()
        if view:
            view.close()
        p.close_canvas()
