"""기존 등각 화면의 클릭 좌표와 한 칸씩 실행하는 자동 이동을 관리한다.

좌표는 pico2d처럼 아래쪽 원점, 위쪽 +y이다. SDL 마우스 y는 호출부에서
변환한다. 자동 이동은 모델의 이동 행동을 그대로 호출하므로 각 칸의
장치 처리와 되돌리기 기록이 유지된다. 표시 보간은 이 모듈에서 하지 않는다.
"""

from collections import deque
from dataclasses import dataclass
from math import floor

from game.levels import Pos
from game.model import DIRECTIONS, Game


_ACTIONS = {delta: action for action, delta in DIRECTIONS.items()}


@dataclass(frozen=True)
class IsoBoard:
    width: int
    height: int

    @property
    def half_width(self) -> int:
        return min(48, int(1152 / (self.width + self.height)))

    @property
    def half_height(self) -> float:
        return self.half_width / 2

    @property
    def origin(self) -> tuple[float, float]:
        return (640 - (self.width - self.height) * self.half_width / 2,
                440 + (self.width + self.height - 2) * self.half_height / 2)

    def screen(self, pos: tuple[float, float]) -> tuple[float, float]:
        x, y = pos
        ox, oy = self.origin
        return ox + (x - y) * self.half_width, oy - (x + y) * self.half_height

    def pick(self, sx: float, sy: float) -> Pos | None:
        """마름모 바닥의 칸을 선택한다. 칸 경계는 +0.5 후 내림으로 통일한다."""
        ox, oy = self.origin
        u = (sx - ox) / self.half_width
        v = (oy - sy) / self.half_height
        x, y = floor((u + v) / 2 + 0.5), floor((v - u) / 2 + 0.5)
        if 0 <= x < self.width and 0 <= y < self.height:
            return x, y
        return None


def find_path(game: Game, target: Pos | None) -> list[Pos] | None:
    """현재 진입 가능한 최단 경로를 돌려준다. 시작칸은 결과에서 제외한다."""
    start = game.state.player
    if target == start:
        return []
    if target is None or game.state.cleared or not game.walkable(target):
        return None
    # 닫힘 대기 문 위에서는 시작칸으로 다시 들어올 수 없어도 나갈 수 있다.
    previous: dict[Pos, Pos | None] = {start: None}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS.values():
            neighbor = x + dx, y + dy
            if neighbor in previous or not game.walkable(neighbor):
                continue
            previous[neighbor] = (x, y)
            if neighbor == target:
                path = [neighbor]
                while previous[path[-1]] != start:
                    path.append(previous[path[-1]])
                path.reverse()
                return path
            queue.append(neighbor)
    return None


class ClickNavigator:
    def __init__(self):
        self.path: list[Pos] = []
        self.target: Pos | None = None
        self.next_step_at = 0.0

    @property
    def active(self) -> bool:
        return bool(self.path)

    def cancel(self) -> None:
        """남은 경로만 취소한다. 이미 실행한 이동을 되돌리지는 않는다."""
        self.path.clear()
        self.target = None

    def start(self, game: Game, target: Pos | None, now: float,
              ready_at: float | None = None) -> bool:
        """새 목표로 경로를 교체한다. ready_at 이전에는 첫 칸을 실행하지 않는다."""
        self.cancel()
        path = find_path(game, target)
        if path is None:
            if not game.state.cleared:
                game.message = "이 칸까지 이동할 수 없습니다."
            return False
        if not path:
            if not game.state.cleared:
                game.message = "현재 서 있는 칸입니다."
            return True
        self.path.extend(path)
        self.target = target
        self.next_step_at = max(now, ready_at if ready_at is not None else now)
        game.message = "선택한 칸으로 이동합니다. 우클릭으로 취소할 수 있습니다."
        return True

    def tick(self, game: Game, now: float) -> str | None:
        """한 번에 최대 한 칸만 실행하고, 성공한 이동 액션을 반환한다."""
        if not self.active:
            return None
        if game.state.cleared:
            self.cancel()
            return None
        if now < self.next_step_at:
            return None
        destination = self.path[0]
        delta = tuple(b - a for a, b in zip(game.state.player, destination))
        action = _ACTIONS.get(delta)
        if action is None:
            self.cancel()
            game.message = "현재 위치가 바뀌어 자동 이동을 멈췄습니다."
            return None
        if not game.walkable(destination):
            self.cancel()
            game.message = "앞길이 막혀 자동 이동을 멈췄습니다."
            return None
        if not game.act(action):
            self.cancel()
            return None
        self.path.pop(0)
        self.next_step_at = now + 0.18
        if game.state.cleared or not self.path:
            self.cancel()
        return action
