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
class PanelBeat:
    time: float
    focus: tuple[float, float]
    effect: str
    sound: str
    color: tuple[int, int, int]
    shake: float = 0
    before: str | None = None
    after: str | None = None


PANEL_BEATS = {
    "midpoint_gate": PanelBeat(.74, (.68, .24), "impact", "impactTin_medium_000", (255, 216, 145),
                               5, before="midpoint_gate_closed"),
    "midpoint_checklist": PanelBeat(.94, (.52, .64), "swoosh", "cloth1", (255, 242, 199),
                                    2, before="midpoint_checklist_front"),
    "midpoint_light": PanelBeat(1.0, (.9, .57), "fizzle", "metalPot1", (216, 153, 251),
                                after="midpoint_light_off"),
    "midpoint_toolbox": PanelBeat(1.48, (.48, .18), "dust", "worker_sigh", (220, 179, 129),
                                  before="midpoint_toolbox_down"),
    "ending_repair": PanelBeat(.68, (.47, .39), "sparkle", "impactTin_medium_000", (255, 220, 112), 2),
    "ending_hero": PanelBeat(1.66, (.87, .64), "swoosh", "cloth2", (255, 227, 140),
                             before="ending_hero_glove_down"),
    "ending_report": PanelBeat(1.66, (.55, .31), "stamp", "impactWood_heavy_000", (255, 185, 112),
                               7, before="ending_report_raised"),
    "ending_dawn": PanelBeat(1.36, (.62, .53), "sparkle", "cloth2", (255, 224, 161),
                             before="ending_dawn_wave_down"),
}


@dataclass(frozen=True)
class Impact:
    x: float = 0
    y: float = 0
    strength: float = 0


def sample_impact(index, age):
    """랜덤 상태나 실제 시계를 쓰지 않아 정지·다시 보기 결과가 동일하다."""
    return impact_at(IMPACTS[index], age)


def impact_at(impacts, age):
    x = y = strength = 0
    for start, duration, amplitude in impacts:
        q = (age - start) / duration
        if 0 <= q < 1:
            envelope = min(1, q / .08) * (1 - q) ** 1.4
            x += sin(q * pi * 8) * amplitude * envelope
            y += sin(q * pi * 11) * amplitude * .55 * envelope
            strength = max(strength, envelope)
    return Impact(x, y, strength)


def panel_frames(name, beat, age):
    """컷의 전후 그림을 짧게 섞는다. 정지 중에는 같은 프레임을 유지한다."""
    if not (beat.before or beat.after):
        return ((name, 1.0),)
    before, after = beat.before or name, beat.after or name
    progress = min(1.0, max(0.0, (age - beat.time) / .10))
    if progress == 0.0:
        return ((before, 1.0),)
    if progress == 1.0:
        return ((after, 1.0),)
    return ((before, 1.0), (after, progress))


def draw_panel_beat(view, bounds, beat, age, impact):
    import pico2d.pico2d as p
    from game.play_effects import alpha_blend

    elapsed = age - beat.time
    if not 0 <= elapsed < 1.15:
        return
    left, bottom, right, top = bounds
    x = left + (right - left) * beat.focus[0] + impact.x
    y = bottom + (top - bottom) * beat.focus[1] + impact.y
    color = beat.color
    with alpha_blend():
        if beat.effect in ("swoosh", "fizzle"):
            draw_curved_strokes(p, x, y, color, elapsed, fizzle=beat.effect == "fizzle")
        elif beat.effect == "dust":
            q = elapsed / .72
            if q < 1:
                for index in range(7):
                    spread = (index - 3) * (8 + q * 9)
                    p.draw_circle(x + spread, y + sin(q * pi) * (7 + index % 3 * 5),
                                  round(3 + q * 5), *color, round(145 * sin(q * pi)), filled=True)
        else:
            draw_beat_sparks(p, x, y, color, elapsed, streaks=beat.effect in ("impact", "stamp"))
        if beat.effect == "stamp":
            draw_approval_stamp(view, p, x, y + 31, elapsed)


def draw_curved_strokes(p, x, y, color, elapsed, *, fizzle):
    duration = .66 if fizzle else .48
    q = elapsed / duration
    if q >= 1:
        return
    opacity = round(230 * sin(pi * q))
    if fizzle:
        for index in range(5):
            px = x - (21 + 13 * index) * (1 - q)
            py = y + sin(index * 2.4 + q * 11) * (5 + q * 12)
            p.draw_line(px - 4, py + 3, px + 3, py - 1, *color, opacity)
        return
    for index in range(3):
        radius = 23 + index * 11
        start = .1 + q * .95
        previous = (x + cos(start) * radius, y + sin(start) * radius * .56)
        for point in range(1, 8):
            angle = start + point * .16
            current = (x + cos(angle) * radius, y + sin(angle) * radius * .56)
            p.draw_line(*previous, *current, *color, opacity)
            previous = current


def draw_beat_sparks(p, x, y, color, elapsed, *, streaks):
    for index in range(8 if streaks else 6):
        q = (elapsed - index * .045) / (.45 if streaks else .68)
        if not 0 <= q < 1:
            continue
        angle = index * 2.399
        dx, dy = cos(angle), sin(angle)
        distance = (18 + 66 * q) if streaks else (24 + index * 6 + 12 * q)
        px, py = x + dx * distance, y + dy * distance * .7
        glow = sin(pi * q)
        alpha = round(240 * glow)
        if streaks:
            p.draw_line(px, py, px + dx * 17 * (1 - q), py + dy * 12 * (1 - q), *color, alpha)
        else:
            size = 3 + 7 * glow
            p.draw_line(px - size, py, px + size, py, *color, alpha)
            p.draw_line(px, py - size, px, py + size, *color, alpha)
            p.draw_circle(px, py, 2, 255, 250, 220, alpha, filled=True)


def draw_approval_stamp(view, p, x, y, elapsed):
    settle = min(1.0, elapsed / .24)
    scale = 1 + .33 * (1 - settle) ** 2
    alpha = round(255 * min(1.0, elapsed / .08, (1.15 - elapsed) / .28))
    half_w, half_h = 83 * scale, 25 * scale
    bounds = (x - half_w, y - half_h, x + half_w, y + half_h)
    p.draw_rectangle(*bounds, 74, 23, 26, alpha, filled=True)
    p.draw_rectangle(*bounds, 251, 151, 112, alpha)
    p.draw_rectangle(bounds[0] + 4, bounds[1] + 4, bounds[2] - 4, bounds[3] - 4, 251, 151, 112, alpha)
    view.centered(x, y, "퇴근 승인", 26, (255, 230, 176, alpha))


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
