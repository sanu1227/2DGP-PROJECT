"""1번 방의 현재 퍼즐 상태에서 다음 연습 목표를 계산한다."""

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
    reminder: str
    targets: tuple[tuple[Pos, str], ...]
    links: tuple[tuple[Pos, Pos], ...] = ()


def device_lessons(level: Level, state: State | None = None) -> tuple[DeviceLesson, ...]:
    """지도에 실제로 있는 장치와 연결만 설명한다. 정답 경로는 제공하지 않는다."""
    lessons = []
    if level.traps and level.levers:
        lessons.append(DeviceLesson(
            "trap", "함정 설치와 가동", "부품을 들고 함정 위에서 E로 설치하세요. "
            "모든 함정을 설치한 뒤, 빈손으로 레버 위에서 E를 눌러 가동하세요.",
            "설치한 함정은 지나갈 수 있지만, 가동한 함정은 지나갈 수 없어요.",
            ((min(level.traps), "복구할 함정"), (min(level.levers), "가동 레버"))))
    if level.benches and level.posts:
        benches = sorted(level.benches)
        delivery = "한 작업대에 두 묶음을 모으세요. " if len(benches) > 1 else ""
        lessons.append(DeviceLesson(
            "assembly", "해골 병사 조립", "뼈 묶음을 하나씩 들고 작업대 옆 칸에서 E / Space로 납품하세요. "
            f"{delivery}완성된 병사는 손에 들립니다. 몬스터 배치대에서 E / Space로 배치하세요.",
            "병사를 배치한 칸은 다시 들어갈 수 없어요.",
            tuple((bench, "작업대") for bench in benches) + ((min(level.posts), "몬스터 배치대"),)))
    if level.plates:
        gate, plate = min((g,p) for g,p in level.gates.items() if p in level.plates)
        lessons.append(DeviceLesson(
            "plate", "무게로 여는 문", "발판 위에 서거나 물건을 놓으면 연결된 문이 열립니다. "
            "발판에서 무게가 사라지면 문이 닫힙니다.",
            "표시한 발판과 문은 서로 연결된 한 쌍이에요.",
            ((plate, "발판"), (gate, "연결문")), ((plate, gate),)))
    if level.chutes:
        inlet, outlet = min(level.chutes.items())
        lessons.append(DeviceLesson(
            "chute", "벽 너머로 뼈 보내기", "뼈를 들고 투입구 위에서 E / Space를 누르면 "
            "연결된 배출구로 보냅니다. 배출구가 물건이나 병사로 막혀 있으면 보낼 수 없어요.",
            "투입구에는 뼈만 넣을 수 있어요.",
            ((inlet, "뼈 투입구"), (outlet, "배출구")), ((inlet, outlet),)))
    rubble = level.rubble if state is None else state.rubble
    mirrors = level.mirrors if state is None else mirror_cells(level, state)
    for kind, title, instruction, reminder, cells in (
        ("rubble", "잔해를 밀어 길 만들기", "잔해 옆에서 빈손으로 잔해 쪽 방향키를 누르세요. 한 칸 밀며 이동합니다.",
         "당길 수 없어요. 빈 바닥·발판으로만 밀 수 있고, Z로 되돌릴 수 있어요.", rubble),
        ("mirror", "빛으로 장치 연결", "빈손으로 고정 거울 옆 칸에서 E / Space를 눌러 돌리세요. 빛은 화살표 방향으로 나갑니다.",
         "수신기에 닿으면 연결문이 열려요. 벽·잔해·초소의 병사·광원은 빛을 막아요.", mirrors),
        ("helper", "발걸음을 따라가는 해골 인부", "기록 발판을 밟고 표시된 칸 수만큼 자유롭게 이동하세요.",
         "기록석마다 한 번 기록해요. 인부가 발판 위에 머무르면 연결된 문도 열린 채로 유지돼요.", level.jobs)):
        if kind == "mirror" and level.movable_mirrors:
            movable = level.movable_mirrors if state is None else state.movable_mirrors
            targets = ((min(movable), "이동 거울"),)
            if rubble:
                targets += ((min(rubble), "빛을 막는 잔해"),)
            lessons.append(DeviceLesson(
                kind, "거울과 잔해로 광로 조절",
                "빈손으로 이동 거울 쪽 방향키를 누르면 밀어요. 거울 옆에서 E / Space로 돌리세요.",
                "잔해는 빛을 막아요. 방향키로 잔해를 광로 밖에 밀어내면 수신기에 닿은 빛이 문을 열어요.",
                targets))
        elif cells:
            lessons.append(DeviceLesson(kind, title, instruction, reminder, ((min(cells), title),)))
    if rubble and len(level.sources) > 1 and len(level.receivers) > 1:
        links = tuple((control, gate) for gate, control in sorted(level.gates.items())
                      if control in level.receivers)
        targets = ((min(rubble), "차광 블록"),) + tuple(
            (receiver, f"{level.device_labels[receiver]} 수신기") for receiver in sorted(level.receivers))
        lessons.append(DeviceLesson(
            "beam_switch", "두 광로 번갈아 열기",
            "블록 옆에서 빈손으로 방향키를 눌러 미세요. 한 광로를 막으면 반대편 수신기와 연결문이 켜져요.",
            "반대편으로 돌아가 블록을 다시 밀면 열린 문이 바뀌어요. 운반 중에는 뼈를 잠시 내려놓으세요.",
            targets, links))
    return tuple(lessons)


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
        instruction = ("E로 가동하세요. 가동한 함정은 통과 불가."
                       if state.player in level.levers else
                       "함정을 건너 레버에서 E를 누르세요.")
        return TutorialHint(4, "건너편에서 레버 가동", instruction, target, "레버 가동")
    if state.carrying == "part":
        target = min(level.traps - state.installed)
        instruction = ("E로 설치하세요. 설치 후 통과할 수 있어요."
                       if state.player == target else
                       "표시된 함정으로 이동해 E를 누르세요.")
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
