"""탑다운 격자에 퍼즐 상태와 전용 스프라이트를 표시한다."""

import json
from math import hypot, pi, sin
from pathlib import Path

import pico2d.pico2d as p

from game.device_outline import DeviceOutlines
from game.layout import HEIGHT
from game.levels import DIRECTIONS
from game.magic import mirror_output
from game.mechanics import mirror_cells
from game.play_effects import beam_contacts, trap_motion
from game.themes import scene_for
from game.topdown_terrain import Light, draw_shadows, draw_terrain, materials_for
from game.worker_view import ECHO_COLOR, draw_echo_trail, draw_echo_turn, recording_label


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
    "chute_outlet", "chute_inlet", "source", "receiver", "receiver_powered", "mirror_base", "winch", "helper",
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
    "chute_inlet", "source", "mirror_base", "receiver", "receiver_powered", "winch", "helper",
})


class TopDownArt:
    def __init__(self):
        self.atlases = {}
        self.outlines = DeviceOutlines()
        manifest = json.loads((ASSET_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.sprites = manifest["sprites"]
        self.files = manifest["atlases"]

    def close(self):
        self.outlines.close()
        for atlas in self.atlases.values():
            p.SDL_DestroyTexture(atlas.texture)
            atlas.texture = None
        self.atlases.clear()

    def draw(self, name, x, y, size, *, angle=0, opacity=1, height_scale=1, outline=0,
             inset=(0, 0)):
        atlas_name, left, top, width, height = self.sprites[name]
        atlas = self.atlases.get(atlas_name)
        if atlas is None:
            atlas = self.atlases[atlas_name] = p.load_image(str(ASSET_ROOT / self.files[atlas_name]))
        scale = size / max(width, height)
        margin_x, margin_y = round(width * inset[0]), round(height * inset[1])
        left, top = left + margin_x, top + margin_y
        width, height = width - 2 * margin_x, height - 2 * margin_y
        clip = (left, atlas.h - top - height, width, height)
        draw_width, draw_height = width * scale, height * scale * height_scale
        if outline:
            rect = p.to_sdl_rect(x - draw_width / 2, y - draw_height / 2, draw_width, draw_height)
            self.outlines.draw(ASSET_ROOT / self.files[atlas_name], (left, top, width, height), rect, angle, outline)
        if opacity != 1:
            atlas.opacify(opacity)
        try:
            if angle:
                atlas.clip_composite_draw(*clip, angle, "", x, y, draw_width, draw_height)
            else:
                atlas.clip_draw(*clip, x, y, draw_width, draw_height)
        finally:
            if opacity != 1:
                atlas.opacify(1)


def rectangle(left, bottom, right, top, color, filled=True):
    p.draw_rectangle(round(left), round(bottom), round(right), round(top), *color, filled=filled)


def device_entries(game, gate_statuses, powered, exit_ready):
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
        pressed = game.plate_pressed(pos)
        entries[pos] = ("plate_down" if pressed else "plate_up"), level.device_labels[pos], TEAL if pressed else GOLD
    for pos, status in gate_statuses.items():
        label, color = {"open": ("열림", TEAL), "held": ("대기", GOLD), "closed": ("닫힘", RED)}[status]
        if status == "open" and level.gates[pos] in level.timed_echoes:
            entries[pos] = "gate_open", "지금 통과", color
        else:
            entries[pos] = "gate_open", f"{level.device_labels[pos]} {label}", color
    for pos in level.sources:
        entries[pos] = "source", "광원", GOLD
    for pos in mirror_cells(level, state):
        facing = state.mirror_rotations.get(pos, 0) + 1
        entries[pos] = ("mirror_base", "이동 거울", TEAL) if pos in state.movable_mirrors else (
            "mirror_base", f"거울 {facing}/4", GOLD)
    for pos in level.receivers:
        label = level.device_labels[pos]
        entries[pos] = ("receiver_powered", f"{label} 수신", TEAL) if pos in powered else ("receiver", label, INK)
    for pos in level.jobs:
        working = pos in state.workers
        label = level.device_labels[pos]
        if pos in level.echo_links:
            recording = state.recording and state.recording.origin == pos
            entries[pos] = (("recording_plate_active", "기록 중", GOLD) if recording else
                            ("recording_plate", recording_label(level, pos), ECHO_COLOR))
        else:
            entries[pos] = ("helper" if working else "winch"), label, TEAL if working else GOLD
    for seals, _ in level.echo_links.values():
        for gate, seal in seals.items():
            entries[seal] = "replay_seal", level.device_labels[gate], TEAL if game.echo_pressed(gate) else ECHO_COLOR
    return entries


def draw_mirror(sx, sy, size, rotation):
    """거울 화살표를 광선이 방출되는 방향으로 그린다."""
    nx, ny = mirror_output(rotation)
    tx, ty = ny, -nx

    def point(tangent, normal):
        return (sx + size * (tx * tangent + nx * normal),
                sy - size * (ty * tangent + ny * normal))

    def fill(triangles, color):
        vertices = [
            p.SDL_Vertex(p.SDL_FPoint(x, HEIGHT - 1 - y), p.SDL_Color(*color, 255), p.SDL_FPoint())
            for x, y in (point(t, n) for t, n in triangles)
        ]
        mesh = (p.SDL_Vertex * len(vertices))(*vertices)
        p.SDL_RenderGeometry(p.renderer, None, mesh, len(mesh), None, 0)

    span = .41
    for back, front, color in ((-.034, -.016, (167, 116, 75)),
                               (-.016, .004, (46, 47, 59)),
                               (.004, .027, (188, 236, 251))):
        fill(((-span, back), (span, back), (span, front),
              (-span, back), (span, front), (-span, front)), color)

    # 방출 방향 화살표는 빛과 겹치는 곳에서도 알아볼 수 있게 밝게 그린다.
    fill(((0, .37), (-.11, .24), (.11, .24),
          (-.04, .24), (-.04, .10), (.04, .10),
          (-.04, .24), (.04, .10), (.04, .24)), (137, 252, 225))


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


def draw_board(view, game, board, now, beam_segments, powered, rotations, mirror_positions,
               gate_statuses, gate_openings, rubble_contacts):
    level, state = game.level, game.state
    art = view.topdown_art
    size, half = board.cell_size, board.half_width
    stage = STAGE_THEMES.get(level.id, 1)
    scene = scene_for(level)
    ready = (state.installed == level.traps and (not level.traps or state.active)
             and state.soldiers == level.posts and state.carrying is None)
    entries = device_entries(game, gate_statuses, powered, ready)
    workshop = stage == 1
    sprites = WORKSHOP_SPRITES if workshop else ROOM_SPRITES
    props, prop_lights, recesses = room_props(scene)
    lights = room_lights(level, prop_lights, powered, ready)
    player = view.player_position(state.player, now)
    rubble = {pos: view.rubble_pose(game, pos, now) for pos in sorted(state.rubble)}
    view.hit_regions.clear()
    view.hit_masks.clear()
    view.gate_hit_masks.clear()
    view.gate_inlets.clear()
    view.plate_hit_masks.clear()
    view.action_badge_bounds = None

    background = tuple(scene["background"]) if scene else (19, 27, 32)
    draw_terrain(art, board, level, materials_for(stage), lights, background, now, recesses)
    draw_echo_trail(game, board)
    raised = [mirror_positions.get(pos, pos) for pos, (sprite, _, _) in entries.items() if sprite in RAISED_DEVICES]
    draw_shadows(board, player, [*raised, *state.items, *(pos for pos, _ in rubble.values())])

    for sprite, pos, scale in props:
        x, y = board.screen(pos)
        prop_size = size * scale
        if sprite == "throne":
            view.room_atmosphere.throne_shadow(x, y, prop_size, now)
        plinth = {"anvil": "workshop_plinth", "throne": "room_08_plinth"}.get(sprite)
        if plinth:
            art.draw(plinth, x, y, size * (.83 if workshop else .85))
            y += size * .06
        sway = view.room_atmosphere.banner(now) if sprite == "treasure_banner" else 0
        art.draw(sprites.get(sprite, sprite), x + prop_size * .45 * sin(sway), y, prop_size, angle=sway)
        view.room_atmosphere.draw(sprite, x, y, prop_size, now, top_down=True)

    view.room_debris.draw(board, now)
    for pos, (sprite, _, color) in entries.items():
        sx, sy = board.screen(mirror_positions.get(pos, pos))
        asset = sprites.get(sprite, sprite)
        if pos in level.gates:
            x, y = pos
            across_x = sum(cell in level.walls for cell in ((x - 1, y), (x + 1, y)))
            across_y = sum(cell in level.walls for cell in ((x, y - 1), (x, y + 1)))
            angle = 0 if across_x > across_y else pi / 2
            opening = gate_openings[pos]
            if opening == 0:
                art.draw(sprites.get("gate_closed", "gate_closed"), sx, sy, size * .94,
                         angle=angle, outline=True)
            else:
                art.draw(asset, sx, sy, size * .94, angle=angle, outline=True)
                if opening < 1:
                    art.draw(sprites.get("gate_closed", "gate_closed"), sx, sy + size * .19 * opening,
                             size * .94, angle=angle, opacity=min(1, 3 * (1 - opening)), inset=(.18, 0))
            view.draw_gate_dust(board, pos, now)
            if gate_statuses[pos] == "held":
                p.draw_circle(sx, sy, max(2, round(size * .044)), *GOLD, filled=True)
        elif pos in level.plates:
            pressure = view.plate_depths[pos]
            sprite = "plate_up" if pressure == 0 else "plate_down"
            art.draw(sprites.get(sprite, sprite), sx, sy, size * .82, outline=True)
            if 0 < pressure < 1:
                art.draw(sprites.get("plate_up", "plate_up"), sx, sy - size * .054 * pressure,
                         size * .82, opacity=1 - pressure, inset=(.17, .17))
        elif pos in level.sources:
            art.draw(asset, sx, sy, size * .82, angle=SOURCE_ANGLES[level.sources[pos]], outline=True)
        elif pos in state.soldiers:
            art.draw(sprites.get("post_empty", "post_empty"), sx, sy, size * .79, outline=True)
            art.draw(asset, sx, sy, size * .72, height_scale=view.work_feedback.soldier_height(pos, now))
        elif sprite == "lever_on":
            progress = view.work_feedback.progress(pos, "lever", now)
            lever = sprites["lever_off"] if progress < .44 else asset
            art.draw(lever, sx, sy, size * .82, outline=True, height_scale=1 - .11 * sin(pi * progress))
        else:
            art.draw(asset, sx, sy, size * .82, outline=True)
        if sprite == "trap_active":
            trap_motion(sx, sy + size * .35, half, now)
        if sprite == "replay_seal" and color == TEAL:
            p.draw_circle(sx, sy, round(size * .42), *TEAL, filled=False)

    for origin, pos in state.replay_workers.items():
        if state.echo is None or state.echo.origin != origin:
            sx, sy = board.screen(pos)
            art.draw(sprites["soldier_carried"], sx, sy, size * .54)

    echo_pose = view.echo_motion.pose(game, now)
    if echo_pose:
        position, direction = echo_pose
        sx, sy = board.screen(position)
        p.draw_circle(sx, sy, round(size * .33), *ECHO_COLOR)
        if state.echo.origin in state.replay_workers:
            art.draw(sprites["soldier_deployed"], sx, sy, size * .72, height_scale=view.echo_motion.stride(now))
        else:
            art.draw(f"worker_{direction}_idle", sx, sy, size * .75, opacity=.67)

    for pos, kind in state.items.items():
        sx, sy = board.screen(pos)
        sprite = ITEMS[kind]
        lift = view.chute_feedback.item_lift(pos, now)
        bounce = view.work_feedback.drop_lift(pos, now)
        lateral = size * .22 if pos in entries else 0
        art.draw(sprites.get(sprite, sprite), sx + lateral * (1 - lift), sy + size * (.04 + .28 * lift + .24 * bounce),
                 size * .54, outline=True)
    for pos, (position, height) in rubble.items():
        sx, sy = board.screen(position)
        view.draw_rubble_scrape(board, pos, position, now)
        art.draw(sprites.get("rubble", "rubble"), sx, sy + min(height, 24) * size / 256, size * .74, outline=True)

    px, py = board.screen(player)
    p.draw_circle(px, py, round(size * .38), *TEAL)
    facing = FACINGS[view.facing]
    pose = "carry" if state.carrying else (
        "walk_a" if now - view.motion[2] < .09 else "walk_b") if view.motion else "idle"
    tired = view.fatigue(game)
    art.draw(f"worker_{facing}_{pose}", px, py, size * .75,
             height_scale=view.player_pose_height(game, tired, now))
    if state.carrying:
        dx, dy = DIRECTIONS[facing]
        sprite = ITEMS[state.carrying]
        _, lift = view.work_feedback.actor_pose(state.player, now)
        art.draw(sprites.get(sprite, sprite), px + dx * size * .27 * lift, py - dy * size * .27 * lift, size * .32)
    head = py + size * .35
    badge_x = px
    player_x, player_y = state.player
    above = (player_x, player_y - 1)
    beam_devices = level.sources.keys() | level.receivers
    if above in beam_devices:
        badge_x += size * (-1 if (player_x + 1, player_y - 1) in beam_devices else 1)
    elif state.echo and state.echo.position == above:
        badge_x -= size * .85
    view.place_action_badge(game, badge_x, head, now)
    view.worker_effort((px - size * .3, py - size * .27, px + size * .3, head), tired, now)

    view.chute_feedback.draw(board, now, lambda x, y, ratio: art.draw(sprites["bone"], x, y, size * .32 * ratio),
                             top_down=True)
    view.work_feedback.draw(board, now)
    draw_echo_turn(game, board, view.echo_motion, now)
    for start, end in beam_segments:
        x1, y1 = board.screen(start)
        x2, y2 = board.screen(end)
        length = max(1, hypot(x2 - x1, y2 - y1))
        nx, ny = (y1 - y2) / length, (x2 - x1) / length
        for offset, color in ((-1, VIOLET), (0, (247, 202, 255)), (1, VIOLET)):
            p.draw_line(x1 + nx * offset, y1 + ny * offset, x2 + nx * offset, y2 + ny * offset, *color)
    beam_contacts(board, rubble_contacts, now)
    for pos, position in mirror_positions.items():
        draw_mirror(*board.screen(position), size, rotations[pos])
        view.draw_mirror_stop(board, pos, board.screen(position), now)
    for pos in powered:
        progress = view.receiver_feedback.progress(game, pos, now)
        sx, sy = board.screen(pos)
        if progress < 1:
            p.draw_circle(sx, sy, max(2, round(size * (.26 + progress * .16))), *VIOLET, filled=False)

    for pos, (_, label, color) in entries.items():
        sx, sy = board.screen(mirror_positions.get(pos, pos))
        sy += half - 2 if level.sources.get(pos) == "down" else 2 - half
        width = min(size - 4, len(label) * 12 + 8)
        rectangle(sx - width / 2, sy - 8, sx + width / 2, sy + 8, (24, 35, 40))
        view.centered(sx, sy, label, 13, color)
    if level.sources:
        for position, _ in rubble.values():
            sx, sy = board.screen(position)
            sy += 2 - half
            rectangle(sx - 30, sy - 8, sx + 30, sy + 8, (24, 35, 40))
            view.centered(sx, sy, "차광 블록", 13, GOLD)
    view.interaction_markers(game, board)
    if view.show_coordinates:
        view.coordinate_overlay(level, board)
    view.navigation_overlay(game, board)
    view.action_badge(game)
