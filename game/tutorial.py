"""방의 장치 안내와 1번 방의 현재 연습 목표를 계산한다."""

from dataclasses import dataclass

from game.levels import Level, Pos
from game.mechanics import mirror_cells
from game.model import Game, State


@dataclass(frozen=True)
class TutorialHint:
    step: int
    title: str
    instruction: str
    target: Pos | None
    target_label: str = ""
    complete: bool = False


@dataclass(frozen=True)
class DeviceLesson:
    kind: str
    title: str
    instruction: str
    target: Pos


def device_lessons(level: Level, state: State | None = None) -> tuple[DeviceLesson, ...]:
    """지도에 실제로 있는 장치와 연결만 설명한다. 정답 경로는 제공하지 않는다."""
    lessons = []
    if level.traps and level.levers:
        lessons.extend((
            DeviceLesson("trap", "함정", "부품을 들고 함정 위에서 E로 설치해요.", min(level.traps)),
            DeviceLesson("trap", "가동 레버", "모든 함정을 고친 뒤 빈손으로 E를 눌러요.", min(level.levers)),
        ))
    if level.benches and level.posts:
        lessons.extend((
            DeviceLesson("assembly", "작업대", "옆에서 E로 뼈를 두 번 납품해요.", min(level.benches)),
            DeviceLesson("assembly", "몬스터 배치대", "완성한 병사를 들고 여기서 E를 눌러요.", min(level.posts)),
        ))
    if level.plates:
        gate, plate = min((gate, control) for gate, control in level.gates.items() if control in level.plates)
        lessons.extend((
            DeviceLesson("plate", "발판", "위에 서거나 물건을 올리면 문이 열려요.", plate),
            DeviceLesson("plate", "연결문", "발판에서 무게가 사라지면 닫혀요.", gate),
        ))
    if level.chutes:
        inlet, outlet = min(level.chutes.items())
        lessons.extend((
            DeviceLesson("chute", "뼈 투입구", "뼈를 들고 위에서 E를 누르면 보내요.", inlet),
            DeviceLesson("chute", "배출구", "이 칸이 비어 있어야 뼈를 받을 수 있어요.", outlet),
        ))
    rubble = level.rubble if state is None else state.rubble
    if rubble:
        if len(level.sources) > 1 and len(level.receivers) > 1:
            lessons.append(DeviceLesson("beam_switch", "차광 블록", "블록을 밀면 막히는 빛이 바뀌어요.", min(rubble)))
        else:
            lessons.append(DeviceLesson("rubble", "잔해", "빈손으로 잔해 쪽 방향키를 눌러 밀어요.", min(rubble)))
    movable = level.movable_mirrors if state is None else state.movable_mirrors
    mirrors = level.mirrors if state is None else mirror_cells(level, state)
    fixed = mirrors - movable
    if movable:
        lessons.append(DeviceLesson("mirror", "이동 거울", "빈손으로 방향키로 밀고, 옆에서 E로 돌려요.", min(movable)))
    if fixed:
        lessons.append(DeviceLesson("fixed_mirror", "고정 거울", "빈손으로 거울 옆에서 E를 눌러 돌려요.", min(fixed)))
    if level.receivers:
        lessons.append(DeviceLesson("receiver", "빛 수신기", "빛이 닿으면 연결문이 열려요.", min(level.receivers)))
    if level.echo_links:
        station = min(level.echo_links)
        workers = level.replay_workers if state is None else state.replay_workers
        has_worker = station in workers
        recording = "밟은 뒤 움직이면 발걸음이 기록돼요." if has_worker else "빈손으로 E를 눌러 기록을 시작해요."
        lessons.append(DeviceLesson("helper", "기록 발판", recording, station))
        if has_worker:
            lessons.append(DeviceLesson("helper", "해골 인부", "기록한 방향을 차례로 따라가요.", workers[station]))
        seals, _ = level.echo_links[station]
        seal = min(seals.values())
        title = "무게 발판" if seal in level.plates else "기록 문양"
        actor = "인부" if has_worker else "분신"
        lessons.append(DeviceLesson("helper", title, f"{actor}가 올라서면 연결문이 열려요.", seal))
    winches = level.jobs - level.echo_links.keys()
    if winches:
        lessons.append(DeviceLesson("winch", "작업 윈치", "조립한 병사를 들고 위에서 E를 눌러요.", min(winches)))
    return tuple(lessons)


def device_introductions(levels):
    """각 장치의 첫 등장 방에 입장 안내를 배정한다."""
    known = set()
    introductions = {}
    for level in levels:
        lessons = device_lessons(level)
        introductions[level.id] = tuple(lesson for lesson in lessons if lesson.kind not in known
                                        and (level.id, lesson.kind) != ("stage_01", "trap"))
        known.update(lesson.kind for lesson in lessons)
    return introductions


def first_room_hint(game: Game) -> TutorialHint | None:
    """별도 진행 기록을 두지 않아 내려놓기·되돌리기·재시작에도 일치한다."""
    if game.level.id != "stage_01":
        return None
    state, level = game.state, game.level
    if state.cleared:
        return TutorialHint(5, "첫 복구 완료!", "E / Space로 다음 방에 입장하세요.",
                            None, complete=True)
    if state.active:
        return TutorialHint(5, "빈손으로 출구 복귀", "가동된 함정을 피해 출구로 가세요.",
                            level.exit, "출구로 이동")
    if state.installed == level.traps:
        target = min(level.levers)
        instruction = ("E로 가동. 가동하면 통과 불가."
                       if state.player in level.levers else
                       "함정을 건너 레버에서 E를 누르세요.")
        return TutorialHint(4, "건너편에서 레버 가동", instruction, target, "레버 가동")
    if state.carrying == "part":
        target = min(level.traps - state.installed)
        instruction = ("E로 설치. 가동 전엔 통과 가능."
                       if state.player == target else
                       "함정 위에서 E를 누르세요.")
        return TutorialHint(3, "함정에 부품 설치", instruction, target, "함정에 설치")
    parts = sorted(pos for pos, kind in state.items.items() if kind == "part")
    if parts:
        target = state.player if state.player in parts else parts[0]
        if state.player == target:
            return TutorialHint(2, "부품 줍기", "부품 위에서 E를 누르세요.",
                                target, "E / Space")
        return TutorialHint(1, "부품까지 이동", "부품 클릭 또는 WASD / 방향키",
                            target, "부품으로 이동")
    return None
