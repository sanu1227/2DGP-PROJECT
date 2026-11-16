"""탑다운 격자에 퍼즐 상태와 전용 스프라이트를 표시한다."""

import json
from math import hypot, pi
from pathlib import Path

import pico2d.pico2d as p

from game.levels import DIRECTIONS
from game.themes import scene_for
from game.topdown_terrain import Light, draw_shadows, draw_terrain, materials_for
from game.worker_view import ECHO_COLOR, draw_echo_marks, recording_label


ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "topdown_v2"
INK = (239, 237, 219)
TEAL = (112, 216, 190)
GOLD = (231, 190, 108)
RED = (232, 119, 105)
VIOLET = (184, 103, 242)
ITEMS = {"part": "part", "bone": "bone", "soldier": "soldier_carried"}
FACINGS = {"ne": "up", "se": "right", "sw": "down", "nw": "left"}
SOURCE_ANGLES = {"up": 0, "right": -pi / 2, "down": pi, "left": pi / 2}
DECOR = {
    "forge_anvil": "anvil", "crypt_sarcophagus": "sarcophagus", "crypt_candles": "candles",
    "archive_book_pile": "books", "sewer_hand_pump": "hand_pump", "sewer_pipe_elbow": "elbow_pipe",
    "sewer_water_barrel": "water_barrel", "treasury_locked_coffer": "treasure",
    "treasury_treasure_banner": "treasure_banner", "boss_throne": "throne", "boss_brazier": "brazier",
    "forge_mount_lamp": "lantern", "forge_mount_tools": "tool_rack", "forge_mount_vent": "air_vent",
    "crypt_mount_sconce": "candle_sconce", "crypt_mount_banner": "crypt_banner", "crypt_mount_crest": "crest",
    "archive_mount_sconce": "crystal_sconce", "archive_mount_banner": "archive_banner",
    "sewer_mount_lamp": "lantern", "sewer_mount_pipes": "wall_pipes",
}
STAGE_THEMES = {f"stage_{stage:02d}": stage for stage in range(1, 9)}
WORKSHOP_SPRITES = {name: f"workshop_{name}" for name in (
    "trap_broken", "trap_installed", "trap_active", "exit_closed", "exit_ready",
    "lever_off", "lever_on", "part", "anvil", "lantern", "candle_sconce", "tool_rack",
)}
ROOM_SPRITES = WORKSHOP_SPRITES | {name: f"depth_{name}" for name in (
    "bone", "soldier_carried", "soldier_deployed", "post_empty",
    "bench_empty", "bench_bone", "plate_up", "plate_down", "gate_closed", "gate_open", "rubble",
    "chute_outlet", "chute_inlet", "source", "receiver", "mirror_base", "winch", "helper",
    "crystal_sconce", "lantern", "candle_sconce", "air_vent", "wall_pipes", "crest",
    "sarcophagus", "candles", "books", "throne", "hand_pump", "elbow_pipe", "water_barrel",
    "brazier", "treasure", "treasure_banner", "crypt_banner", "archive_banner",
)}
PROP_LIGHTS = {
    "candle_sconce": (2.06, 1.78, (249, 169, 99), 119, .24),
    "candles": (1.75, 1.54, (250, 177, 104), 104, .23),
    "lantern": (2.42, 2.05, (248, 164, 80), 132, .24),
    "brazier": (2.56, 2.20, (253, 128, 73), 143, .27),
    "crystal_sconce": (2.26, 1.92, (115, 192, 247), 120, .20),
}
RAISED_DEVICES = frozenset({
    "lever_off", "lever_on", "bench_empty", "bench_bone", "soldier_deployed",
    "chute_inlet", "source", "mirror_base", "receiver", "winch", "helper",
})


class TopDownArt:
    def __init__(self):
        self.atlases = {}
        manifest = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.sprites = manifest["sprites"]
        self.files = manifest["atlases"]

    def close(self):
        for atlas in self.atlases.values():
            p.SDL_DestroyTexture(atlas.texture)
            atlas.texture = None
        self.atlases.clear()

    def draw(self, name, x, y, size, *, angle=0, opacity=1, height_scale=1):
        atlas_name, left, top, width, height = self.sprites[name]
        atlas = self.atlases.get(atlas_name)
        if atlas is None:
            atlas = self.atlases[atlas_name] = p.load_image(str(ASSET_ROOT / self.files[atlas_name]))
        scale = size / max(width, height)
        clip = (left, atlas.h - top - height, width, height)
        if opacity != 1:
            atlas.opacify(opacity)
        try:
            if angle:
                atlas.clip_composite_draw(*clip, angle, "", x, y, width * scale, height * scale * height_scale)
            else:
                atlas.clip_draw(*clip, x, y, width * scale, height * scale * height_scale)
        finally:
            if opacity != 1:
                atlas.opacify(1)


def rectangle(left, bottom, right, top, color, filled=True):
    p.draw_rectangle(round(left), round(bottom), round(right), round(top), *color, filled=filled)


def device_entries(game, gate_statuses, powered, exit_ready, plate_depths):
    """장치별 그림과 상태 이름을 계산한다. 발판은 같은 칸의 배출구 위에 표시한다."""
    level, state = game.level, game.state
    entries = {}
    for pos in level.traps:
        frame, label = ("active", "가동") if state.active else (
            ("installed", "설치") if pos in state.installed else ("broken", "파손"))
        entries[pos] = f"trap_{frame}", label, RED if state.active else GOLD
    for pos in level.posts:
        assigned = pos in state.soldiers
        entries[pos] = ("soldier_deployed", "배치 완료", TEAL) if assigned else ("post_empty", "초소", GOLD)
    entries[level.exit] = ("exit_ready", "출구", TEAL) if exit_ready else ("exit_closed", "출구", INK)
    for pos in level.levers:
        entries[pos] = ("lever_on" if state.active else "lever_off"), "레버", GOLD
    for pos in level.benches:
        count = state.bench_bones.get(pos, 0)
        entries[pos] = ("bench_bone" if count else "bench_empty"), f"조립 {count}/2", GOLD
    for pos in level.chutes.values():
        entries[pos] = "chute_outlet", "배출", GOLD
    for pos in level.chutes:
        entries[pos] = "chute_inlet", f"{level.device_labels[pos]} 투입구", GOLD
    for pos in level.plates:
        pressed = plate_depths[pos] >= .5
        entries[pos] = ("plate_down" if pressed else "plate_up"), level.device_labels[pos], TEAL if pressed else GOLD
    for pos, status in gate_statuses.items():
        label, color = {"open": ("열림", TEAL), "held": ("대기", GOLD), "closed": ("닫힘", RED)}[status]
        if status == "open" and level.gates[pos] in level.timed_echoes:
            label = "통과"
        entries[pos] = "gate_open", f"{level.device_labels[pos]} {label}", color
    for pos in level.sources:
        entries[pos] = "source", "광원", GOLD
    for pos in level.mirrors:
        entries[pos] = "mirror_base", "거울", GOLD
    for pos in level.receivers:
        entries[pos] = "receiver", f"{level.device_labels[pos]} 수신" if pos in powered else level.device_labels[pos], (
            TEAL if pos in powered else INK)
    for pos in level.jobs:
        working = pos in state.workers
        label = level.device_labels[pos]
        if pos in level.echo_links:
            entries[pos] = None, recording_label(level, pos), ECHO_COLOR
        else:
            entries[pos] = ("helper" if working else "winch"), label, TEAL if working else GOLD
    for seals, _ in level.echo_links.values():
        for gate, seal in seals.items():
            entries[seal] = None, level.device_labels[gate], ECHO_COLOR
    return entries


def draw_mirror(view, board, pos, rotation):
    # 거울 면과 앞면 방향을 모델과 같은 지도 좌표에서 투영한다.
    x, y = pos
    tx, ty = view.art.mirror_basis(rotation)
    nx, ny = -ty, tx
    a = board.screen((x - tx * .36, y - ty * .36))
    b = board.screen((x + tx * .36, y + ty * .36))
    for offset in range(-3, 4):
        p.draw_line(a[0], a[1] + offset, b[0], b[1] + offset, 88, 64, 58)
    p.draw_line(*a, *b, 220, 230, 220)
    tip = board.screen((x + nx * .24, y + ny * .24))
    for sign in (-1, 1):
        tail = board.screen((x + nx * .13 + sign * tx * .07, y + ny * .13 + sign * ty * .07))
        p.draw_line(*tip, *tail, *TEAL)


def source_nozzle(level, start, end):
    """공유 광선의 첫 선분을 탑다운 광원 그림의 발사구에 맞춘다."""
    for (x, y), facing in level.sources.items():
        dx, dy = DIRECTIONS[facing]
        offset_x, offset_y = start[0] - x, start[1] - y
        parallel = abs(offset_x * dy - offset_y * dx) < 1e-6
        distance = offset_x * dx + offset_y * dy
        outgoing = (end[0] - start[0]) * dx + (end[1] - start[1]) * dy
        if parallel and 0 <= distance < .7 and outgoing > 0:
            return x + dx * .29, y + dy * .29
    return start


def room_props(scene):
    """실내 쪽 벽면을 기준으로 소품과 조명, 벽감의 위치를 맞춘다."""
    props, lights, recesses = [], [], {}
    if scene is None:
        return props, lights, recesses
    for mounted, entries in ((True, scene.get("wall_mounts", ())), (False, scene["decorations"])):
        for entry in entries:
            x, y = entry["cell"]
            dx, dy = DIRECTIONS[entry["facing"]]
            key = entry["sprite"]
            sprite = DECOR[key.rsplit("_", 1)[0] if mounted else key]
            if not mounted:
                recesses[(x, y)] = (dx, dy)
            offset = .41 if mounted else .05
            props.append((sprite, (x + dx * offset, y + dy * offset), .38 if mounted else entry["scale"]))
            if sprite in PROP_LIGHTS:
                lights.append(Light((x + dx * .73, y + dy * .73), *PROP_LIGHTS[sprite]))
    return props, lights, recesses


def room_lights(level, lights, powered, exit_ready):
    lights.extend(Light(pos, 1.25, 1.12, (178, 94, 240), 60) for pos in level.sources)
    lights.extend(Light(pos, 1.48, 1.30, (192, 125, 250), 104) for pos in sorted(powered))
    if exit_ready:
        lights.append(Light(level.exit, 1.34, 1.15, (64, 202, 151), 103))
    return tuple(lights)


def draw_board(view, game, board, now, beam_segments, powered, rotations, gate_statuses, gate_openings):
    level, state = game.level, game.state
    art = view.topdown_art
    size, half = board.cell_size, board.half_width
    stage = STAGE_THEMES.get(level.id, 1)
    scene = scene_for(level)
    ready = (state.installed == level.traps and (not level.traps or state.active)
             and state.soldiers == level.posts and state.carrying is None)
    entries = device_entries(game, gate_statuses, powered, ready, view.plate_depths)
    workshop = stage == 1
    sprites = WORKSHOP_SPRITES if workshop else ROOM_SPRITES
    props, prop_lights, recesses = room_props(scene)
    lights = room_lights(level, prop_lights, powered, ready)
    player = view.player_position(state.player, now)
    rubble = [view.rubble_pose(game, pos, now) for pos in sorted(state.rubble)]
    view.hit_regions.clear()
    view.hit_masks.clear()
    view.gate_hit_masks.clear()
    view.gate_inlets.clear()
    view.plate_hit_masks.clear()
    view.action_badge_bounds = None

    background = tuple(scene["background"]) if scene else (19, 27, 32)
    draw_terrain(art, board, level, materials_for(stage), lights, background, now, recesses)
    draw_echo_marks(game, board)
    raised = [pos for pos, (sprite, _, _) in entries.items() if sprite in RAISED_DEVICES]
    draw_shadows(board, player, [*raised, *state.items, *(pos for pos, _ in rubble)])

    for sprite, pos, scale in props:
        x, y = board.screen(pos)
        plinth = {"anvil": "workshop_plinth", "throne": "room_08_plinth"}.get(sprite)
        if plinth:
            art.draw(plinth, x, y, size * (.83 if workshop else .85))
            y += size * .06
        art.draw(sprites.get(sprite, sprite), x, y, size * scale)

    for pos, (sprite, _, _) in entries.items():
        if sprite is None:
            continue
        sx, sy = board.screen(pos)
        asset = sprites.get(sprite, sprite)
        if pos in level.gates:
            x, y = pos
            across_x = sum(cell in level.walls for cell in ((x - 1, y), (x + 1, y)))
            across_y = sum(cell in level.walls for cell in ((x, y - 1), (x, y + 1)))
            angle = 0 if across_x > across_y else pi / 2
            art.draw(asset, sx, sy, size * .94, angle=angle)
            if gate_openings[pos] < 1:
                art.draw(sprites.get("gate_closed", "gate_closed"), sx, sy, size * .94,
                         angle=angle, opacity=1 - gate_openings[pos])
        elif pos in level.sources:
            art.draw(asset, sx, sy, size * .68, angle=SOURCE_ANGLES[level.sources[pos]])
        elif pos in state.soldiers:
            art.draw(sprites.get("post_empty", "post_empty"), sx, sy, size * .79)
            art.draw(asset, sx, sy, size * .72)
        else:
            art.draw(asset, sx, sy, size * .82)

    echo_pose = view.echo_motion.pose(game, now)
    if echo_pose:
        position, direction = echo_pose
        sx, sy = board.screen(position)
        p.draw_circle(sx, sy, round(size * .33), *ECHO_COLOR)
        art.draw(f"worker_{direction}_idle", sx, sy, size * .75, opacity=.67)

    for pos, kind in state.items.items():
        sx, sy = board.screen(pos)
        sprite = ITEMS[kind]
        art.draw(sprites.get(sprite, sprite), sx + (size * .22 if pos in entries else 0), sy + size * .04,
                 size * .54)
    for position, height in rubble:
        sx, sy = board.screen(position)
        art.draw(sprites.get("rubble", "rubble"), sx, sy + min(height, 24) * size / 256, size * .74)

    px, py = board.screen(player)
    p.draw_circle(px, py, round(size * .38), *TEAL)
    facing = FACINGS[view.facing]
    pose = "carry" if state.carrying else (
        "walk_a" if now - view.motion[2] < .09 else "walk_b") if view.motion else "idle"
    tired = view.fatigue(game)
    art.draw(f"worker_{facing}_{pose}", px, py, size * .75,
             height_scale=view.worker_height(tired, now))
    if state.carrying:
        dx, dy = DIRECTIONS[facing]
        sprite = ITEMS[state.carrying]
        art.draw(sprites.get(sprite, sprite), px + dx * size * .27, py - dy * size * .27, size * .32)
    head = py + size * .35
    badge_x = px
    if state.echo and state.echo.position == (state.player[0], state.player[1] - 1):
        badge_x -= size * .85
    view.place_action_badge(game, badge_x, head, now)
    view.worker_effort((px - size * .3, py - size * .27, px + size * .3, head), tired, now)

    for start, end in beam_segments:
        x1, y1 = board.screen(source_nozzle(level, start, end))
        x2, y2 = board.screen(end)
        length = max(1, hypot(x2 - x1, y2 - y1))
        nx, ny = (y1 - y2) / length, (x2 - x1) / length
        for offset, color in ((-1, VIOLET), (0, (247, 202, 255)), (1, VIOLET)):
            p.draw_line(x1 + nx * offset, y1 + ny * offset, x2 + nx * offset, y2 + ny * offset, *color)
    for pos in level.mirrors:
        draw_mirror(view, board, pos, rotations[pos])
    for pos in powered:
        progress = view.receiver_feedback.progress(game, pos, now)
        sx, sy = board.screen(pos)
        p.draw_circle(sx, sy, max(2, round(size * .18)), *VIOLET, filled=False)
        if progress < 1:
            p.draw_circle(sx, sy, max(2, round(size * (.18 + progress * .2))), *VIOLET, filled=False)

    for pos, (_, label, color) in entries.items():
        sx, sy = board.screen(pos)
        sy += half - 10 if level.sources.get(pos) == "down" else 10 - half
        width = min(size - 4, len(label) * 12 + 8)
        rectangle(sx - width / 2, sy - 8, sx + width / 2, sy + 8, (24, 35, 40))
        view.centered(sx, sy, label, 13, color)
    view.interaction_markers(game, board)
    if view.show_coordinates:
        view.coordinate_overlay(level, board)
    view.navigation_overlay(game, board)
    view.action_badge(game)
