"""실시간이나 렌더러에 의존하지 않는 만화 캐릭터 동작 샘플링."""

from dataclasses import dataclass
from math import pi, sin


MOTION_END = 5.2
WALK_START, WALK_END = 0.35, 2.6
INHALE_START, EXHALE_START, EXHALE_END = 3.0, 3.5, 4.6


def clamp(value):
    return min(1.0, max(0.0, value))


def smooth(value):
    t = clamp(value)
    return t * t * (3 - 2 * t)


@dataclass(frozen=True)
class WorkerMotion:
    frame: int
    x: float
    bob: float
    stretch: float
    phase: str
    breath: float | None = None


def worker_motion(age):
    t = max(0.0, age)
    progress = clamp((t - WALK_START) / (WALK_END - WALK_START))
    x = 0.24 + 0.20 * smooth(progress)
    if t < WALK_START:
        return WorkerMotion(6, x, 0, 1, "ready")
    if t < WALK_END:
        walk = t - WALK_START
        return WorkerMotion(int(walk * 6) % 6, x, -2.2 * abs(sin(walk * 6 * pi)), 1, "walk")
    if t < INHALE_START:
        return WorkerMotion(6, x, 0, 1, "stop")
    if t < EXHALE_START:
        lift = smooth((t - INHALE_START) / (EXHALE_START - INHALE_START))
        return WorkerMotion(7, x, 0, 1 + .025 * lift, "inhale")
    if t < EXHALE_END:
        breath = (t - EXHALE_START) / (EXHALE_END - EXHALE_START)
        return WorkerMotion(8 if breath < .48 else 9, x, 0, 1.025 - .04 * smooth(breath), "sigh", breath)
    return WorkerMotion(11 if 4.9 <= t < 5.1 else 10, x, 0, .985, "rest")
