"""기존 아트에 고정된 파손 흔적을 더한다. 지형과 게임 상태는 바꾸지 않는다."""

from contextlib import contextmanager
from ctypes import byref, c_ubyte
from math import hypot


def draw_rubble_track(board, track):
    """두 광로 사이에서 차광 블록이 움직일 레일과 양 끝의 멈춤쇠."""
    if not track:
        return
    import pico2d.pico2d as p

    (x1, y1), (x2, y2) = map(board.screen, sorted(track))
    dx, dy = x2 - x1, y2 - y1
    length = hypot(dx, dy)
    offset = board.half_width * .24
    ox, oy = -dy / length * offset, dx / length * offset
    x1, y1, x2, y2 = x1 - dx * .37, y1 - dy * .37, x2 + dx * .37, y2 + dy * .37
    for x, y in ((x1, y1), (x2, y2)):
        p.draw_line(x - ox * 1.25, y - oy * 1.25, x + ox * 1.25, y + oy * 1.25, 179, 140, 80)
    for sign in (-1, 1):
        ax, ay = ox * sign, oy * sign
        for lift, color in ((-2, (27, 25, 24)), (-1, (78, 66, 53)), (0, (156, 133, 100))):
            p.draw_line(x1 + ax, y1 + ay + lift, x2 + ax, y2 + ay + lift, *color)
        for x, y in ((x1, y1), (x2, y2)):
            p.draw_circle(x + ax, y + ay, 2, 189, 157, 105, filled=True)


def _pattern(pos):
    """프로세스나 프레임과 무관한 좌표별 무늬 번호."""
    x, y = pos
    value = (x * 0x9E3779B1 ^ y * 0x85EBCA77 ^ 0xC2B2AE3D) & 0xFFFFFFFF
    value ^= value >> 16
    return (value * 0x27D4EB2D) & 0xFFFFFFFF


def floor_style(pos, near_trap=False):
    """일반 바닥용 스프라이트와 RGB 변조값. 장치 타일에는 적용하지 않는다."""
    pattern = _pattern(pos)
    variation = (pattern >> 8) % 15
    if near_trap:
        sprite = "floor_cracked" if pattern % 4 else "floor_scuffed"
        return sprite, (163 + variation, 157 + variation, 147 + variation)
    choice = pattern % 20
    if choice < 10:
        return "floor_cracked", (180 + variation, 179 + variation, 169 + variation)
    if choice < 17:
        return "floor_scuffed", (191 + variation, 179 + variation, 162 + variation)
    if choice < 19:
        return "floor_moss", (180 + variation, 190 + variation, 172 + variation)
    return "floor_plain", (202 + variation, 197 + variation, 185 + variation)


def wall_style(pos):
    """벽칸 약 30%를 낮은 잔해 타일로 표현한다. 충돌은 원래 벽 그대로다."""
    pattern = _pattern(pos)
    variation = (pattern >> 12) % 24
    if pattern % 10 < 3:
        return "rubble", (178 + variation, 166 + variation, 146 + variation)
    return "wall_low", (176 + variation, 177 + variation, 166 + variation)


@contextmanager
def texture_tint(texture, tint):
    """공유 아틀라스의 기존 RGB를 보관하고, 그리기가 실패해도 복원한다."""
    if tint is None:
        yield
        return
    import pico2d.pico2d as p

    previous = (c_ubyte(), c_ubyte(), c_ubyte())
    if p.SDL_GetTextureColorMod(texture, *(byref(channel) for channel in previous)) != 0:
        raise RuntimeError("배경 아틀라스의 기존 색상을 읽지 못했습니다.")
    try:
        if p.SDL_SetTextureColorMod(texture, *tint) != 0:
            raise RuntimeError("배경 아틀라스의 색상을 적용하지 못했습니다.")
        yield
    finally:
        p.SDL_SetTextureColorMod(texture, *(channel.value for channel in previous))


def draw_tinted(art, sprite, sx, sy, scale, tint):
    entry = art.manifest["sprites"][sprite]
    texture = art.atlases[entry["atlas"]].texture
    with texture_tint(texture, tint):
        art.draw(sprite, sx, sy, scale)


def draw_scars(pos, sx, sy, scale, near_trap=False):
    """일반 바닥 윗면 안에 균열·그을음을 그린다. 칸당 최대 10개 선이다."""
    import pico2d.pico2d as p

    pattern = _pattern(pos)
    if not near_trap and pattern % 3 == 0:
        return
    flip_x = -1 if pattern & 1 else 1
    flip_y = -1 if pattern & 2 else 1

    def stroke(first, second, color):
        p.draw_line(
            round(sx + first[0] * flip_x * scale),
            round(sy + first[1] * flip_y * scale),
            round(sx + second[0] * flip_x * scale),
            round(sy + second[1] * flip_y * scale),
            *color,
        )

    crack = ((-74, -4), (-29, 9), (-7, -4), (27, 5), (58, -10))
    dark = (35, 34, 30) if near_trap else (43, 43, 38)
    for first, second in zip(crack, crack[1:]):
        stroke(first, second, dark)
    stroke(crack[2], (11, -27), dark)
    stroke((-29, 11), (-7, -2), (104, 93, 73))
    if near_trap:
        stroke(crack[3], (17, 25), dark)
        for offset in (-3, 0, 3):
            stroke((-19, -16 + offset), (24, -7 + offset), (49, 43, 34))
