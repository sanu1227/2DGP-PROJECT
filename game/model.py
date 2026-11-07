"""화면이나 실시간 프레임에 의존하지 않는 한 칸 단위 퍼즐."""

from copy import deepcopy
from collections import Counter
from dataclasses import dataclass, field

from game.levels import Level, Pos


DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
ITEM_NAMES = {"part": "함정 부품", "bone": "뼈 묶음", "soldier": "해골 병사"}


@dataclass
class State:
    player: Pos
    carrying: str | None = None
    items: dict[Pos, str] = field(default_factory=dict)
    installed: set[Pos] = field(default_factory=set)
    active: bool = False
    soldiers: set[Pos] = field(default_factory=set)
    bench_bones: dict[Pos, int] = field(default_factory=dict)
    moves: int = 0
    cleared: bool = False


class Game:
    def __init__(self, level: Level):
        self.level = level
        self.restart()

    def restart(self) -> None:
        self.state = State(player=self.level.start, items=dict(self.level.initial_items))
        self.history: list[State] = []
        self.message = "물건이나 장치 위에서 E를 누르세요."

    def act(self, action: str) -> bool:
        """성공한 상태 변경만 한 행동으로 기록한다. 실패는 안내만 바꾼다."""
        if action not in {*DIRECTIONS, "interact", "drop", "wait"}:
            raise ValueError(f"알 수 없는 행동: {action}")
        if self.state.cleared:
            self.message = "복구 완료! 다음 방으로 진행하세요."
            return False

        candidate = deepcopy(self.state)
        changed, message = self._apply(candidate, action)
        self.message = message
        if not changed:
            return False
        transported = self._advance_belts(candidate)
        if transported:
            self.message += f" 벨트가 물건 {transported}개를 옮겼습니다."
        # ponytail: 최대 12×12칸에서는 전체 복사가 충분하다. 대형 맵이 필요해지면 행동별 차이를 기록한다.
        self.history.append(deepcopy(self.state))
        candidate.moves += 1
        candidate.cleared = (
            candidate.player == self.level.exit
            and candidate.carrying is None
            and candidate.installed == self.level.traps
            and (not self.level.traps or candidate.active)
            and candidate.soldiers == self.level.posts
        )
        self.state = candidate
        if candidate.cleared:
            self.message = "던전 복구 완료! 출구로 돌아왔습니다."
        return True

    def undo(self) -> bool:
        if not self.history:
            self.message = "되돌릴 행동이 없습니다."
            return False
        self.state = self.history.pop()
        self.message = "직전 행동을 되돌렸습니다."
        return True

    def context_action(self) -> str:
        if self.state.cleared:
            return "복구 완료! 다음 방으로 진행"
        return self._interaction(self.state)[1]

    def plate_pressed(self, pos: Pos, state: State | None = None) -> bool:
        state = self.state if state is None else state
        return pos == state.player or pos in state.items

    def gate_status(self, pos: Pos, state: State | None = None) -> str:
        state = self.state if state is None else state
        if self.plate_pressed(self.level.gates[pos], state):
            return "open"
        if state.player == pos or pos in state.items:
            return "held"
        return "closed"

    def walkable(self, pos: Pos, state: State | None = None) -> bool:
        """진입 가능성만 판정한다. 닫힘 대기 문에서 이탈은 허용한다."""
        state = self.state if state is None else state
        return (0 <= pos[0] < self.level.width and 0 <= pos[1] < self.level.height
                and pos not in self.level.walls and pos not in state.soldiers
                and not (state.active and pos in self.level.traps)
                and (pos not in self.level.gates or self.gate_status(pos, state) == "open"))

    def _advance_belts(self, state: State) -> int:
        """행동 후의 동일한 배치를 기준으로 한 칸 이동을 동시에 확정한다."""
        fixed = self.level.traps | self.level.posts | self.level.benches | self.level.levers | self.level.chutes.keys() | {self.level.exit}
        candidates = {}
        for source, direction in self.level.belts.items():
            if state.items.get(source) not in {"part", "soldier"}:
                continue
            dx, dy = DIRECTIONS[direction]
            destination = source[0] + dx, source[1] + dy
            if (destination == state.player or destination in state.items or destination in fixed
                    or not self.walkable(destination, state)):
                continue
            candidates[source] = destination
        counts = Counter(candidates.values())
        moves = [(source, destination, state.items[source]) for source, destination in candidates.items()
                 if counts[destination] == 1]
        for source, _, _ in moves:
            del state.items[source]
        for _, destination, kind in moves:
            state.items[destination] = kind
        return len(moves)

    def _interaction(self, state: State) -> tuple[str | None, str]:
        """현재 칸에서 가능한 행동과 안내를 함께 결정한다."""
        pos = state.player
        if pos in state.items:
            if state.carrying is not None:
                return None, "손이 찼습니다. 먼저 내려놓으세요."
            return "pickup", f"E: {ITEM_NAMES[state.items[pos]]} 줍기"
        if pos in self.level.chutes:
            outlet = self.level.chutes[pos]
            if state.carrying != "bone":
                return None, f"{self.level.device_labels[pos]} 투입구: 뼈 묶음만 보낼 수 있습니다."
            if outlet == state.player or outlet in state.items or outlet in state.soldiers:
                return None, "배출구가 막혔습니다. 물건이나 병사를 치우세요."
            return "send_bone", f"E: {self.level.device_labels[pos]} 배출구로 뼈 보내기"
        if pos in self.level.traps:
            if pos in state.installed:
                return None, "이미 설치했습니다. 레버로 가동하세요."
            if state.carrying != "part":
                return None, "함정 부품을 가져오세요."
            return "install", "E: 함정 부품 설치"
        if pos in self.level.benches:
            stored = state.bench_bones.get(pos, 0)
            if state.carrying != "bone":
                return None, f"뼈 묶음을 가져오세요. ({stored}/2)"
            return "deliver", "E: 뼈 납품·병사 조립" if stored else "E: 뼈 납품 (1/2)"
        if pos in self.level.posts:
            if pos in state.soldiers:
                return None, "병사가 이미 배치되어 있습니다."
            if state.carrying != "soldier":
                return None, "조립한 병사를 가져오세요."
            return "deploy", "E: 해골 병사 배치"
        if pos in self.level.levers:
            if state.carrying is not None:
                return None, "레버는 빈손으로 가동하세요."
            if state.active:
                return None, "함정이 이미 가동되었습니다."
            if state.installed != self.level.traps:
                return None, "모든 함정을 먼저 설치하세요."
            if any(pos in state.items for pos in self.level.traps):
                return None, "함정 위의 물건을 먼저 치우세요."
            return "activate", "E: 모든 함정 가동"
        if pos == self.level.exit:
            return None, "복구를 마친 뒤 빈손으로 돌아오세요."
        if pos in self.level.plates:
            return None, f"{self.level.device_labels[pos]} 발판: Q로 물건을 놓아 문을 유지하세요."
        if pos in self.level.gates:
            return None, "문이 닫혀도 현재 칸에서 나갈 수 있습니다."
        if pos in self.level.belts:
            return None, "벨트: 부품·병사를 Q로 놓으세요. B로 한 차례 기다립니다."
        return None, "물건이나 장치 위에서 E를 누르세요."

    def _apply(self, state: State, action: str) -> tuple[bool, str]:
        if action == "wait":
            return True, "한 차례 기다렸습니다."
        if action in DIRECTIONS:
            dx, dy = DIRECTIONS[action]
            x, y = state.player
            destination = x + dx, y + dy
            if destination in self.level.gates and not self.walkable(destination, state):
                return False, "닫힌 문입니다. 연결 발판을 눌러 주세요."
            if not (0 <= destination[0] < self.level.width and 0 <= destination[1] < self.level.height) or destination in self.level.walls:
                return False, "벽으로 막힌 칸입니다."
            if state.active and destination in self.level.traps:
                return False, "가동된 함정은 지나갈 수 없습니다."
            if destination in state.soldiers:
                return False, "배치한 병사가 통로를 지키고 있습니다."
            state.player = destination
            return True, "한 칸 이동했습니다."

        if action == "drop":
            if state.carrying is None:
                return False, "들고 있는 물건이 없습니다."
            devices = self.level.traps | self.level.posts | self.level.benches | self.level.levers | self.level.chutes.keys() | {self.level.exit}
            if state.player in devices or state.player in state.items:
                return False, "빈 일반 바닥에만 내려놓을 수 있습니다."
            if state.player in self.level.belts and state.carrying == "bone":
                return False, "벨트에는 부품이나 조립한 병사만 놓을 수 있습니다."
            state.items[state.player] = state.carrying
            state.carrying = None
            return True, "물건을 바닥에 내려놓았습니다."

        operation, message = self._interaction(state)
        if operation is None:
            return False, message
        pos = state.player
        if operation == "send_bone":
            state.items[self.level.chutes[pos]] = "bone"
            state.carrying = None
            return True, "뼈 묶음을 연결된 배출구로 보냈습니다."
        if operation == "pickup":
            state.carrying = state.items.pop(pos)
            return True, f"운반 중: {ITEM_NAMES[state.carrying]}"
        if operation == "install":
            state.installed.add(pos)
            state.carrying = None
            return True, "함정을 설치했습니다. 아직 통과 가능합니다."
        if operation == "deliver":
            if state.bench_bones.get(pos, 0) == 0:
                state.bench_bones[pos] = 1
                state.carrying = None
                return True, "뼈를 납품했습니다. 한 묶음 더 필요합니다."
            del state.bench_bones[pos]
            state.carrying = "soldier"
            return True, "해골 병사를 조립해 들었습니다. 초소로 운반하세요."
        if operation == "deploy":
            state.soldiers.add(pos)
            state.carrying = None
            return True, "병사를 배치했습니다. 이 칸은 다시 들어올 수 없습니다."
        state.active = True
        return True, "모든 함정을 가동했습니다. 출구로 돌아가세요."
