"""벽과 소품 주위에서만 움직이는 방별 환경 효과."""

from math import cos, pi, sin

import pico2d.pico2d as p

from game.play_effects import alpha_blend

LIGHT_PROPS = frozenset({"lantern", "candle_sconce", "candles", "brazier", "crystal_sconce"})
SCENERY_PROPS = LIGHT_PROPS | {
    "sarcophagus", "books", "tool_rack", "air_vent", "wall_pipes", "elbow_pipe", "treasure", "throne",
}


def prop_kind(sprite):
    """사선 아트의 벽·소품 이름을 같은 환경 효과에 연결한다."""
    for part, kind in (
        ("mount_lamp", "lantern"), ("crypt_mount_sconce", "candle_sconce"),
        ("archive_mount_sconce", "crystal_sconce"), ("crypt_candles", "candles"),
        ("mount_tools", "tool_rack"), ("sarcophagus", "sarcophagus"), ("book_pile", "books"),
        ("mount_vent", "air_vent"), ("mount_pipes", "wall_pipes"), ("pipe_elbow", "elbow_pipe"),
        ("treasure_banner", "treasure_banner"), ("locked_coffer", "treasure"), ("brazier", "brazier"),
    ):
        if part in sprite:
            return kind
    return sprite


class RoomAtmosphere:
    def __init__(self, level, now):
        self.stage = level.id
        self.began = now

    def banner(self, now):
        return .028 * sin((now - self.began) * 1.65)

    def draw(self, kind, x, y, size, now, *, top_down):
        if kind not in SCENERY_PROPS:
            return
        age = max(0, now - self.began)
        phase = (x * .016 + y * .023) % (2 * pi)
        moment = (age + phase) % 9.5
        rare = moment / 1.15
        # 탑다운은 그림의 중심, 사선은 바닥 접점에서 시작한다.
        center_y = y if top_down else y + size * .32
        with alpha_blend():
            if kind in LIGHT_PROPS:
                self.light(kind, x, center_y, size, age, phase, rare)
            elif kind == "sarcophagus" and self.stage == "stage_02":
                for i in range(3):
                    dx = (sin(age * .64 + i) * .26 + i * .13) * size
                    p.draw_circle(x + dx, y - size * .12, 3 + i, 168, 177, 198, 23, filled=True)
            elif kind == "books" and self.stage == "stage_03" and rare < .56:
                lift = sin(pi * rare / .56)
                p.draw_line(x - size * .16, center_y, x + size * .11,
                            center_y + size * .19 * lift, 211, 191, 149, round(155 * lift))
            elif kind == "tool_rack" and self.stage == "stage_01" and rare < .66:
                shift = sin(rare * 17) * (1 - rare / .66) * size * .13
                p.draw_line(x + size * .11, center_y, x + size * .11 + shift,
                            center_y - size * .19, 197, 182, 148, round(124 * (1 - rare / .66)))
            elif self.stage == "stage_04" and kind == "air_vent" and rare < 1:
                self.drip(x + size * .14, y - size * .25, size, rare)
            elif self.stage == "stage_05" and kind in ("wall_pipes", "elbow_pipe"):
                flow = (age * .8 + phase) % 1
                px = x + (flow - .5) * size * .52
                p.draw_line(px - 4, y - size * .26, px + 3, y - size * .27, 125, 155, 163,
                            round(85 * sin(pi * flow)))
                if rare < 1:
                    self.drip(x + size * .14, y - size * .26, size, rare)
            elif self.stage == "stage_06" and kind == "air_vent":
                radius = size * .16
                for i in range(3):
                    angle = age * 4 + i * 2 * pi / 3
                    p.draw_line(x, center_y, x + cos(angle) * radius, center_y + sin(angle) * radius,
                                154, 166, 162, 99)
            elif self.stage == "stage_06" and kind == "elbow_pipe" and rare < 1:
                self.steam(x + size * .12, center_y, size, rare)
            elif self.stage == "stage_07" and kind == "treasure" and rare < .55:
                progress = rare / .55
                light_x = x + (progress - .5) * size * .48
                alpha = round(182 * sin(pi * progress))
                p.draw_line(light_x - 3, center_y + 2, light_x + 3, center_y + 2, 251, 213, 142, alpha)
                p.draw_line(light_x, center_y - 1, light_x, center_y + 5, 251, 213, 142, alpha)

    def throne_shadow(self, x, y, size, now):
        if self.stage != "stage_08":
            return
        drift = sin((now - self.began) * 1.2)
        with alpha_blend():
            for i in range(3):
                p.draw_circle(x + size * (.09 * drift + .083 * (i - 1)), y + size * .22,
                              max(3, round(size * (.17 + .05 * i))), 24, 13, 18, 27, filled=True)

    def light(self, kind, x, y, size, age, phase, rare):
        flicker = .72 + .18 * sin(age * 7 + phase) + .1 * sin(age * 11 + phase * 2)
        if kind == "crystal_sconce":
            p.draw_circle(x, y, max(2, round(size * .095)), 139, 198, 236,
                          round(63 * flicker), filled=True)
            return
        if self.stage == "stage_02" and kind in ("candle_sconce", "candles") and rare < .65:
            flicker *= .55 + .45 * cos(pi * rare / .65) ** 2
        length = max(3, round(size * .11))
        lean = sin(age * 6 + phase) * length * .46
        p.draw_line(x, y, x + lean, y + length * flicker, 250, 166, 82,
                    round(145 * flicker))
        if self.stage == "stage_01":
            for i in range(3):
                t = (age * .31 + phase + i * .31) % 1
                px = x + sin(t * 4 + i * 2) * size * .44
                p.draw_circle(px, y - t * size * .56, 1, 228, 188, 136,
                              round(84 * sin(pi * t)), filled=True)
        if kind == "brazier" and rare < 1:
            for i in range(3):
                t = rare - i * .16
                if 0 < t < .68:
                    px = x + sin(t * 8 + i) * size * .18
                    py = y + size * (.13 + t * .56)
                    p.draw_circle(px, py, 1 + (i % 2), 249, 149, 67,
                                  round(190 * sin(pi * t / .68)), filled=True)

    @staticmethod
    def drip(x, y, size, progress):
        if progress < .54:
            travel = (progress / .54) ** 2
            py = y + (1 - travel) * size * .5
            p.draw_line(x, py, x, py + 3, 137, 181, 193, 171)
        else:
            spread = (progress - .54) / .46
            opacity = round(105 * (1 - spread))
            width = 1 + spread * max(4, size * .17)
            p.draw_line(x - width, y, x + width, y, 148, 182, 187, opacity)
            p.draw_line(x - width * .7, y + 2, x + width * .7, y + 2, 148, 182, 187, opacity)

    @staticmethod
    def steam(x, y, size, progress):
        for i in range(4):
            offset = progress - .13 * i
            if 0 < offset < .64:
                px = x + size * (.34 * offset + .05 * i)
                py = y + size * (.85 * offset)
                p.draw_circle(px, py, max(2, round(size * (.05 + offset * .18))), 197, 210, 211,
                              round(75 * sin(pi * offset / .64)), filled=True)
