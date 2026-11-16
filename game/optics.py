"""연속 각도의 표시용 광선. 게임과 같은 거울 방출 방향을 사용한다."""

from math import sqrt

from game.levels import DIRECTIONS
from game.magic import mirror_output

MAGIC_BEAM_HEIGHT = 70
MIRROR_HALF_SPAN = .36
MIRROR_HALF_DEPTH = .027
SOURCE_REACH = {'right': 74 / 112, 'down': 74 / 112, 'up': 58 / 112, 'left': 58 / 112}


def source_origin(pos, direction):
    delta = DIRECTIONS[direction]
    return tuple(pos[i] + delta[i] * SOURCE_REACH[direction] for i in (0, 1))


def box_hit(origin, direction, left, bottom, right, top):
    if left <= origin[0] <= right and bottom <= origin[1] <= top:
        return 0.0
    near, far = -float('inf'), float('inf')
    for coordinate, component, low, high in zip(origin, direction, (left, bottom), (right, top)):
        if abs(component) < 1e-10:
            if not low <= coordinate <= high:
                return None
        else:
            a, b = (low - coordinate) / component, (high - coordinate) / component
            near, far = max(near, min(a, b)), min(far, max(a, b))
    return near if far >= max(near, 1e-6) and near > 1e-6 else None


def device_hit(origin, direction, center):
    offset = origin[0] - center[0], origin[1] - center[1]
    b = sum(a * d for a, d in zip(offset, direction))
    discriminant = b * b - (offset[0] ** 2 + offset[1] ** 2 - .22 ** 2)
    if discriminant < 0:
        return None
    distance = -b - sqrt(discriminant)
    return distance if distance > 1e-6 else None


def trace_display_magic(level, state, rotations):
    """발사구에서 광선을 쏴 가장 가까운 장치로 보낸다. 최대 64번 방향을 바꾼다."""
    segments, powered = [], set()
    obstacles = level.walls | state.rubble | state.soldiers | level.sources.keys()
    for source, name in level.sources.items():
        origin, direction = source_origin(source, name), DIRECTIONS[name]
        if not (-.5 <= origin[0] <= level.width - .5 and -.5 <= origin[1] <= level.height - .5):
            continue
        seen = set()
        for _ in range(64):
            token = tuple(round(value, 7) for value in (*origin, *direction))
            if token in seen:
                break
            seen.add(token)
            # 지도 외곽까지의 양의 거리. 바깥에서 시작하는 광원은 없다.
            candidates = [((bound - origin[i]) / direction[i], 'stop', None)
                          for i, bounds in enumerate(((-.5, level.width - .5), (-.5, level.height - .5)))
                          if abs(direction[i]) > 1e-10 for bound in bounds
                          if (bound - origin[i]) / direction[i] > 1e-6]
            for x, y in obstacles:
                distance = box_hit(origin, direction, x - .5, y - .5, x + .5, y + .5)
                if distance is not None:
                    candidates.append((distance, 'stop', None))
            for pos in level.receivers:
                distance = device_hit(origin, direction, pos)
                if distance is not None:
                    candidates.append((distance, 'receiver', pos))
            for pos in level.mirrors - obstacles:
                distance = device_hit(origin, direction, pos)
                if distance is not None:
                    candidates.append((distance, 'mirror', pos))
            distance, kind, target = min(candidates, key=lambda item: item[0])
            end = target if kind == 'mirror' else tuple(origin[i] + direction[i] * distance for i in (0, 1))
            segments.append((origin, end))
            if kind == 'receiver':
                powered.add(target)
            if kind != 'mirror':
                break
            direction = mirror_output(rotations.get(target, state.mirror_rotations.get(target, 0)))
            origin = end
    return segments, powered
