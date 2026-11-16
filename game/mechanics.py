"""새 장치의 파생 상태. 광선은 저장하지 않고 현재 배치에서 계산한다."""

from game.levels import DIRECTIONS
from game.magic import mirror_output


def mirror_axis(rotation):
    """거울판은 지도 평면에서 방출 방향과 수직으로 표시한다."""
    nx, ny = mirror_output(rotation)
    return ny, -nx


def mirror_cells(level, state):
    return (level.mirrors - level.movable_mirrors) | state.movable_mirrors


def beam_obstacles(level, state, rubble=None):
    blocks = state.rubble if rubble is None else rubble
    return level.walls | state.soldiers | level.sources.keys() | blocks


def trace_magic(level, state):
    """마력 광선의 선분과 작동 수신기. 순환 경로도 유한하게 끝낸다.

    광선은 머리 위로 지나가며 벽·잔해·최종 배치 병사·광원에서 멈춘다.
    문과 운반물은 막지 않으므로 문 전원 판정에 순환 의존성이 없다.
    """
    segments, powered = [], set()
    obstacles = beam_obstacles(level, state)
    mirrors = mirror_cells(level, state)
    for start, direction in level.sources.items():
        pos, delta = start, DIRECTIONS[direction]
        seen = set()
        while (pos, delta) not in seen:
            seen.add((pos, delta))
            target = pos[0] + delta[0], pos[1] + delta[1]
            if not (0 <= target[0] < level.width and 0 <= target[1] < level.height):
                break
            segments.append((pos, target))
            if target in obstacles:
                break
            if target in level.receivers:
                powered.add(target)
                break
            if target in mirrors:
                delta = mirror_output(state.mirror_rotations.get(target, 0))
            pos = target
    return segments, powered


def fixed_devices(level, state):
    return (level.traps | level.posts | level.benches | level.levers | level.chutes.keys()
            | mirror_cells(level, state) | level.sources.keys() | level.receivers | level.jobs | {level.exit})
