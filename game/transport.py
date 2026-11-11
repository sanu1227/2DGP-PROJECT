"""완료된 벨트 운반을 게임 상태 변경 없이 칸별로 재생한다."""

from game.model import Game

BELT_SECONDS = 0.16


class BeltAnimation:
    def __init__(self):
        self.game = None
        self.state = None
        self.steps = ()
        self.started = 0.0

    def start(self, game: Game, now: float) -> None:
        self.game = game
        self.state = game.state
        self.steps = tuple(game.belt_steps)
        self.started = now

    def sample(self, game: Game, now: float):
        # 되돌리기·재시작·방 이동은 논리 상태가 바뀌므로 즉시 재생을 취소한다.
        if game is not self.game or game.state is not self.state:
            return None
        progress = max(0.0, now - self.started) / BELT_SECONDS
        index = int(progress)
        if index >= len(self.steps):
            return None
        step = self.steps[index]
        return step.state, step.moves, progress - index
