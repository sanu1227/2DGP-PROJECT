"""정면 3/4 격자에 맞는 낮은 돌벽. 기존 석재 질감과 코드로만 그린다."""


def draw_wall(art, pos, sx, sy, width, height, tint):
    """벽칸 전체를 채우고 윗면을 16~22px 올린다. 충돌·원본 아트는 그대로다."""
    import pico2d.pico2d as p

    x, y = pos
    pattern = x * 37 + y * 61 + x * y * 13
    rise = 16 + pattern % 7
    left, right = round(sx - width / 2), round(sx + width / 2)
    baseline = round(sy - height / 2)
    ledge = baseline + rise
    middle = baseline + rise // 2

    def shade(factors):
        return tuple(max(0, min(255, round(channel * factor)))
                     for channel, factor in zip(tint, factors))

    # 앞면에도 원본 석재의 요철을 써 단색 띠처럼 보이지 않게 한다.
    art.ground("floor_scuffed", sx, baseline + rise / 2, width, rise,
               shade((0.57, 0.63, 0.68)))
    cap = "floor_plain" if pattern % 5 == 0 else "floor_cracked"
    art.ground(cap, sx, sy + rise, width, height,
               shade((0.72, 0.78, 0.84)))

    mortar = (23, 29, 32)
    edge = shade((0.58, 0.64, 0.68))
    p.draw_line(left, baseline, right, baseline, *mortar)
    p.draw_line(left, baseline + 1, right, baseline + 1, *mortar)
    p.draw_line(left, middle, right, middle, *mortar)
    p.draw_line(left, ledge - 1, right, ledge - 1, *mortar)
    # 닳아 끊어진 밝은 모서리와 바로 아래 그림자로 윗면의 높이를 읽게 한다.
    p.draw_line(left + 3, ledge, round(left + width * 0.36), ledge, *edge)
    p.draw_line(round(left + width * 0.53), ledge, right - 4, ledge, *edge)
    # 위아래 줄의 세로 이음매를 엇갈리게 두어 긴 벽돌 벽으로 읽히게 한다.
    for fraction in (0.25, 0.68):
        seam = round(left + width * fraction)
        p.draw_line(seam, baseline + 1, seam, middle, *mortar)
        p.draw_line(seam + 1, baseline + 2, seam + 1, middle - 1,
                    *shade((0.34, 0.40, 0.43)))
    seam = round(left + width * 0.47)
    p.draw_line(seam, middle + 1, seam, ledge - 1, *mortar)

    # 짧은 파손선과 이끼 자국도 좌표로 고정해 움직이거나 되돌려도 유지한다.
    crack_x = round(left + width * (0.57 + (pattern % 4) * 0.06))
    bend_x = crack_x + (3 if pattern % 2 else -3)
    p.draw_line(crack_x, ledge - 1, bend_x, middle + 1, *mortar)
    p.draw_line(bend_x, middle + 1, crack_x - 2, baseline + 2, *mortar)
    if pattern % 3 == 0:
        moss_x = round(left + width * 0.12)
        p.draw_line(moss_x, baseline + 2, moss_x + round(width * 0.18),
                    baseline + 2, *shade((0.29, 0.37, 0.28)))
