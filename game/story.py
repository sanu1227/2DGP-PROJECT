"""오프닝, 중간 이야기, 엔딩의 네 컷 만화 대사와 재생 상태."""
from dataclasses import dataclass
from game.character_motion import MOTION_END

@dataclass(frozen=True)
class StoryPage:
    atlas: str
    cell: int
    dialogue: tuple[tuple[str, ...], ...]
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

MIDPOINT = (
    StoryPage("midpoint_gate", 0, (
        ("수리공", "좋아, 네 구역 끝.", "이제 퇴근인가?"),
        ("해골 병사", "철문도 이제", "잘 열리네요!"),
    ), "철컥!"),
    StoryPage("midpoint_checklist", 0, (
        ("수리공", "잠깐, 뒷면에도", "네 칸이 있잖아."),
        ("해골 병사", "반장님, 이거", "양면이에요."),
    ), "팔락!"),
    StoryPage("midpoint_light", 0, (
        ("수리공", "빛이 또 꺼졌네.", "불부터 살려야겠어."),
    ), "깜빡"),
    StoryPage("midpoint_toolbox", 0, (
        ("수리공", "공구함아, 너도", "퇴근인 줄 알았지?"),
    ), "영차!"),
)

ENDING = (
    StoryPage("ending_repair", 0, (
        ("해골 인부", "반장님! 마지막", "장치도 잘 돌아가요!"),
        ("수리공", "좋아, 여덟 구역", "전부 복구 완료."),
    ), "철컥!"),
    StoryPage("ending_hero", 0, (
        ("수리공", "잠깐, 또 던전을", "정복하러 왔어요?"),
        ("용사", "아뇨. 두고 간", "장갑만 찾으러요."),
    ), "머쓱..."),
    StoryPage("ending_report", 0, (
        ("수리공", "그럼 이제 제 퇴근도", "승인해 주세요."),
        ("마왕", "승인! 오늘은", "내가 문단속하마."),
    ), "쾅!"),
    StoryPage("ending_dawn", 0, (
        ("해골 인부", "반장님, 오늘은", "푹 쉬고 오세요!"),
        ("수리공", "고맙다. 너희도", "작업등 끄고 쉬어."),
    ), "야근 끝!"),
)

# 짧은 컷은 바로 이어지고, 수리공 컷만 한숨을 마칠 시간을 확보한다.
PANEL_DURATIONS = (3.5, 3.5, 5.0, 3.5)
MIDPOINT_DURATIONS = (4.0, 4.5, 4.5, 4.5)
ENDING_DURATIONS = (4.5, 5.0, 5.0, 5.0)
BALLOON_DELAYS = (0.55, 1.8)
REVEAL_SECONDS = MOTION_END

@dataclass
class ComicPlayback:
    """시간 기반 재생. 마지막 컷은 자동으로 안내 화면을 넘기지 않는다."""
    index: int = 0
    elapsed: float = 0.0
    paused: bool = False
    durations: tuple[float, ...] = PANEL_DURATIONS

    @property
    def duration(self):
        return self.durations[self.index]

    @property
    def finished(self):
        return self.index == len(self.durations) - 1 and self.elapsed >= self.duration

    def reset(self):
        self.index, self.elapsed, self.paused = 0, 0.0, False

    def update(self, seconds):
        if self.paused:
            return
        self.elapsed += max(0.0, seconds)
        while self.elapsed >= self.duration and self.index < len(self.durations) - 1:
            self.elapsed -= self.duration
            self.index += 1
        self.elapsed = min(self.elapsed, self.duration)

    def advance(self):
        if self.index == len(self.durations) - 1:
            return False
        self.index += 1
        self.elapsed = 0.0
        return True

    def back(self):
        if self.index == 0:
            return False
        self.index -= 1
        self.elapsed, self.paused = min(REVEAL_SECONDS, self.duration), True
        return True

    def age(self, index):
        if index > self.index:
            return None
        return self.durations[index] if index < self.index else self.elapsed
