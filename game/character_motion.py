"""실시간이나 렌더러에 의존하지 않는 만화 캐릭터 동작 샘플링."""

from dataclasses import dataclass


MOTION_END = 5.2
WALK_START, WALK_END = 0.25, 2.25
INHALE_START, EXHALE_START, EXHALE_END = 2.85, 3.45, 4.65
WALK_FRAMES = 12
ACCEL_SECONDS = .25
TRAVEL = .20
# 가속·감속 곡선의 면적까지 포함해 원래 이동 거리(패널 폭의 20%)를 유지한다.
WALK_SPEED = TRAVEL / (WALK_END - WALK_START - ACCEL_SECONDS / 2
                       + (INHALE_START - WALK_END) / 2)
WALK_DISTANCE = WALK_SPEED * (WALK_END - WALK_START - ACCEL_SECONDS / 2)


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
    if t < WALK_START:
        return WorkerMotion(0, .24, 0, 1, "ready")
    if t < WALK_END:
        elapsed = t - WALK_START
        if elapsed < ACCEL_SECONDS:
            q = elapsed / ACCEL_SECONDS
            distance = WALK_SPEED * ACCEL_SECONDS * (q ** 3 - q ** 4 / 2)
        else:
            distance = WALK_SPEED * (elapsed - ACCEL_SECONDS / 2)
        # 실제 이동량에 두 주기를 맞춘다. 느리게 출발할 때 발만 먼저 뛰지 않는다.
        frame = int(distance / WALK_DISTANCE * WALK_FRAMES * 2) % WALK_FRAMES
        return WorkerMotion(frame, .24 + distance, 0, 1, "walk")
    if t < INHALE_START:
        duration = INHALE_START - WALK_END
        q = (t - WALK_END) / duration
        distance = WALK_SPEED * duration * (q - q ** 3 + q ** 4 / 2)
        # 속도는 걷기 끝에서 연속이고 발을 모은 뒤 0이 된다.
        progress = clamp(distance / (TRAVEL - WALK_DISTANCE))
        frame = 12 + min(5, int(progress * 6))
        return WorkerMotion(frame, .24 + WALK_DISTANCE + distance, 0, 1, "stop")
    x = .24 + TRAVEL
    if t < EXHALE_START:
        progress = (t - INHALE_START) / (EXHALE_START - INHALE_START)
        return WorkerMotion(18 + min(5, int(progress * 6)), x, 0, 1, "inhale")
    if t < EXHALE_END:
        breath = (t - EXHALE_START) / (EXHALE_END - EXHALE_START)
        return WorkerMotion(24 + min(11, int(breath * 12)), x, 0, 1, "sigh", breath)
    return WorkerMotion(35, x, 0, 1, "rest")
