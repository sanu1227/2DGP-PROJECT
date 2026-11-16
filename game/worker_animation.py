"""동작별 수리공 자세와 손에 닿는 프레임을 계산한다."""

from dataclasses import dataclass, replace

from game.levels import DIRECTIONS


@dataclass(frozen=True)
class Gesture:
    frames: tuple
    contact: float


# 각 자세는 (진행률, 무릎 굽힘, 손 뻗기) 순이다.
GESTURES = {
    "pickup": Gesture(((0, .04, 0), (.42, 1, 1), (.63, .68, .6), (1, 0, 0)), .42),
    "drop": Gesture(((0, 0, 0), (.57, 1, 1), (.72, .85, .6), (1, 0, 0)), .57),
    "install": Gesture(((0, 0, 0), (.35, .70, .68), (.66, .91, 1), (1, 0, 0)), .66),
    "lever": Gesture(((0, .06, 0), (.33, .35, 1), (.60, .15, .72), (1, 0, 0)), .60),
    "deliver": Gesture(((0, 0, 0), (.29, .13, .62), (.54, .46, 1), (1, 0, 0)), .54),
    "assemble": Gesture(((0, 0, 0), (.31, .35, .70), (.56, .61, 1), (1, 0, 0)), .56),
    "deploy": Gesture(((0, 0, 0), (.25, .38, .54), (.57, .88, 1), (1, 0, 0)), .57),
}

# 투명 여백을 포함한 아틀라스의 운반 자세에서 양 손 사이의 중심.
TOPDOWN_HAND = {"down": (0, .69), "up": (0, .44), "left": (-.24, .55), "right": (.24, .55)}
ISO_HAND = {"up": (.24, .57), "right": (.22, .59), "down": (-.22, .60), "left": (-.24, .58)}


def smooth(value):
    value = max(0, min(1, value))
    return value * value * (3 - 2 * value)


@dataclass(frozen=True)
class WorkerAction:
    kind: str
    origin: tuple
    target: tuple
    before_item: str | None
    after_item: str | None
    began: float
    seconds: float

    def progress(self, now):
        return max(0, min(1, (now - self.began) / self.seconds))

    @property
    def contact(self):
        return GESTURES[self.kind].contact

    @property
    def direction(self):
        dx = self.target[0] - self.origin[0]
        dy = self.target[1] - self.origin[1]
        return next((name for name, delta in DIRECTIONS.items() if delta == (dx, dy)), None)

    def reaches(self, now):
        phase = self.progress(now)
        frames = GESTURES[self.kind].frames
        for (start, bend, reach), (end, next_bend, next_reach) in zip(frames, frames[1:]):
            if phase <= end:
                mix = smooth((phase - start) / (end - start))
                return bend + (next_bend - bend) * mix, reach + (next_reach - reach) * mix
        return 0, 0


@dataclass(frozen=True)
class WorkerPose:
    upper: str
    boots: str
    height: float
    shift: tuple
    grip: tuple
    item: str | None
    item_floor_scale: float

    def layers(self, top_down):
        dx, dy = self.shift
        if self.upper == self.boots and self.shift == (0, 0):
            return ((self.upper, 0, 0, None),)
        seam, bottom = (212, 248) if top_down else (191, 256)
        return ((self.boots, 0, 0, (seam - 8, bottom)), (self.upper, dx, dy, (0, seam)))

    def item_position(self, feet, floor):
        hand_x, hand_y = feet[0] + self.grip[0], feet[1] + self.grip[1]
        ratio = self.item_floor_scale
        return hand_x + (floor[0] - hand_x) * ratio, hand_y + (floor[1] - hand_y) * ratio

    def reach_toward(self, feet, point, weight, body_size):
        limit = .14 * body_size
        dx = max(-limit, min(limit, point[0] - feet[0] - self.grip[0])) * weight
        dy = max(-limit, min(limit, point[1] - feet[1] - self.grip[1])) * weight
        return replace(self, shift=(self.shift[0] + dx, self.shift[1] + dy),
                       grip=(self.grip[0] + dx, self.grip[1] + dy))


def sample_pose(direction, body_size, rest_height, walk, carrying, action, now, *, top_down, push=False):
    """상체를 움직여도 발은 밟고 있던 자리에 둔다."""
    hands = TOPDOWN_HAND if top_down else ISO_HAND
    hand_x, hand_row = hands[direction]
    forward_x, forward_y = DIRECTIONS[direction]
    if not top_down:
        forward_x -= forward_y
    upper = "carry" if carrying else walk
    boots = walk if walk != "idle" else upper
    item, floor_scale = carrying, 0
    bend = reach = 0
    if action:
        bend, reach = action.reaches(now)
        phase, contact = action.progress(now), action.contact
        upper, boots = "carry", "idle"
        if action.kind == "pickup":
            floor_scale = 1 - smooth((phase - contact) / (1 - contact))
        elif action.kind in ("drop", "install", "deliver", "deploy"):
            floor_scale = smooth(phase / contact)
            item = action.before_item if phase < contact else None
        elif action.kind == "assemble":
            if phase < contact:
                item = action.before_item
                floor_scale = smooth(phase / contact)
            else:
                item = action.after_item
                floor_scale = 1 - smooth((phase - contact) / (1 - contact))
    elif push:
        upper = "carry"
        bend, reach = .54, .76
    elif carrying and walk != "idle":
        bend = .13 if walk == "walk_a" else .02

    height = rest_height * (1 - .25 * bend)
    shift = (body_size * .14 * reach * forward_x, -body_size * .09 * bend)
    # 발 기준 높이로 변환해서 스프라이트 압축과 손에 든 물건이 함께 움직이게 한다.
    anchor = 1 if top_down else 220 / 256
    grip = (hand_x * body_size + shift[0], (anchor - hand_row) * body_size * height + shift[1])
    return WorkerPose(upper, boots, height, shift, grip, item, floor_scale)
