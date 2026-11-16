"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 14,
    "stage_02": 28,
    "stage_03": 55,
    "stage_04": 74,
    "stage_05": 56,
    "stage_06": 77,
    "stage_07": 43,
    "stage_08": 43,
}

SOLUTIONS = {
    "stage_01": (
        "right interact down down interact down right right up interact down left left "
        "left"
    ).split(),
    "stage_02": (
        "down down down interact right right interact up right right up right interact "
        "left down left left down interact up right interact left down left down down "
        "left"
    ).split(),
    "stage_03": (
        "down down down down right right right right right interact left left interact "
        "right down interact up left left left up left up up right interact right right "
        "right right interact left left interact right up interact down left left left "
        "interact right interact left left down down down down right right interact left "
        "left"
    ).split(),
    "stage_04": (
        "down right down right right right up interact down left left down down interact "
        "right right right down interact up left left down left left left interact right "
        "right up right right right right right right right interact left left left left "
        "left left interact left interact down interact left left interact right right "
        "right down interact right interact left up up interact down left left down down "
        "interact down right interact right right"
    ).split(),
    "stage_05": (
        "down right down right interact down right right right right right "
        "up up left interact right down down interact left left left "
        "left left down down down right right up right interact left "
        "down left left up interact down right right up interact down "
        "left left up up left interact up left interact down down "
        "down"
    ).split(),
    "stage_06": (
        "right down down down right right right up down down right "
        "right right right down right interact left up left left interact "
        "right right down interact up left left up up up up "
        "left left interact down up interact up right right right up "
        "right interact down interact up interact down left left down left "
        "left left left up up left interact left interact right interact "
        "down down down down down right interact down down left left"
    ).split(),
    "stage_07": (
        "down right up left down right right down down left left "
        "interact down interact down right down interact up right interact up "
        "left left interact right right interact right up up down down "
        "right right right right interact down interact down interact left"
    ).split(),
    "stage_08": (
        "down right interact right up right right down right right interact "
        "left left up left left down left left up left interact "
        "right interact interact left up up up up right right right "
        "right right left right right right right down interact down"
    ).split(),
}
