"""만화 재생 시간에 맞춘 카메라 충격과 짧은 만화 효과."""

from ctypes import byref, c_int, c_ubyte
from dataclasses import dataclass
from math import cos, pi, sin

from game.character_motion import EXHALE_START, worker_motion


# (시작, 지속 시간, 최대 이동 픽셀). 수리공의 걸음에는 카메라 흔들림을 넣지 않는다.
IMPACTS = (
    ((.42, .62, 7),),
    ((.28, .46, 4),),
    (),
    ((.55, .62, 9), (1.30, .30, 4)),
)
CAMERA_MARGIN = 12


@dataclass(frozen=True)
class Impact:
    x: float = 0
    y: float = 0
    strength: float = 0


def sample_impact(index, age):
    """랜덤 상태나 실제 시계를 쓰지 않아 정지·다시 보기 결과가 동일하다."""
    x = y = strength = 0
    for start, duration, amplitude in IMPACTS[index]:
        q = (age - start) / duration
        if 0 <= q < 1:
            envelope = min(1, q / .08) * (1 - q) ** 1.4
            x += sin(q * pi * 8) * amplitude * envelope
            y += sin(q * pi * 11) * amplitude * .55 * envelope
            strength = max(strength, envelope)
    return Impact(x, y, strength)


def draw_effects(bounds, age, index, impact):
    # 시간 계산 검사는 SDL 창 없이 실행할 수 있게 그릴 때만 가져온다.
    import pico2d.pico2d as p

    left, bottom, right, top = bounds
    width = right - left
    blend = c_int()
    color = [c_ubyte() for _ in range(4)]
    p.SDL_GetRenderDrawBlendMode(p.renderer, byref(blend))
    p.SDL_GetRenderDrawColor(p.renderer, *(byref(value) for value in color))
    p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
    try:
        # 화면 가장자리에서 안쪽으로 모이는 선. 얼굴과 대사 영역은 비운다.
        if impact.strength:
            tint = (250, 118, 82) if index == 3 else (255, 224, 146)
            cx, cy = left + width * .45, bottom + 168
            alpha = round(180 * impact.strength)
            for ray in range(18):
                angle = ray * 2 * pi / 18 + .10
                reach = 1.12 + (ray % 3) * .08
                x1, y1 = cx + cos(angle) * 320, cy + sin(angle) * 250
                x2 = cx + cos(angle) * (210 + 16 * (1 - impact.strength)) * reach
                y2 = cy + sin(angle) * 140 * reach
                for offset in (-1, 0, 1):
                    p.draw_line(x1 + offset, y1, x2 + offset, y2, *tint, alpha)

        if index in (0, 1):
            # 검과 보물 주변의 작은 십자 반짝임.
            for delay, x, y in ((.60, .58, 152), (.83, .18, 250), (1.06, .48, 214)):
                q = (age - delay) / .65
                if 0 <= q < 1:
                    glow = sin(q * pi)
                    radius, alpha = 4 + 8 * glow, round(230 * glow)
                    cx, cy = left + width * x, bottom + y + q * 8
                    p.draw_line(cx - radius, cy, cx + radius, cy, 255, 232, 148, alpha)
                    p.draw_line(cx, cy - radius, cx, cy + radius, 255, 247, 208, alpha)
                    p.draw_circle(cx, cy, 2, 255, 251, 226, alpha, filled=True)

        if index == 2:
            # 발을 끌고 간 자리에 남았다가 흩어지는 먼지.
            for start in (.85, 1.35, 1.90, 2.40):
                q = (age - start) / .55
                if 0 <= q < 1:
                    origin = left + width * worker_motion(start).x - 10
                    for mote in range(4):
                        x = origin - (7 + mote * 6) * q - mote * 3
                        y = bottom + 47 + sin(q * pi) * (5 + mote * 2)
                        radius = round(2 + q * (2 + mote % 2))
                        alpha = round(120 * sin(pi * q) * (1 - mote * .12))
                        p.draw_circle(x, y, radius, 210, 190, 150, alpha, filled=True)
            # 한숨과 함께 내려가는 짧은 피로선. 캐릭터 자체는 흔들지 않는다.
            q = (age - EXHALE_START) / .95
            if 0 <= q < 1:
                alpha = round(185 * sin(q * pi))
                x = left + width * worker_motion(age).x
                for line in range(3):
                    px, py = x - 30 + line * 11, bottom + 282 - q * 15 - line * 3
                    p.draw_line(px, py, px + 1, py - 10 - line * 3, 116, 167, 191, alpha)
                    p.draw_line(px + 1, py, px + 2, py - 10 - line * 3, 116, 167, 191, alpha)
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, blend.value)
        p.SDL_SetRenderDrawColor(p.renderer, *(value.value for value in color))
