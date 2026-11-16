"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 14,
    "stage_02": 32,
    "stage_03": 51,
    "stage_04": 76,
    "stage_05": 60,
    "stage_06": 71,
    "stage_07": 41,
    "stage_08": 41,
}

SOLUTIONS = {
    "stage_01": (
        "right interact down down interact down right right up interact down left left "
        "left"
    ).split(),
    "stage_02": (
        "down down down interact down right right interact up up right right up right "
        "interact left down left left down down interact up up right interact left down "
        "down down left left"
    ).split(),
    "stage_03": (
        "down right right right right right interact left left interact right up "
        "interact down left left left down interact down down right right right right "
        "interact left left interact right down interact up left left left up up "
        "interact up right interact left down down down down right interact left left"
    ).split(),
    "stage_04": (
        "down right down right right right up interact down left left down down "
        "interact right right right down interact up left left down left left left "
        "interact right right up right right right right right right right interact "
        "left left left left left left down left left interact left interact down right "
        "right interact up up interact down down interact right right interact left "
        "left left up interact down down interact down right interact right right"
    ).split(),
    "stage_05": (
        "down push_right down right up interact down down right right right right right up "
        "up left interact right down down interact left left left left left down down "
        "down right right up right interact left down left left up left interact down "
        "right right right up interact down left left up left interact up up left "
        "interact down down down"
    ).split(),
    "stage_06": (
        "down right right up left down down down right right right down right interact "
        "up left left left interact right right down interact "
        "up left left left up left interact up left up right down down interact "
        "up up up right up right right right interact down right interact up left interact "
        "left left left down left down down down right interact up right up interact left up left left down"
    ).split(),
    "stage_07": (
        "down right up down right down down left left interact down interact down "
        "right down interact up right interact up left left interact right right "
        "interact right up up down down right right right right interact down "
        "interact down interact left"
    ).split(),
    "stage_08": (
        "right interact right down left right right right right right interact left left left up "
        "left left left left interact right right interact interact left left up up up up "
        "right right right right right right right right down interact down"
    ).split(),
}
