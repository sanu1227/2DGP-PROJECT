"""화면이나 실시간 프레임에 의존하지 않는 한 칸 단위 퍼즐."""

from copy import deepcopy
from dataclasses import dataclass, field

from game.levels import DIRECTIONS, Level, Pos, neighbors
from game.magic import MIRROR_DIRECTIONS, MIRROR_LABELS
from game.mechanics import trace_magic, fixed_devices


ITEM_NAMES = {"part": "함정 부품", "bone": "뼈 묶음", "soldier": "해골 병사"}
PUSH_ACTIONS = {f"push_{direction}": direction for direction in DIRECTIONS}
INTERACTION_HELP = "물건은 위에서, 작업대와 거울은 옆에서 E를 누르세요."


@dataclass(frozen=True)
class Recording:
    origin: Pos
    inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Echo:
    origin: Pos
    position: Pos
    remaining: tuple[str, ...]
    just_stepped: bool = False


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
    mirror_rotations: dict[Pos, int] = field(default_factory=dict)
    movable_mirrors: set[Pos] = field(default_factory=set)
    rubble: set[Pos] = field(default_factory=set)
    workers: set[Pos] = field(default_factory=set)
    recording: Recording | None = None
    echo: Echo | None = None
    replay_workers: dict[Pos, Pos] = field(default_factory=dict)
    recorded_stations: set[Pos] = field(default_factory=set)


class Game:
    def __init__(self, level: Level):
        self.level = level
        self.restart()

    def restart(self) -> None:
        rotations = {pos: MIRROR_DIRECTIONS.index(direction)
                     for pos, direction in self.level.mirror_directions.items()
                     if direction != MIRROR_DIRECTIONS[0]}
        self.state = State(player=self.level.start, items=dict(self.level.initial_items),
                           rubble=set(self.level.rubble), replay_workers=dict(self.level.replay_workers),
                           mirror_rotations=rotations,
                           movable_mirrors=set(self.level.movable_mirrors & self.level.mirrors))
        self.history: list[State] = []
        self.message = INTERACTION_HELP

    @property
    def remaining_actions(self) -> int | None:
        limit = self.level.action_limit
        return None if limit is None else max(0, limit - self.state.moves)

    @property
    def repair_percent(self) -> int:
        """현재 방의 복구 작업 진행률. 운반·출구 복귀는 작업량에 포함하지 않는다."""
        total = 2 * len(self.level.traps) + 3 * len(self.level.posts)
        if not total:
            return 100
        state = self.state
        assembled = sum(kind == "soldier" for kind in state.items.values()) + int(state.carrying == "soldier") + len(state.workers)
        done = (len(state.installed) + (len(self.level.traps) if state.active else 0)
                + sum(state.bench_bones.values()) + 2 * assembled + 3 * len(state.soldiers))
        return min(100, done * 100 // total)

    @property
    def ready_to_exit(self) -> bool:
        return not self.exit_requirements()

    def exit_requirements(self, state: State | None = None) -> tuple[str, ...]:
        """출구 칸에 도착하기 전에 충족해야 하는 조건."""
        state = self.state if state is None else state
        level = self.level
        remaining_traps = len(level.traps - state.installed)
        remaining_posts = len(level.posts - state.soldiers)
        requirements = []
        if remaining_traps:
            requirements.append(f"함정 {remaining_traps}개 설치 필요")
        elif level.traps and not state.active:
            requirements.append("레버로 함정 가동 필요")
        if remaining_posts:
            requirements.append(f"병사 {remaining_posts}명 배치 필요")
        if state.carrying is not None:
            requirements.append("물건을 내려놓으세요")
        if state.recording is not None:
            requirements.append("발걸음 기록을 마치세요")
        return tuple(requirements)

    @property
    def failed(self) -> bool:
        # 실패 여부를 행동 수에서 계산하므로 undo로 상태와 횟수가 함께 복구된다.
        return not self.state.cleared and self.remaining_actions == 0

    def act(self, action: str) -> bool:
        """성공한 상태 변경만 한 행동으로 기록한다. 실패는 안내만 바꾼다."""
        if action not in {*DIRECTIONS, *PUSH_ACTIONS, "interact", "drop"}:
            raise ValueError(f"알 수 없는 행동: {action}")
        if self.state.cleared:
            self.message = "복구 완료! 다음 방으로 진행하세요."
            return False
        if self.failed:
            self.message = "행동 횟수 소진! Z로 되돌리거나 R로 재시작하세요."
            return False

        candidate = deepcopy(self.state)
        changed, message = self._apply(candidate, action)
        self.message = message
        if not changed:
            return False
        recording = candidate.recording
        if recording and action in DIRECTIONS:
            self._record_step(candidate, action)
        if recording is None or recording.origin not in candidate.replay_workers:
            self._advance_echo(candidate)
        if (action in DIRECTIONS and recording is None and candidate.player in candidate.replay_workers
                and candidate.player not in candidate.recorded_stations
                and (candidate.echo is None or not candidate.echo.remaining)):
            candidate.echo = None
            candidate.recording = Recording(candidate.player)
            self.message = "기록 시작. 해골 인부에게 남길 방향으로 이동하세요."
        # ponytail: 최대 12×12칸에서는 전체 복사가 충분하다. 대형 맵이 필요해지면 행동별 차이를 기록한다.
        self.history.append(deepcopy(self.state))
        candidate.moves += 1
        candidate.cleared = candidate.player == self.level.exit and not self.exit_requirements(candidate)
        self.state = candidate
        if candidate.cleared:
            self.message = "던전 복구 완료! 출구로 돌아왔습니다."
        elif self.failed:
            self.message = "행동 횟수 소진! Z로 되돌리거나 R로 재시작하세요."
        return True

    def undo(self) -> bool:
        if not self.history:
            self.message = "되돌릴 행동이 없습니다."
            return False
        self.state = self.history.pop()
        self.message = "직전 행동을 되돌렸습니다."
        return True

    def context_action(self) -> str:
        if self.failed:
            return "실패 — Z / Backspace: 되돌리기 · R: 재시작"
        if self.state.cleared:
            return "복구 완료! 다음 방으로 진행"
        return self._interaction(self.state)[1]

    def can_interact(self) -> bool:
        return self.interaction_target() is not None

    def interaction_target(self) -> Pos | None:
        """E로 지금 조작할 수 있는 칸을 반환한다."""
        if self.state.cleared or self.failed:
            return None
        operation, _, target = self._interaction(self.state)
        return target if operation else None

    def plate_pressed(self, pos: Pos, state: State | None = None) -> bool:
        state = self.state if state is None else state
        return pos == state.player or pos in state.items or pos in state.rubble or pos in state.replay_workers.values()

    def echo_pressed(self, gate: Pos, state: State | None = None) -> bool:
        state = self.state if state is None else state
        echo = state.echo
        origin = self.level.gates[gate]
        if origin in self.level.plates:
            return self.plate_pressed(origin, state)
        seals, _ = self.level.echo_links[origin]
        if echo is None or echo.origin != origin or echo.position != seals[gate]:
            return False
        return origin not in self.level.timed_echoes or (echo.just_stepped and bool(echo.remaining))

    def gate_status(self, pos: Pos, state: State | None = None) -> str:
        state = self.state if state is None else state
        control = self.level.gates[pos]
        if control in self.level.receivers:
            powered = control in trace_magic(self.level, state)[1]
        elif control in self.level.echo_links:
            powered = self.echo_pressed(pos, state)
        elif control in self.level.jobs:
            powered = control in state.workers
        else:
            powered = self.plate_pressed(control, state)
        if powered:
            return "open"
        if state.player == pos or pos in state.items:
            return "held"
        return "closed"

    def walkable(self, pos: Pos, state: State | None = None) -> bool:
        """진입 가능성만 판정한다. 닫힘 대기 문에서 이탈은 허용한다."""
        state = self.state if state is None else state
        return (0 <= pos[0] < self.level.width and 0 <= pos[1] < self.level.height
                and pos not in self.level.walls and pos not in state.soldiers
                and pos not in state.rubble
                and pos not in state.movable_mirrors
                and pos not in self.level.solid_devices
                and not (state.active and pos in self.level.traps)
                and (pos not in self.level.gates or self.gate_status(pos, state) == "open"))

    def _interaction(self, state: State) -> tuple[str | None, str, Pos]:
        """현재 칸의 장치를 우선하고, 이어 옆 칸의 장치와 내려놓기를 확인한다."""
        pos = state.player
        standing = self._standing_interaction(state)
        if standing is not None and (standing[0] or state.recording):
            return *standing, pos
        nearby_hint = None
        solid_devices = self.level.solid_devices
        for target in neighbors(pos):
            if target in self.level.benches:
                stored = state.bench_bones.get(target, 0)
                if state.carrying == "bone":
                    return "deliver", "E: 뼈 납품·병사 조립" if stored else "E: 뼈 납품 (1/2)", target
                nearby_hint = nearby_hint or f"뼈 묶음을 가져오세요. ({stored}/2)"
            elif target in solid_devices or target in state.movable_mirrors:
                if state.carrying is None:
                    return "rotate", "E / Space: 거울 90도 회전 · 화살표 방향으로 빛 방출", target
                nearby_hint = nearby_hint or "거울은 빈손으로 돌리세요."
        if standing is not None:
            return *standing, pos
        if state.carrying is not None:
            return *self._drop_interaction(state), pos
        if nearby_hint:
            return None, nearby_hint, pos
        if pos in self.level.plates:
            return None, "발판에 물건을 놓으면 연결문을 열어 둘 수 있습니다.", pos
        if pos in self.level.gates:
            return None, "문이 닫혀도 현재 칸에서 나갈 수 있습니다.", pos
        return None, INTERACTION_HELP, pos

    def _standing_interaction(self, state: State) -> tuple[str | None, str] | None:
        pos = state.player
        if state.recording:
            _, steps = self.level.echo_links[state.recording.origin]
            return (None, f"발걸음 기록 {len(state.recording.inputs)}/{steps} · 방향키로 이동")
        if pos in state.items:
            if state.carrying is not None:
                return None, "손이 찼습니다. 먼저 내려놓으세요."
            return "pickup", f"E: {ITEM_NAMES[state.items[pos]]} 줍기"
        if pos in state.movable_mirrors:
            return (None, "거울은 빈손으로 돌리세요.") if state.carrying else ("rotate", "E / Space: 거울 90도 회전 · 화살표 방향으로 빛 방출")
        if pos in self.level.jobs:
            if pos in state.replay_workers:
                if pos in state.recorded_stations:
                    return None, "기록을 마친 발판입니다. Z로 되돌리거나 R로 다시 시작할 수 있습니다."
                return None, "기록 발판을 밟으면 자동으로 기록합니다."
            if pos in self.level.echo_links:
                if state.carrying:
                    return None, "발걸음을 기록하려면 손을 비우세요."
                _, steps = self.level.echo_links[pos]
                return "record", f"E / Space: 발걸음 {steps}칸 기록"
            if pos in state.workers:
                return (None, "인부를 회수하려면 손을 비우세요.") if state.carrying else ("recall", "E / Space: 해골 인부 회수")
            if state.carrying != "soldier":
                return None, "조립된 해골을 데려와 작업을 맡기세요."
            return "assign", "E / Space: 해골 인부 배치"
        if pos in self.level.chutes:
            outlet = self.level.chutes[pos]
            if state.carrying != "bone":
                return None, "투입구에는 뼈 묶음만 넣을 수 있습니다."
            if (outlet == state.player or outlet in state.items or outlet in state.soldiers
                    or outlet in state.rubble):
                return None, "배출구가 막혔습니다. 물건이나 병사를 치우세요."
            return "send_bone", "E: 연결된 배출구로 뼈 보내기"
        if pos in self.level.traps:
            if pos in state.installed:
                return None, "이미 설치했습니다. 레버로 가동하세요."
            if state.carrying != "part":
                return None, "함정 부품을 가져오세요."
            return "install", "E: 함정 부품 설치"
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
        return None

    def _drop_interaction(self, state: State) -> tuple[str | None, str]:
        """내려놓기 가능 여부를 입력 처리와 현재 칸 안내에 함께 사용한다."""
        if state.carrying is None:
            return None, "들고 있는 물건이 없습니다."
        devices = fixed_devices(self.level, state)
        if state.player in devices or state.player in state.items:
            return None, "빈 일반 바닥에만 내려놓을 수 있습니다."
        return "drop", f"E / Space: {ITEM_NAMES[state.carrying]} 내려놓기"

    def _push_mirror(self, state: State, direction: str) -> tuple[bool, str]:
        dx, dy = DIRECTIONS[direction]
        x, y = state.player
        source, target = (x + dx, y + dy), (x + 2 * dx, y + 2 * dy)
        if source not in state.movable_mirrors:
            return False, "그쪽 칸에 밀 수 있는 거울이 없습니다."
        if state.recording or state.carrying:
            return False, "기록을 마치고 손을 비운 뒤 거울을 미세요."
        level = self.level
        forbidden = (fixed_devices(level, state) | level.plates | level.gates.keys()
                     | set(level.chutes.values()) | state.items.keys() | set(state.replay_workers.values()))
        if not self.walkable(target, state) or target in forbidden:
            return False, "거울은 비어 있는 바닥으로만 밀 수 있습니다."
        state.movable_mirrors.remove(source)
        state.movable_mirrors.add(target)
        rotation = state.mirror_rotations.pop(source, 0)
        if rotation:
            state.mirror_rotations[target] = rotation
        state.player = source
        return True, "거울을 한 칸 밀었습니다. Z로 되돌릴 수 있습니다."

    def _apply(self, state: State, action: str) -> tuple[bool, str]:
        if action in PUSH_ACTIONS:
            return self._push_mirror(state, PUSH_ACTIONS[action])
        if action in DIRECTIONS:
            dx, dy = DIRECTIONS[action]
            x, y = state.player
            destination = x + dx, y + dy
            if destination in state.movable_mirrors:
                return self._push_mirror(state, action)
            if destination in state.rubble:
                if state.recording:
                    return False, "기록 중에는 발걸음만 남길 수 있습니다."
                target = destination[0] + dx, destination[1] + dy
                if destination in self.level.rubble_track and target not in self.level.rubble_track:
                    return False, "차광 블록은 바닥 레일을 따라 두 자리 사이에서만 움직입니다."
                forbidden = fixed_devices(self.level, state) | self.level.gates.keys()
                if (state.carrying or not self.walkable(target, state) or target in forbidden
                        or target in state.items or target in state.workers):
                    return False, "잔해는 빈손으로, 비어 있는 바닥·발판 쪽으로만 밀 수 있습니다."
                state.rubble.remove(destination)
                state.rubble.add(target)
                state.player = destination
                return True, "잔해를 한 칸 밀었습니다. Z로 되돌릴 수 있습니다."
            if self.walkable(destination, state):
                state.player = destination
                return True, "한 칸 이동했습니다."
            if destination in self.level.gates:
                control = self.level.gates[destination]
                if control in self.level.timed_echoes:
                    actor = "해골 인부" if control in state.replay_workers else "분신"
                    return False, f"{actor}가 문양을 밟은 직후 한 턴에만 들어갈 수 있습니다."
                return False, "닫힌 문입니다. 연결 장치의 상태를 확인하세요."
            if destination in self.level.solid_devices:
                return False, "장치가 길을 막고 있습니다. 옆 칸에서 E로 조작하세요."
            if state.active and destination in self.level.traps:
                return False, "가동된 함정은 지나갈 수 없습니다."
            if destination in state.soldiers:
                return False, "배치한 병사가 통로를 지키고 있습니다."
            return False, "벽이나 잔해로 막힌 칸입니다."

        if action == "drop":
            operation, message = self._drop_interaction(state)
            pos = state.player
        else:
            operation, message, pos = self._interaction(state)
        if operation is None:
            return False, message
        if operation == "record":
            state.echo = None
            state.recording = Recording(pos)
            if pos in self.level.timed_echoes:
                return True, "기록을 시작합니다. 문양을 지나는 걸음과 문에 도착할 때를 맞추세요."
            return True, "기록을 시작합니다. 분신이 머물 문양을 향해 이동하세요."
        if operation == "rotate":
            rotation = (state.mirror_rotations.get(pos, 0) + 1) % 4
            if rotation:
                state.mirror_rotations[pos] = rotation
            else:
                state.mirror_rotations.pop(pos, None)
            return True, f"거울 방출 방향 {MIRROR_LABELS[rotation]} ({rotation + 1}/4)."
        if operation == "assign":
            state.workers.add(pos)
            state.carrying = None
            return True, "해골 인부가 윈치를 돌려 문을 유지합니다."
        if operation == "recall":
            state.workers.remove(pos)
            state.carrying = "soldier"
            return True, "해골 인부가 돌아왔습니다. 다시 보내거나 초소로 데려가세요."
        if operation == "drop":
            state.items[pos] = state.carrying
            state.carrying = None
            return True, "물건을 바닥에 내려놓았습니다."
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

    def _record_step(self, state: State, action: str) -> None:
        recording = state.recording
        inputs = (*recording.inputs, action)
        _, steps = self.level.echo_links[recording.origin]
        if len(inputs) < steps:
            state.recording = Recording(recording.origin, inputs)
            return
        state.recording = None
        if recording.origin in state.replay_workers:
            state.recorded_stations.add(recording.origin)
            state.echo = Echo(recording.origin, state.replay_workers[recording.origin], inputs)
            self.message = "기록 완료. 다음 행동부터 해골 인부가 한 칸씩 움직입니다."
        else:
            state.player = recording.origin
            state.echo = Echo(recording.origin, recording.origin, inputs)
            self.message = "기록 발판으로 돌아왔습니다. 분신이 같은 발걸음을 따라갑니다."

    def _advance_echo(self, state: State) -> None:
        echo = state.echo
        if not echo or not echo.remaining:
            return
        dx, dy = DIRECTIONS[echo.remaining[0]]
        x, y = echo.position
        target = x + dx, y + dy
        position = target if self.walkable(target, state) else echo.position
        state.echo = Echo(echo.origin, position, echo.remaining[1:], position != echo.position)
        if echo.origin in state.replay_workers:
            state.replay_workers[echo.origin] = position
