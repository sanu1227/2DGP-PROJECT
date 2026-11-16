"""거울의 회전 상태와 실제 방출 방향."""

from math import cos, pi, sin

from game.levels import DIRECTIONS


MIRROR_DIRECTIONS = ("right", "down", "left", "up")
MIRROR_LABELS = ("오른쪽", "아래", "왼쪽", "위")


def mirror_output(rotation):
    """정지 시 격자 방향, 회전 중에는 같은 방향 사이의 연속 벡터."""
    if rotation == int(rotation):
        return DIRECTIONS[MIRROR_DIRECTIONS[int(rotation) % len(MIRROR_DIRECTIONS)]]
    angle = rotation * pi / 2
    return cos(angle), sin(angle)
