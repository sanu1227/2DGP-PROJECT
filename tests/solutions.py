"""실제 게임 규칙의 최단 탐색으로 검증한 소형 방 풀이."""

MINIMUM_ACTIONS = {
    "stage_01": 12,
    "stage_02": 36,
    "stage_03": 49,
    "stage_04": 68,
    "stage_05": 50,
    "stage_06": 63,
    "stage_07": 70,
    "stage_08": 122,
}

SOLUTIONS = {
    "stage_01": (
        "right interact down down interact down right right interact left left left"
    ).split(),
    "stage_02": (
        "down down right right right right up right interact left down left left down "
        "interact up right right down down interact up up left left down interact up "
        "right interact left down down down left left"
    ).split(),
    "stage_03": (
        "down right right right right right interact left left interact right up "
        "interact down left left left down interact down down right right right right "
        "interact left left interact right down interact up left left left up up "
        "interact up right interact left down down down down interact left"
    ).split(),
    "stage_04": (
        "down right down right right right up interact down left left left left down "
        "down right right interact right right right down interact up left left down "
        "interact up right right right right right right interact left left left left "
        "left left down left interact up interact down down interact up right interact "
        "down left interact right interact left up interact down left down interact "
        "down interact left"
    ).split(),
    "stage_05": (
        "down right right interact down down right right up up interact down down right "
        "right right interact left left left left left down down down right right up "
        "right interact left down left left up interact down right right up interact "
        "down left left up interact left left interact down"
    ).split(),
    "stage_06": (
        "right interact down down down interact interact interact right right right "
        "down right right interact left left up left left interact right right down "
        "interact up left left left up up left interact up right interact up up right "
        "right right interact left left left down down down left interact down right "
        "interact down right interact left down interact down left interact left"
    ).split(),
    "stage_07": (
        "right interact down left interact down right right interact left left up "
        "interact right right right interact right right up interact down left left "
        "down down left left left interact up up right right right interact down down "
        "right interact right right down right right interact left left up left left "
        "left left down down interact up up right right interact left left down "
        "interact down down left interact left"
    ).split(),
    "stage_08": (
        "down left interact interact interact right right right interact down down down "
        "interact interact interact up up up right right right right down down interact "
        "down interact up up up left left left down down down down left down down right "
        "right right down down right interact left up up left left interact right right "
        "down down interact up up left left left up left left interact right interact "
        "left interact up up up up up right right right right right right down interact "
        "up right right interact left left left left left down down left interact up up "
        "right right right right down interact up left left left down down down down "
        "left left interact down down left left interact down"
    ).split(),
}
