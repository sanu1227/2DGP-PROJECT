"""1번 방의 현재 퍼즐 상태에서 다음 연습 목표를 계산한다."""

from dataclasses import dataclass

from game.levels import Level, Pos
from game.model import Game


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


def device_lessons(level: Level) -> tuple[DeviceLesson, ...]:
    """지도에 실제로 있는 장치와 연결만 설명한다. 정답 경로는 제공하지 않는다."""
    lessons = []
    if level.traps and level.levers:
        lessons.append(DeviceLesson(
            "trap", "함정 설치와 가동", "부품을 들고 함정 위에서 E로 설치하세요. "
            "모든 함정을 설치한 뒤, 빈손으로 레버 위에서 E를 눌러 가동하세요.",
            "설치한 함정은 지나갈 수 있지만, 가동한 함정은 지나갈 수 없어요.",
            ((min(level.traps), "복구할 함정"), (min(level.levers), "가동 레버"))))
    if level.benches and level.posts:
        bench, post = min(level.benches), min(level.posts)
        lessons.append(DeviceLesson(
            "assembly", "해골 병사 조립", "뼈 묶음 2개를 작업대에 하나씩 가져와 E / Space로 납품하세요. "
            "완성된 병사는 손에 들립니다. 몬스터 배치대에서 E / Space로 배치하세요.",
            "병사를 배치한 칸은 다시 들어갈 수 없어요.",
            ((bench, "작업대"), (post, "몬스터 배치대"))))
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
    for kind, title, instruction, reminder, cells in (
        ("rubble", "잔해를 밀어 길 만들기", "잔해 옆에서 빈손으로 잔해 쪽 방향키를 누르세요. 한 칸 밀며 이동합니다.",
         "당길 수 없어요. 빈 바닥·발판으로만 밀 수 있고, Z로 되돌릴 수 있어요.", level.rubble),
        ("mirror", "빛으로 장치 연결", "거울 위에서 빈손으로 E / Space를 눌러 90도 돌리세요. 수신기에 빛이 닿으면 연결문이 열립니다.",
         "벽·잔해·초소의 병사는 빛을 막아요. 사람·운반물·문은 막지 않아요.", level.mirrors),
        ("water", "수로와 부교 바꾸기", "밸브 위에서 빈손으로 E / Space를 누르세요. 낮은 수위에는 수로, 높은 수위에는 부교를 건널 수 있어요.",
         "잠길 수로나 내려갈 부교 위의 물건부터 회수하세요.", level.valves),
        ("helper", "함께 일하는 해골", "조립한 해골을 윈치로 가져와 E / Space로 배치하세요. 인부가 일하는 동안 문이 열립니다.",
         "빈손으로 윈치에서 E를 누르면 회수해요. 최종 초소 배치는 되돌리기로만 취소해요.", level.jobs)):
        if cells:
            lessons.append(DeviceLesson(kind, title, instruction, reminder, ((min(cells), title),)))
    return tuple(lessons)


def first_room_hint(game: Game) -> TutorialHint | None:
    """별도 진행 기록을 두지 않아 내려놓기·되돌리기·재시작에도 일치한다."""
    if game.level.id != "stage_01":
        return None
    state, level = game.state, game.level
    if state.cleared:
        return TutorialHint(5, "첫 복구 완료!", "E / Space를 눌러 2번 방에서 병사 복구를 배워 보세요.",
                            None, complete=True)
    if state.active:
        return TutorialHint(5, "빈손으로 출구 복귀", "함정이 가동되어 길이 막혔어요. 표시된 출구까지 이동하면 완료!",
                            level.exit, "출구로 이동")
    if state.installed == level.traps:
        target = min(level.levers)
        instruction = ("E / Space로 가동하세요. 가동한 함정은 다시 지나갈 수 없어요."
                       if state.player in level.levers else
                       "설치한 함정을 건너 레버로 이동하세요. 레버 위에서 E / Space로 가동!")
        return TutorialHint(4, "건너편에서 레버 가동", instruction, target, "레버 가동")
    if state.carrying == "part":
        target = min(level.traps - state.installed)
        instruction = ("E / Space를 눌러 부품을 설치하세요. 설치만 한 함정은 지나갈 수 있어요."
                       if state.player == target else
                       "표시된 함정으로 부품을 옮기세요. 함정과 같은 칸에서 E / Space로 설치!")
        return TutorialHint(3, "함정에 부품 설치", instruction, target, "함정에 설치")
    parts = sorted(pos for pos, kind in state.items.items() if kind == "part")
    if parts:
        target = state.player if state.player in parts else parts[0]
        if state.player == target:
            return TutorialHint(2, "부품 줍기", "E / Space를 눌러 부품을 드세요. 도착만 해서는 자동으로 줍지 않아요.",
                                target, "E / Space")
        return TutorialHint(1, "부품까지 이동", "표시된 부품을 클릭하세요. WASD / 방향키로 한 칸씩 이동해도 좋아요.",
                            target, "부품으로 이동")
    return None
