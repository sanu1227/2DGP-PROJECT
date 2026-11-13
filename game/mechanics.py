"""새 장치의 파생 상태. 광선은 저장하지 않고 현재 배치에서 계산한다."""

from game.levels import DIRECTIONS


def trace_magic(level, state):
    """반사 광선의 선분과 작동 수신기. 순환 경로도 유한하게 끝낸다.

    광선은 머리 위로 지나가며 벽·잔해·최종 배치 병사만 막는다.
    문과 운반물은 막지 않으므로 문 전원 판정에 순환 의존성이 없다.
    """
    segments, powered = [], set()
    for start, direction in level.sources.items():
        pos, delta = start, DIRECTIONS[direction]
        seen = set()
        while (pos, delta) not in seen:
            seen.add((pos, delta))
            target = pos[0] + delta[0], pos[1] + delta[1]
            if not (0 <= target[0] < level.width and 0 <= target[1] < level.height):
                break
            segments.append((pos, target))
            if target in level.walls or target in state.rubble or target in state.soldiers:
                break
            if target in level.receivers:
                powered.add(target)
                break
            if target in level.mirrors:
                dx, dy = delta
                delta = (dy, dx) if target in state.turned_mirrors else (-dy, -dx)
            pos = target
    return segments, powered


def fixed_devices(level):
    return (level.traps | level.posts | level.benches | level.levers | level.chutes.keys()
            | level.mirrors | level.sources.keys() | level.receivers | level.jobs | {level.exit})
