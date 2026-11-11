"""왼쪽 위부터 쌓이는 네 컷의 야근 코미디와 재생 상태."""
from dataclasses import dataclass
from game.character_motion import MOTION_END

@dataclass(frozen=True)
class StoryPage:
    atlas: str
    cell: int
    dialogue: tuple[tuple[str, ...], tuple[str, ...]]
    effect: str

STORY = (
    StoryPage("overtime_01", 0, (
        ("용사", "마왕의 던전이여!", "이 용사가 왔다!"),
        ("해골 병사", "저 오늘 첫", "출근인데요?!"),
    ), "두둥!"),
    StoryPage("overtime_01", 2, (
        ("용사", "정복 끝! 보물도", "챙겼으니 퇴근!"),
        ("해골 병사", "함정도 저도 박살!", "수리티이임!!"),
    ), "정복 완료!"),
    StoryPage("overtime_01", 3, (
        ("수리공 (당신)", "하... 오늘도 야근.", "난 또 뒷정리네."),
        ("해골 병사", "함정 말고 제 몸부터!", "허리가 없어요!"),
    ), "터덜..."),
    StoryPage("overtime_02", 0, (
        ("마왕 (상사)", "함정이랑 병사들,", "내일까지 고쳐 놔!"),
        ("수리공 (당신)", "네... 수리할게요.", "제 퇴근도 고쳐줘요."),
    ), "야근 확정!"),
)

PANEL_SECONDS = 6.5
BALLOON_DELAYS = (0.55, 1.8)
REVEAL_SECONDS = MOTION_END

@dataclass
class ComicPlayback:
    """시간 기반 재생. 마지막 컷은 자동으로 안내 화면을 넘기지 않는다."""
    index: int = 0
    elapsed: float = 0.0
    paused: bool = False

    @property
    def finished(self):
        return self.index == len(STORY) - 1 and self.elapsed >= PANEL_SECONDS

    def reset(self):
        self.index, self.elapsed, self.paused = 0, 0.0, False

    def update(self, seconds):
        if self.paused:
            return
        self.elapsed += max(0.0, seconds)
        while self.elapsed >= PANEL_SECONDS and self.index < len(STORY) - 1:
            self.elapsed -= PANEL_SECONDS
            self.index += 1
        self.elapsed = min(self.elapsed, PANEL_SECONDS)

    def advance(self):
        if self.index == len(STORY) - 1:
            return False
        self.index += 1
        self.elapsed = 0.0
        return True

    def back(self):
        if self.index == 0:
            return False
        self.index -= 1
        self.elapsed, self.paused = REVEAL_SECONDS, True
        return True

    def age(self, index):
        if index > self.index:
            return None
        return PANEL_SECONDS if index < self.index else self.elapsed
