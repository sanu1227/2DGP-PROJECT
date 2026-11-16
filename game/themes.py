"""스테이지의 장식만 선택한다. 이동·충돌·장치 상태는 모델이 관리한다."""

from functools import lru_cache
import json
from pathlib import Path

from game.levels import DIRECTIONS
from game.scenery import _pattern, wall_style


@lru_cache(maxsize=1)
def _catalog():
    source = Path(__file__).resolve().parents[1] / "data" / "scenery.json"
    return json.loads(source.read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
def _checked_scene(identifier, width, height, walls):
    scene = _catalog().get(identifier)
    if scene:
        occupied = set()
        for mount, entries in ((False, scene["decorations"]), (True, scene.get("wall_mounts", ()))):
            for entry in entries:
                x, y = entry["cell"]
                dx, dy = DIRECTIONS[entry["facing"]]
                cell, room_cell = (x, y), (x + dx, y + dy)
                if (cell not in walls or cell in occupied or room_cell in walls
                        or not (0 <= room_cell[0] < width and 0 <= room_cell[1] < height)):
                    raise ValueError(f"{identifier}: {entry['sprite']}는 실내 바닥과 맞닿은 빈 벽면에 둬야 합니다.")
                if mount and not entry["sprite"].endswith("_nw" if dx else "_ne"):
                    raise ValueError(f"{identifier}: {entry['sprite']}의 벽면 방향이 맞지 않습니다.")
                if not mount and not (0 < x < width - 1 and 0 < y < height - 1):
                    raise ValueError(f"{identifier}: {entry['sprite']}는 방 안쪽 벽칸에 둬야 합니다.")
                occupied.add(cell)
    return scene


def scene_for(level):
    return _checked_scene(level.id, level.width, level.height, level.walls)


def room_background(scene):
    return tuple(scene["background"]) if scene else (19, 27, 32)


def themed_floor(scene, pos, near_trap=False):
    """기본 바닥을 넓게 남기고, 고정된 일부 칸에만 장식 문양을 배치한다."""
    for region in scene.get("floor_regions", ()):
        x0, y0, x1, y1 = region["rect"]
        if x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1:
            return region["floor"], tuple(scene["floor_tint"])
    floors = scene["floors"]
    choice = _pattern(pos) % 100
    index = 0 if choice < 68 or near_trap else 1 if choice < 82 else 2 if choice < 94 else 3
    if scene["name"] == "왕실 납골당" and pos[0] == 2 and not near_trap:
        index = 3
    return floors[index], tuple(scene["floor_tint"])


def low_wall_sprite(scene, pos, level=None):
    """직선·코너·끝을 주변 석축에 연결한다. 잔해와 충돌 데이터는 유지한다."""
    variants = scene.get("low_wall_variants") if scene else None
    straight = variants[(_pattern(pos) >> 6) % len(variants)] if variants else "wall_low"
    if not (scene and scene.get("connected_low_walls") and level):
        return straight

    def solid(point):
        # 뒤쪽 외곽은 높은 벽 앞의 낮은 석축이 항상 존재한다.
        return point in level.walls and (0 in point or wall_style(point)[0] != "rubble")

    x, y = pos
    # N/E/S/W are grid directions, not screen compass directions.
    directions = ((0, -1), (1, 0), (0, 1), (-1, 0))
    exposed = sum(1 << index for index, (dx, dy) in enumerate(directions)
                  if not solid((x + dx, y + dy)))
    corners = {3: "sw", 6: "nw", 12: "ne", 9: "se"}
    if exposed in corners:
        return f"wall_low_corner_{corners[exposed]}"
    if exposed.bit_count() >= 3:
        return "wall_low_pier"
    if exposed in (2, 8, 10):
        return "wall_low_axis_y"
    if exposed in (1, 4, 5):
        return straight
    # 넓은 벽 덩어리 안쪽은 가까운 통로의 방향을 따른다.
    floors = ((fx, fy) for fy in range(level.height) for fx in range(level.width)
              if (fx, fy) not in level.walls)
    nearest = min(floors, key=lambda p: (abs(p[0] - x) + abs(p[1] - y), p), default=pos)
    return "wall_low_axis_y" if abs(nearest[0] - x) > abs(nearest[1] - y) else straight


def boundary_walls(scene, pos, level):
    """뒤쪽 두 변을 연결한다. 모서리는 두 면, 양 끝은 낮은 벽으로 마감한다."""
    x, y = pos
    theme = scene.get("wall_pack", scene["packs"][0])
    faces = []
    for at_edge, along, length, direction in ((x == 0, y, level.height, "nw"),
                                              (y == 0, x, level.width, "ne")):
        if at_edge:
            style = "short" if along == length - 1 else "damaged" if along and along % 5 == 0 else "tall"
            faces.append(f"{theme}_wall_{style}_{direction}")
    return faces
