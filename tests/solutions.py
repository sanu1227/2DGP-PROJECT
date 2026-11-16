"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 14,
    "stage_02": 32,
    "stage_03": 51,
    "stage_04": 76,
    "stage_05": 60,
    "stage_06": 69,
    "stage_07": 70,
    "stage_08": 130,
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
        "down down right right up interact down down right right right right right up "
        "up left interact right down down interact left left left left left down down "
        "down right right up right interact left down left left up left interact down "
        "right right right up interact down left left up left interact up up left "
        "interact down down down"
    ).split(),
    "stage_06": (
        "right interact down down down interact interact interact right right right "
        "down right right interact left left up left left interact right right down "
        "interact up left left left up left left interact up up right right interact up "
        "up right right right interact left left left down interact left left interact "
        "down down down interact right right interact down right interact left down "
        "interact down left interact left"
    ).split(),
    "stage_07": (
        "right interact down down left interact right right interact left left interact "
        "up right right right interact right right up interact down left left down "
        "interact up interact down down right right interact right down right right "
        "interact left left up left left left left down left left interact up right "
        "right right right right interact left left interact up interact left down down "
        "down interact down left interact left"
    ).split(),
    "stage_08": (
        "down left interact interact interact right right right interact down down down "
        "down interact interact interact up up up up right right right right down down "
        "interact down interact up up up left left left down down down down left down "
        "down right right right down down right interact left up up left left interact "
        "right right down down interact up up left left left up left left interact "
        "right right interact left left interact up up up up up right right right right "
        "right right down interact up right right interact left left left left left "
        "down down interact up up right right right down interact up left left left "
        "down down left interact right interact down left left left interact down down "
        "down down right interact left left"
    ).split(),
}
