"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 12,
    "stage_02": 31,
    "stage_03": 45,
    "stage_04": 31,
    "stage_05": 39,
    "stage_06": 50,
    "stage_07": 39,
    "stage_08": 105,
}

SOLUTIONS = {
    "stage_01": (
        "right interact down down interact down right right interact left left left"
    ).split(),
    "stage_02": (
        "down down right right right up up right interact down down left left left "
        "interact right right down down interact up up left left interact right "
        "interact left down down left"
    ).split(),
    "stage_03": (
        "down right right right right right interact left left interact right interact "
        "left left left down interact down down right right right right interact left "
        "left interact right interact left left left up up interact up right interact "
        "left down down down down interact left"
    ).split(),
    "stage_04": (
        "down right down right right up interact down down interact up right interact "
        "left down interact up up up right interact left interact down down down down "
        "interact right interact right"
    ).split(),
    "stage_05": (
        "down right right interact down down right right up up up interact down down "
        "right interact down left left left down down right right interact left left "
        "left interact right right interact left left interact up left interact down"
    ).split(),
    "stage_06": (
        "right interact down down interact interact interact right right down interact "
        "up left left down interact up right right right interact left left left up "
        "left interact up right interact up up right right interact left left down down "
        "down left interact right interact down down down left interact left"
    ).split(),
    "stage_07": (
        "right interact down down left interact right interact left interact up right "
        "right interact down right right right interact left left left down interact up "
        "up interact down interact down interact left down interact down right interact "
        "left left"
    ).split(),
    "stage_08": (
        "down left interact interact interact right right interact down down interact "
        "interact interact up up right right right down down interact down interact up "
        "up up left left down down down down down right right right down down right "
        "interact left up up left left left interact right right right down down "
        "interact up up left left left up left left interact right interact left "
        "interact up up up up right right right right interact right right interact "
        "left left left left down left left interact up right right right right "
        "interact left left down down down left interact down down left left interact "
        "down"
    ).split(),
}
