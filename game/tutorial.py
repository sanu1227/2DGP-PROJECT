"""1번 방의 현재 퍼즐 상태에서 다음 연습 목표를 계산한다."""

from dataclasses import dataclass

from game.levels import Pos
from game.model import Game


@dataclass(frozen=True)
class TutorialHint:
    step: int
    title: str
    instruction: str
    target: Pos | None
    target_label: str = ""
    complete: bool = False


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
