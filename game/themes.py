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


def boundary_wall(scene, pos, level):
    """장식용 벽은 뒤쪽 외곽에만 쓴다. 내부·앞쪽의 막힌 칸은 블록으로 유지한다."""
    x, y = pos
    # 꼭짓점은 상단 HUD와 가까워 기존의 낮은 블록을 사용한다.
    if x + y < 2 or (x != 0 and y != 0):
        return None
    if x == level.width - 1 or y == level.height - 1:
        return None
    theme = scene["packs"][0]
    edge = "wall_broken" if x == 0 and y % 5 == 0 else "wall_nw" if x == 0 else "wall_ne"
    return f"{theme}_{edge}"
