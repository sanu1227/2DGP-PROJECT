"""실제 규칙의 최단 탐색으로 검증한 방별 풀이와 행동 수."""


MINIMUM_ACTIONS = {
    "stage_01": 19,
    "stage_02": 50,
    "stage_03": 67,
}


SOLUTIONS = {
    "stage_01": (
        "down right interact right right right right down down interact down down "
        "left left left down interact left left"
    ).split(),
    "stage_02": (
        "down down down down right right right right right right right up "
        "up up left interact down right down down left left left left "
        "left interact right right right down down right interact up up left "
        "left left left interact right right interact left down down down left "
        "left left"
    ).split(),
    "stage_03": (
        "down down right right right right right up right interact down left "
        "left left interact right right interact left left left left down down "
        "interact down right right right down right right interact up left left "
        "left interact right down down right right right interact up up left "
        "left left left left left up interact up up right interact left "
        "down down down down interact down left"
    ).split(),
}

# 배치 초안: 실제 완주만 검증했으며 최단성은 미검증이다.
import json
from pathlib import Path
_DRAFT = json.loads((Path(__file__).resolve().parents[1] / "data/gimmick_draft_routes.json").read_text(encoding="utf-8"))
SOLUTIONS.update({name: entry["actions"] for name, entry in _DRAFT.items()})
