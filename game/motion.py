"""모델의 칸 이동을 바꾸지 않고 표시 경로만 부드럽게 재생한다.

성공한 이동마다 start(previous, destination, now)를 호출한다. 그릴 때는
position(model_position, now)를 먼저 호출하고 moving, direction, phase를 읽는다.
direction은 현재 재생 중인 구간의 up/down/left/right이며, phase는 0~1이다.
phase < 0.5이면 walk_a, 나머지는 walk_b 자세로 표시할 수 있다.
되돌리기·재시작·즉시 상호작용처럼 화면을 모델 위치에 맞출 때는 reset()한다.
"""

from collections import deque
from dataclasses import dataclass
from math import isfinite


_DIRECTIONS = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}


@dataclass(frozen=True)
class _Step:
    previous: tuple[int, int]
    destination: tuple[int, int]
    began: float
    duration: float


class GridMotion:
    def __init__(self, step_seconds: float = 0.14):
        if not isfinite(step_seconds) or step_seconds <= 0:
            raise ValueError("이동 시간은 양의 유한한 수여야 합니다.")
        self.step_seconds = step_seconds
        self._steps: deque[_Step] = deque()
        self.phase = 0.0

    @property
    def moving(self) -> bool:
        """가장 최근 start/position 호출 시점에 남아 있는 표시 구간이 있는가."""
        return bool(self._steps)

    @property
    def direction(self) -> str | None:
        if not self._steps:
            return None
        step = self._steps[0]
        delta = tuple(b - a for a, b in zip(step.previous, step.destination))
        return _DIRECTIONS[delta]

    def reset(self) -> None:
        self._steps.clear()
        self.phase = 0.0

    def _advance(self, now: float) -> None:
        while self._steps and now >= self._steps[0].began + self._steps[0].duration:
            self._steps.popleft()
        if self._steps:
            step = self._steps[0]
            self.phase = max(0.0, min(1.0, (now - step.began) / step.duration))
        else:
            self.phase = 0.0

    def start(self, previous: tuple[int, int], destination: tuple[int, int], now: float) -> None:
        """한 칸 이동을 예약한다. 대기 구간은 2배속으로 재생하되 생략하지 않는다."""
        previous, destination = tuple(previous), tuple(destination)
        delta = tuple(b - a for a, b in zip(previous, destination))
        if len(previous) != 2 or len(destination) != 2 or delta not in _DIRECTIONS:
            raise ValueError("표시 경로에는 상하좌우 한 칸 이동만 넣을 수 있습니다.")
        self._advance(now)
        if self._steps:
            tail = self._steps[-1]
            if tail.destination != previous:
                raise ValueError("이전 표시 경로의 도착점과 새 이동의 시작점이 다릅니다.")
            began = tail.began + tail.duration
            duration = self.step_seconds / 2
        else:
            began, duration = now, self.step_seconds
        self._steps.append(_Step(previous, destination, began, duration))
        self._advance(now)

    def position(self, fallback: tuple[int, int], now: float) -> tuple[float, float]:
        self._advance(now)
        if not self._steps:
            return tuple(float(value) for value in fallback)
        step = self._steps[0]
        eased = self.phase * self.phase * (3 - 2 * self.phase)
        return tuple(a + (b - a) * eased for a, b in zip(step.previous, step.destination))
