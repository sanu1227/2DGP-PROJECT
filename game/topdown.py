"""정면에 가까운 3/4 탑다운 화면. 바닥은 압축하고 물체는 세워 그린다."""

import pico2d.pico2d as p

from game.navigation import TopDownBoard
from game.themes import scene_for


DECORATIONS = {
    "forge_anvil": "forge_anvil", "forge_tool_rack": "forge_tools",
    "forge_coal_forge": "forge_furnace", "forge_boiler": "forge_furnace",
    "forge_gear_rack": "forge_gears", "forge_metal_crate": "forge_gears",
    "crypt_sarcophagus": "crypt_coffin", "crypt_coffin": "crypt_coffin",
    "crypt_broken_statue": "crypt_statue", "crypt_memorial_urn": "crypt_statue",
    "crypt_candles": "crypt_candles", "crypt_banner": "crypt_banner",
    "archive_bookshelf": "archive_bookshelf", "archive_scroll_rack": "archive_bookshelf",
    "archive_fallen_shelf": "archive_books", "archive_book_pile": "archive_books",
    "archive_writing_desk": "archive_books", "archive_crystal_lectern": "archive_books",
    "sewer_pipe_elbow": "sewer_pipe", "sewer_drain_outlet": "sewer_pipe",
    "sewer_hand_pump": "sewer_pipe", "sewer_water_barrel": "sewer_barrel",
    "sewer_reed_planter": "sewer_barrel",
}
FACING = {"ne": "up", "se": "right", "sw": "down", "nw": "left"}
FLAT_DEVICES = {"trap_broken", "trap_installed", "trap_active", "exit_closed", "exit_ready",
                "plate_up", "plate_down", "post_empty"}


def draw_board(view, game, now):
    level, state = game.level, game.state
    board = TopDownBoard(level.width, level.height)
    hw, hh = board.half_width, board.half_height
    scene = scene_for(level)
    view.art.load_topdown()
    theme = scene["packs"][0] if scene else "forge"
    view.hit_regions.clear()
    view.hit_masks.clear()
    ready = (state.installed == level.traps and (not level.traps or state.active)
             and state.soldiers == level.posts and state.carrying is None)
    objects, labels, heights = [], [], {}

    def box(left, bottom, right, top, color, filled=True):
        p.draw_rectangle(round(left), round(bottom), round(right), round(top), *color, filled=filled)

    def outline(sx, sy, color):
        box(sx - hw + 2, sy - hh + 2, sx + hw - 2, sy + hh - 2, color, False)

    def add_sprite(pos, sprite, sx, sy, size, priority=1, selectable=True):
        sprite = f"td_{sprite}"
        objects.append((pos[1], priority, "sprite", (pos, sprite, sx, sy, size, selectable)))

    view.text(48, 700, "던전 복구", 22, (104, 206, 184))
    view.text(48, 670, "밝은 바닥 · 이동 가능", 16)
    view.text(48, 640, "F2  좌표 표시", 16)
    view.text(48, 596, "W / ↑  위쪽", 16)
    view.text(48, 568, "D / →  오른쪽", 16)

    # 바닥을 먼저 그린 뒤, 벽과 물체를 뒤에서 앞으로 합성한다.
    for y in range(level.height):
        for x in range(level.width):
            pos = x, y
            sx, sy = board.screen(pos)
            variant = "cracked" if (x * 7 + y * 11) % 5 == 0 else "floor"
            tile = f"td_{theme}_{variant}"
            view.art.draw_rect(tile, sx, sy, hw * 2, hh * 2)
            if pos in level.walls:
                height = 60 if y == 0 else 12 if y == level.height - 1 else 20
                heights[pos] = height * board.cell_size / 68
                objects.append((y, 0, "wall", (pos, sx, sy, heights[pos])))
                continue
            label, sprite, color = "", None, (227, 187, 104)
            if pos in level.traps:
                label = "가동" if state.active else "설치" if pos in state.installed else "파손"
                sprite = "trap_active" if state.active else "trap_installed" if pos in state.installed else "trap_broken"
                color = (232, 119, 105) if state.active else color
            elif pos in level.posts:
                label, sprite = ("병사", "soldier_deployed") if pos in state.soldiers else ("초소", None)
                if pos in state.soldiers:
                    color = (232, 119, 105)
            elif pos in level.levers:
                label, sprite = "레버", "lever_on" if state.active else "lever_off"
            elif pos in level.benches:
                count = state.bench_bones.get(pos, 0)
                label, sprite = f"조립{count}/2", "bench_one_bone" if count else "bench_empty"
            elif pos == level.exit:
                label, sprite = "출구", "exit_ready" if ready else "exit_closed"
                color = (104, 206, 184) if ready else color
            elif pos in level.plates:
                label = level.device_labels[pos]
                sprite = "plate_down" if game.plate_pressed(pos) else "plate_up"
            elif pos in level.gates:
                status = game.gate_status(pos)
                label = {"open": "열림", "held": "대기", "closed": "닫힘"}[status]
                color = (104, 206, 184) if status == "open" else (232, 119, 105)
                sprite = "gate_open" if status == "open" else "gate_closed"
            elif pos in level.chutes:
                label, sprite = level.device_labels[pos], "chute_inlet"
            elif pos in level.chutes.values():
                label, sprite = "배출", "chute_outlet"
            elif pos in level.belts:
                view.art.draw_rect("td_conveyor", sx, sy, hw * 2 - 4, hh * 2 - 4,
                                   rotate=level.belts[pos] in ("up", "down"))
                arrow = {"up": "↑", "down": "↓", "left": "←", "right": "→"}[level.belts[pos]]
                view.text(sx - 8, sy + 4, arrow, 22, color)
                label = "벨트"
            if sprite:
                base = sy - hh + 5 if sprite in FLAT_DEVICES else sy - 5
                size = 0.86 if sprite in FLAT_DEVICES else 0.78
                add_sprite(pos, sprite, sx, base, board.cell_size * size)
            if label:
                outline(sx, sy, color)
            if pos in state.items:
                item = state.items[pos]
                add_sprite(pos, {"part": "part", "bone": "bone_bundle", "soldier": "soldier_carried"}[item],
                           sx, sy - 2, board.cell_size * 0.48, 2)
                if not label:
                    label = {"part": "부품", "bone": "뼈", "soldier": "병사"}[item]
            if label:
                labels.append((pos, sx, sy - hh + 7, label, color))

    if scene:
        for decoration in scene["decorations"]:
            pos = tuple(decoration["cell"])
            sx, sy = board.screen(pos)
            add_sprite(pos, DECORATIONS[decoration["sprite"]], sx, sy + heights[pos] - hh + 2,
                       min(board.cell_size * decoration["scale"], board.cell_height * 0.75), 1.5, False)

    player = view.player_position(state.player, now)
    px, py = board.screen(player)
    outline(px, py, (104, 206, 184))
    pose = "carry" if state.carrying else ("walk_a" if now - view.motion[2] < 0.09 else "walk_b") if view.motion else "idle"
    add_sprite(player, f"worker_{FACING[view.facing]}_{pose}", px, py - 4, board.cell_size * 0.88, 3)
    if state.carrying:
        sprite = {"part": "part", "bone": "bone_bundle", "soldier": "soldier_carried"}[state.carrying]
        add_sprite(player, sprite, px + hw * 0.35, py + 12, board.cell_size * 0.35, 4, False)

    for _, _, kind, data in sorted(objects, key=lambda obj: obj[:2]):
        if kind == "wall":
            pos, sx, sy, height = data
            bottom = sy - hh
            view.art.draw_rect(f"td_{theme}_face", sx, bottom + height / 2, hw * 2, height)
            view.art.draw_rect(f"td_{theme}_cap", sx, sy + height, hw * 2, hh * 2, (190, 198, 205))
            # 벽 앞면과 윗면을 모두 같은 막힌 칸으로 선택한다.
            view.hit_regions.append((pos, (sx - hw, bottom, sx + hw, sy + hh + height)))
        else:
            pos, sprite, sx, sy, size, selectable = data
            entry = view.art.manifest["sprites"][sprite]["content_rect"]
            scale = size / (208 if sprite.startswith("td_worker_") else max(entry["width"], entry["height"]))
            left, bottom, right, _ = view.art.bounds(sprite, 0, 0, scale)
            ax, ay = sx - (left + right) / 2, sy - bottom
            view.art.draw(sprite, ax, ay, scale)
            if selectable:
                cell = state.player if sprite.startswith("td_worker_") else pos
                view.sprite_hit_region(cell, sprite, ax, ay, scale)

    for pos, sx, sy, label, color in labels:
        width = len(label) * 13 + 6
        box(sx - width / 2, sy - 8, sx + width / 2, sy + 8, (23, 31, 34))
        view.text(sx - width / 2 + 3, sy, label, 13, color)
        view.hit_regions.append((pos, (sx - width / 2, sy - 8, sx + width / 2, sy + 8)))
    view.navigation_overlay(game, board)
    if view.show_coordinates:
        view.coordinate_overlay(level, board)
