"""실제 규칙의 최단 탐색으로 검증한 방별 풀이와 행동 수."""


MINIMUM_ACTIONS = {
    "stage_01": 19,
    "stage_02": 50,
    "stage_03": 67,
    "stage_04": 61,
    "stage_05": 27,
    "stage_06": 63,
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
    "stage_04": (
        "down right interact down down interact right right right down down right "
        "right interact left left up up left left down down left interact "
        "up up right right right up up right interact down left down "
        "left left down down left interact up up right right right interact "
        "left left left interact right interact down down down left interact down "
        "left"
    ).split(),
    "stage_05": (
        "down right interact down right interact down right right up right interact "
        "down left down down right interact right interact left interact down interact "
        "down right right"
    ).split(),
    "stage_06": (
        "down right interact down right interact right right down right right down "
        "down down down right interact up left up up up left left "
        "down left left interact up left interact down right interact up right "
        "right right right down down interact up up left left up up "
        "up interact down down down interact down down down left left left "
        "interact down left"
    ).split(),
}
