"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 12,
    "stage_02": 33,
    "stage_03": 45,
    "stage_04": 32,
    "stage_05": 35,
    "stage_06": 40,
    "stage_07": 41,
    "stage_08": 83,
}

SOLUTIONS = {
    "stage_01": (
        "right interact down down interact down right right interact left left left"
    ).split(),
    "stage_02": (
        "down down right right right up up right interact down down left "
        "left left interact right right right down down interact up up left "
        "left left interact right interact left down down left"
    ).split(),
    "stage_03": (
        "down right right right right right interact left left interact right interact "
        "left left left down interact down down right right right right interact "
        "left left interact right interact left left left up up interact up "
        "right interact left down down down down interact left"
    ).split(),
    "stage_04": (
        "down right down right right up interact down down interact up right "
        "interact down left interact up up up right interact left interact down "
        "down down down interact up right interact down"
    ).split(),
    "stage_05": (
        "down right right interact down down right right up up up interact "
        "down down right interact down interact left left left down down left "
        "interact up right interact down left interact right interact left left"
    ).split(),
    "stage_06": (
        "down right right right right up interact down left left down down "
        "interact up interact down interact down interact right right down interact up "
        "interact right interact left interact up right interact down left left left "
        "down left interact left"
    ).split(),
    "stage_07": (
        "right interact down down left interact right interact left interact up right "
        "interact down right right right up right interact down left left left "
        "left interact up interact down right interact left interact down down interact "
        "down right interact left left"
    ).split(),
    "stage_08": (
        "down right right right interact down down down right right interact right "
        "right interact left interact left left left down left left interact right "
        "interact left interact up up up up right right right right down "
        "interact up right right interact left left left left down left left "
        "interact right right up right right down interact up left left down "
        "down down left interact down right interact down right right right down "
        "interact up left left left interact left left left interact down"
    ).split(),
}
