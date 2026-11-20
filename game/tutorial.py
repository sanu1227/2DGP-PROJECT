"""방의 장치 안내와 1번 방의 현재 연습 목표를 계산한다."""

from dataclasses import dataclass

from game.levels import Level, Pos
from game.mechanics import mirror_cells
from game.model import ITEM_NAMES, Game, State


@dataclass(frozen=True)
class TutorialHint:
    step: int
    title: str
    instruction: str
    target: Pos | None
    target_label: str = ""
    complete: bool = False
    persistent: bool = False


@dataclass(frozen=True)
class DeviceLesson:
    kind: str
    title: str
    instruction: str
    target: Pos


def device_lessons(level: Level, state: State | None = None) -> tuple[DeviceLesson, ...]:
    """현재 방의 물건과 장치에서 실제로 할 수 있는 행동을 설명한다."""
    lessons = []
    items = level.initial_items if state is None else state.items
    for kind, instruction in (
        ("part", "함정 하나를 고치는 데 부품 하나가 필요해요."),
        ("bone", "해골 병사를 만드는 재료예요."),
        ("soldier", "초소에 바로 배치할 수 있는 병사예요."),
    ):
        target = min((pos for pos, item in items.items() if item == kind), default=None)
        if target is not None:
            lessons.append(DeviceLesson(kind, ITEM_NAMES[kind], instruction, target))
    if level.traps and level.levers:
        lessons.append(DeviceLesson("trap", "함정", "부품을 들고 함정 칸에서 설치해요.", min(level.traps)))
        lever_hint = "함정을 모두 설치한 뒤 레버 칸에서\n빈손으로 레버를 당겨요."
        if level.circuits:
            lessons.append(DeviceLesson("blueprint", "수리공의 마력 배선",
                                        "부품을 설치한 뒤 B를 누르면 실제 그림판이 열려요.\n"
                                        "검은색 선 도구로 같은 번호의 두 단자를 이어요.\n"
                                        "Ctrl+S로 저장하면 던전에 배선이 생겨요.", min(level.traps)))
            lever_hint = "배선을 저장한 뒤 게임으로 돌아와요.\n함정을 건너 레버에서 E를 누르면 가동돼요."
        lessons.append(DeviceLesson("trap", "가동 레버", lever_hint, min(level.levers)))
    if level.benches and level.posts:
        lessons.extend((
            DeviceLesson("assembly", "작업대", "작업대 옆 칸에서 뼈를 한 묶음씩 넣어요.\n"
                         "같은 작업대에 두 묶음을 모으면 병사가 완성돼요.", min(level.benches)),
            DeviceLesson("assembly", "초소", "병사를 배치하면 이 칸을 지나갈 수 없어요.", min(level.posts)),
        ))
    if level.plates:
        gate, plate = min((gate, control) for gate, control in level.gates.items() if control in level.plates)
        lessons.extend((
            DeviceLesson("plate", "발판", "직접 밟거나 물건을 올려 연결문을 열어요.", plate),
            DeviceLesson("plate", "연결문", "발판이 비면 문이 닫혀요.", gate),
        ))
    if level.chutes:
        inlet, outlet = min(level.chutes.items())
        lessons.extend((
            DeviceLesson("chute", "뼈 투입구", "뼈를 넣으면 연결된 배출구로 나와요.", inlet),
            DeviceLesson("chute", "배출구", "배출구 칸을 비워 두어야 뼈를 보낼 수 있어요.", outlet),
        ))
    rubble = level.rubble if state is None else state.rubble
    if rubble:
        if len(level.sources) > 1 and len(level.receivers) > 1:
            lessons.append(DeviceLesson("beam_switch", "차광 블록", "블록을 밀어 광선을 가려요.\n"
                                        "빛이 닿는 수신기에 따라 열리는 문이 달라져요.", min(rubble)))
        else:
            lessons.append(DeviceLesson("rubble", "잔해", "빈손으로 잔해를 향해 움직이면 한 칸 밀 수 있어요.", min(rubble)))
    movable = level.movable_mirrors if state is None else state.movable_mirrors
    mirrors = level.mirrors if state is None else mirror_cells(level, state)
    fixed = mirrors - movable
    if movable:
        lessons.append(DeviceLesson("mirror", "이동 거울", "빈손으로 거울을 향해 움직이면 밀 수 있어요.\n"
                                    "옆 칸에서 거울을 돌려 빛의 방향을 바꿔요.", min(movable)))
    if fixed:
        lessons.append(DeviceLesson("fixed_mirror", "고정 거울", "빈손으로 거울 옆 칸에 서서 돌려요.\n"
                                    "빛은 거울의 화살표 방향으로 나가요.", min(fixed)))
    if level.receivers:
        receiver_hint = ("빛이 닿은 수신기가 전원을 공급해요.\n전원이 들어온 수신기와 배선으로 이은 문이 열려요."
                         if level.circuits else "빛이 수신기에 닿아 있는 동안 연결문이 열려요.")
        lessons.append(DeviceLesson("receiver", "빛 수신기", receiver_hint, min(level.receivers)))
        if len(level.circuits) > 1:
            lessons.append(DeviceLesson("rewiring", "마력 배선으로 문 바꾸기",
                                        "B로 그림판을 열고 검은 선으로 같은 번호를 이어요.\n"
                                        "1번은 창고 문, 2번은 출구 문이에요. 한 쌍만 연결할 수 있어요.\n"
                                        "문을 바꿀 때는 기존 선을 흰색으로 지우고 새로 이은 뒤 Ctrl+S.",
                                        level.circuits[0].path[-1]))
    if level.echo_links:
        station = min(level.echo_links)
        workers = level.replay_workers if state is None else state.replay_workers
        has_worker = station in workers
        seals, steps = level.echo_links[station]
        recording = (f"발판을 밟은 뒤 {steps}칸 움직이면 이동 방향이 기록돼요." if has_worker
                     else f"빈손으로 발판에서 기록을 시작해요.\n그다음 {steps}칸 움직여요.")
        lessons.append(DeviceLesson("helper", "기록 발판", recording, station))
        if has_worker:
            lessons.append(DeviceLesson("helper", "해골 인부", "기록이 끝난 뒤 수리공이 행동할 때마다\n"
                                        "인부도 기록한 방향으로 한 칸씩 움직여요.", workers[station]))
        seal = min(seals.values())
        title = "무게 발판" if seal in level.plates else "기록 문양"
        actor = "인부가" if has_worker else "분신이"
        effect = (f"{actor} 이 칸을 밟으면 연결문이 잠깐 열려요." if station in level.timed_echoes
                  else f"{actor} 이 칸을 밟고 있는 동안 연결문이 열려요.")
        lessons.append(DeviceLesson("helper", title, effect, seal))
    winches = level.jobs - level.echo_links.keys()
    if winches:
        lessons.append(DeviceLesson("winch", "작업 윈치", "병사를 들고 윈치 칸에서 배치해요.\n"
                                    "배치한 인부가 연결문을 열어 둬요.", min(winches)))
    return tuple(lessons)


def device_introductions(levels):
    """각 물건과 장치의 첫 등장 방에 입장 안내를 배정한다."""
    known = set()
    introductions = {}
    for level in levels:
        lessons = device_lessons(level)
        introductions[level.id] = tuple(lesson for lesson in lessons if lesson.kind not in known)
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
        if level.circuits and not state.circuit:
            return TutorialHint(4, "마력 배선 복구", "B로 그림판 열기\n검은 선을 잇고 Ctrl+S",
                                None, persistent=True)
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
