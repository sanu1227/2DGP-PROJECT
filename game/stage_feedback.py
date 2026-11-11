"""방 입장과 출구 복귀를 알리는 연출. 게임 판정과 행동 수는 변경하지 않는다."""

from math import cos, exp, pi, sin

import pico2d.pico2d as p

from game.front_end import Button, bevel
from game.logo_mode import fade_to_black

INK = (239, 237, 219)
MUTED = (164, 182, 177)
GOLD = (231, 190, 108)
TEAL = (112, 216, 190)
ENTRY_SECONDS = 1.6


class StageFeedback:
    def __init__(self):
        self.game = None
        self.entered_at = 0.0
        self.completed_at = None

    def enter(self, game, now):
        self.game = game
        self.entered_at = now
        self.completed_at = None

    def update(self, game, now):
        if self.game is not game:
            self.enter(game, now)
        if game.state.cleared:
            if self.completed_at is None:
                self.completed_at = now
        else:
            # 완료 행동을 되돌리면 결과 화면도 즉시 사라진다.
            self.completed_at = None

    @staticmethod
    def next_button(index, total):
        label = "처음부터 다시" if index + 1 == total else "다음 방으로"
        return Button("next", label, (600, 240, 1000, 304))

    def draw(self, view, game, index, total):
        now = view.now()
        if game.state.cleared:
            self.draw_result(view, game, index, total, max(0, now - self.completed_at))
        elif game.state.moves == 0 and 0 <= now - self.entered_at < ENTRY_SECONDS:
            self.draw_entry(view, game, index, total, now - self.entered_at)

    @staticmethod
    def draw_entry(view, game, index, total, elapsed):
        # 안내와 메뉴에서는 플레이 시계가 멈추므로 배너 재생 시간도 보존된다.
        progress = min(1, elapsed / .22, (ENTRY_SECONDS - elapsed) / .25)
        lift = round(32 * (1 - max(0, progress)) ** 2)
        bevel((466, 650 + lift, 1134, 796 + lift), (22, 39, 43), TEAL)
        view.centered(800, 767 + lift, f"제 {index + 1:02d} 구역  /  {total:02d}", 18, TEAL)
        view.centered(800, 723 + lift, game.level.title, 32, INK)
        view.centered(800, 680 + lift, "복구 작업 시작", 22, GOLD)

    def draw_result(self, view, game, index, total, elapsed):
        fade_to_black(.64)
        bevel((390, 180, 1210, 808), (23, 37, 41), (104, 139, 127))
        view.centered(800, 766, f"제 {index + 1:02d} 구역 작업 보고", 22, GOLD)
        # 도장이 찍힌 뒤 살짝 튀었다가 멈춘다. 화면 전체는 흔들지 않는다.
        bounce = round(32 * exp(-elapsed * 12) * cos(elapsed * 21))
        y = 659 + bounce
        bevel((528, y - 54, 1072, y + 54), (30, 73, 64), TEAL)
        p.draw_rectangle(538, y - 44, 1062, y + 44, *TEAL)
        view.centered(800, y, "복구 완료!", 64, INK)
        if elapsed < .65:
            radius = 285 + elapsed * 90
            for i in range(12):
                angle = i * pi / 6
                x1, y1 = 800 + cos(angle) * radius, 659 + sin(angle) * radius * .25
                x2, y2 = 800 + cos(angle) * (radius + 14), 659 + sin(angle) * (radius + 14) * .25
                p.draw_line(x1, y1, x2, y2, *GOLD)
        view.centered(800, 564, game.level.title, 26, INK)
        for center, label, value in (
                (620, "사용 행동", f"{game.state.moves}회"),
                (980, "남은 행동", "무제한" if game.remaining_actions is None else f"{game.remaining_actions}회")):
            bevel((center - 150, 414, center + 150, 520), (31, 49, 52), (72, 104, 98))
            view.centered(center, 493, label, 18, MUTED)
            view.centered(center, 450, value, 32, TEAL)
        tasks = []
        if game.level.traps:
            tasks.append(f"함정 {len(game.state.installed)} / {len(game.level.traps)} 가동")
        if game.level.posts:
            tasks.append(f"병사 {len(game.state.soldiers)} / {len(game.level.posts)} 배치")
        view.centered(800, 378, "   ·   ".join(tasks) + "   ·   출구 복귀 완료", 18, INK)
        if index + 1 == total:
            view.centered(800, 337, "모든 구역 복구 완료. 오늘의 근무를 마쳤습니다!", 22, GOLD)
        button = self.next_button(index, total)
        hovered = view.mouse_position is not None and button.contains(view.mouse_position)
        bevel(button.bounds, (61, 116, 100) if hovered else (43, 86, 76), TEAL)
        view.centered(800, 272, button.label, 26, INK)
        view.centered(800, 211, "E / Space 또는 버튼 클릭", 16, MUTED)
        view.centered(800, 130, "Z 되돌리기    R 다시 시작    Esc 메뉴", 18, INK)
