"""스테이지의 장식만 선택한다. 이동·충돌·장치 상태는 모델이 관리한다."""

from functools import lru_cache
import json
from pathlib import Path

from game.scenery import _pattern


@lru_cache(maxsize=1)
def _catalog():
    source = Path(__file__).resolve().parents[1] / "data" / "scenery.json"
    return json.loads(source.read_text(encoding="utf-8"))


@lru_cache(maxsize=16)
def _checked_scene(identifier, walls):
    scene = _catalog().get(identifier)
    if scene:
        for decoration in scene["decorations"]:
            if tuple(decoration["cell"]) not in walls:
                raise ValueError(f"{identifier}: 장식은 막힌 벽칸에만 배치해야 합니다.")
        for mount in scene.get("wall_mounts", ()):
            x, y = mount["cell"]
            direction = "nw" if x == 0 else "ne"
            if ((x, y) not in walls or (x != 0 and y != 0) or (x, y) == (0, 0)
                    or not mount["sprite"].endswith(f"_{direction}")):
                raise ValueError(f"{identifier}: 벽 장식은 방향이 맞는 뒤쪽 외곽 벽에 배치해야 합니다.")
    return scene


def scene_for(level):
    return _checked_scene(level.id, level.walls)


def themed_floor(scene, pos, near_trap=False):
    """기본 바닥을 넓게 남기고, 고정된 일부 칸에만 장식 문양을 배치한다."""
    floors = scene["floors"]
    choice = _pattern(pos) % 100
    index = 0 if choice < 68 or near_trap else 1 if choice < 82 else 2 if choice < 94 else 3
    if scene["name"] == "왕실 납골당" and pos[0] == 2 and not near_trap:
        index = 3
    return floors[index], tuple(scene["floor_tint"])


def low_wall_sprite(scene, pos):
    """선택한 방의 낮은 벽에 고정된 변형을 섞는다. 충돌 칸은 바꾸지 않는다."""
    variants = scene.get("low_wall_variants") if scene else None
    return variants[(_pattern(pos) >> 6) % len(variants)] if variants else "wall_low"


def boundary_walls(scene, pos, level):
    """뒤쪽 두 변을 연결한다. 모서리는 두 면, 양 끝은 낮은 벽으로 마감한다."""
    x, y = pos
    theme = scene["packs"][0]
    faces = []
    for at_edge, along, length, direction in ((x == 0, y, level.height, "nw"),
                                              (y == 0, x, level.width, "ne")):
        if at_edge:
            style = "short" if along == length - 1 else "damaged" if along and along % 5 == 0 else "tall"
            faces.append(f"{theme}_wall_{style}_{direction}")
    return faces
