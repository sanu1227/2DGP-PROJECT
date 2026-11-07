"""기존 장치 상면을 정면 격자에 맞추는 표시 전용 부품."""


BELT_SURFACE = ((164, 79), (206, 103), (84, 179), (40, 153))
PLATE_SURFACE = ((128, 63), (203, 104), (128, 145), (52, 104))
QUARTER_TURNS = {"up": 0, "right": 1, "down": 2, "left": 3}


def _rectangle(p, left, bottom, right, top, color):
    p.draw_rectangle(round(left), round(bottom), round(right), round(top),
                     *color, filled=True)


def _platform(p, sx, sy, width, height, rise, frame, face):
    """지면 기준 앞면과 얇은 금속 테두리를 그리고 상면의 네 꼭짓점을 반환한다."""
    left, right = sx - width / 2, sx + width / 2
    baseline = sy - height / 2
    bottom, top = baseline + rise, sy + height / 2 + rise
    _rectangle(p, left, baseline, right, bottom, face)
    _rectangle(p, left, bottom, right, top, frame)
    p.draw_line(round(left), round(baseline), round(right), round(baseline), 25, 30, 29)
    inset = 2
    corners = ((left + inset, top - inset), (right - inset, top - inset),
               (right - inset, bottom + inset), (left + inset, bottom + inset))
    return corners, (left, bottom, right, top)


def _bolts(p, bounds):
    left, bottom, right, top = bounds
    for x, y in ((left + 3, top - 3), (right - 3, top - 3),
                 (right - 3, bottom + 3), (left + 3, bottom + 3)):
        _rectangle(p, x - 2, y - 2, x + 2, y + 2, (67, 57, 40))
        _rectangle(p, x - 1, y, x + 1, y + 1, (204, 177, 111))


def draw_belt(art, direction, sx, sy, width, height):
    """화살표와 실제 운반 방향을 화면의 상하좌우에 일치시킨다."""
    import pico2d.pico2d as p

    turns = QUARTER_TURNS[direction]
    horizontal = direction in ("left", "right")
    belt_width = width * (0.90 if horizontal else 0.44)
    belt_height = height * (0.58 if horizontal else 0.90)
    corners, bounds = _platform(p, sx, sy, belt_width, belt_height, 5,
                                (132, 105, 61), (63, 54, 40))
    # 원본 NE 화살표의 먼 쪽을 위로 맞춘 뒤 꼭짓점 대응만 90도씩 회전한다.
    target = corners[turns:] + corners[:turns]
    art.quad("conveyor_ne", BELT_SURFACE, target)
    left, bottom, right, top = bounds
    p.draw_line(round(left + 2), round(top), round(right - 2), round(top),
                190, 157, 91)
    p.draw_line(round(left), round(bottom - 1), round(right), round(bottom - 1),
                40, 35, 28)
    _bolts(p, bounds)


def draw_plate(art, pressed, sx, sy, width, height):
    """같은 금속 상면의 높이와 전면 표시등으로 발판 눌림을 구분한다."""
    import pico2d.pico2d as p

    rise = 3 if pressed else 9
    corners, bounds = _platform(p, sx, sy, width * 0.65, height * 0.65,
                                rise, (108, 99, 76), (65, 69, 64))
    tint = (211, 235, 220) if pressed else (255, 255, 255)
    art.quad("plate_up", PLATE_SURFACE, corners, tint)
    left, bottom, right, top = bounds
    p.draw_line(round(left + 2), round(top), round(right - 2), round(top),
                178, 160, 112)
    indicator = (77, 213, 184) if pressed else (65, 77, 70)
    for x in (left + 5, right - 11):
        _rectangle(p, x, bottom - 2, x + 6, bottom, indicator)
