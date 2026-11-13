"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 12,
    "stage_02": 33,
    "stage_03": 45,
    "stage_04": 32,
    "stage_05": 35,
    "stage_06": 43,
    "stage_07": 41,
    "stage_08": 99,
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
        "down right right interact down down interact interact interact right right up "
        "up interact down down down right interact left interact right interact down "
        "left interact up up up up up interact down down down left left down interact "
        "down left interact left"
    ).split(),
    "stage_07": (
        "right interact down down left interact right interact left interact up right "
        "interact down right right right up right interact down left left left "
        "left interact up interact down right interact left interact down down interact "
        "down right interact left left"
    ).split(),
    "stage_08": (
        "down left interact interact interact right right interact down down interact "
        "interact interact up up right right right down down down right interact right "
        "interact left left interact up up up left left down left left down down down "
        "interact right interact left interact up up up up right right right right down "
        "interact up right right interact left left left left down left left interact "
        "up right right right right down interact up left left down down down left "
        "interact down down right right right right down interact up left left left "
        "interact left left left interact down"
    ).split(),
}
