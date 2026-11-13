"""실제 규칙으로 최소 행동 풀이를 찾는 오프라인 A* 검사. 게임 실행에는 사용하지 않는다."""

from collections import deque
from dataclasses import replace
from heapq import heappop, heappush
from itertools import count, permutations, product
from functools import lru_cache
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.levels import load_levels
from game.model import DIRECTIONS, Game
from game.mechanics import trace_magic


def key(state):
    return (state.player, state.carrying, tuple(sorted(state.items.items())),
            frozenset(state.installed), state.active, frozenset(state.soldiers),
            tuple(sorted(state.bench_bones.items())), tuple(sorted(state.mirror_rotations.items())),
            frozenset(state.rubble), frozenset(state.workers))


class LowerBound:
    """문·복구물의 차단을 무시하고 필요한 운반 거리와 상호작용만 센다.

    뼈 투입구 이동 비용은 0으로 완화한다. 새 장치의 통행 제한과 조작 비용도
    완화해 실제 최적 비용보다 큰 값을 반환하지 않는다.
    """

    def __init__(self, level):
        self.level = level
        self.floor = {(x, y) for y in range(level.height) for x in range(level.width)} - level.walls
        self.worker_regions = {}
        self.mirror_regions = []
        self.monotone_mirrors = None
        # 모든 함정이 문 바깥에 있으면 안쪽 부품은 반드시 이 문을 통과한다.
        # 잔해·병사 차단을 없앤 광선의 가능한 방향만 열거해 회전 횟수 하한을 더한다.
        for gate, control in level.gates.items():
            if control not in level.receivers or not level.traps:
                continue
            region, queue = {level.start}, deque([level.start])
            while queue:
                x, y = queue.popleft()
                for dx, dy in DIRECTIONS.values():
                    target = x + dx, y + dy
                    if target in self.floor and target != gate and target not in region:
                        region.add(target)
                        queue.append(target)
            if not level.traps <= region:
                continue
            mirrors = sorted(level.mirrors)
            if len(mirrors) > 6:
                continue  # 큰 지도는 기존의 약한 하한으로 안전하게 돌아간다.
            probe = Game(level).state
            probe.rubble.clear()
            patterns = []
            for rotations in product(range(4), repeat=len(mirrors)):
                probe.mirror_rotations = dict(zip(mirrors, rotations))
                if control in trace_magic(level, probe)[1]:
                    patterns.append(dict(probe.mirror_rotations))
            if patterns:
                self.mirror_regions.append((self.floor - region - {gate}, patterns))
                if len(level.receivers) == 1 and len(patterns) == 1:
                    # 유일한 수신 경로에서 맞춘 거울을 다시 틀면 문을 닫을 뿐이다.
                    # 광선에는 피해나 별도 목표가 없으므로 그 회전은 최단 풀이에 불필요하다.
                    self.monotone_mirrors = patterns[0]
        # 하나의 초소와 인부로 작업하는 방: 모든 함정이 문 바깥에 있다면
        # 안쪽 부품을 꺼내려면 이 인부를 배치한 후 반드시 회수해야 한다.
        if len(level.posts) == 1 and len(level.jobs) == 1:
            for gate, control in level.gates.items():
                if control not in level.jobs:
                    continue
                region, queue = {control}, deque([control])
                while queue:
                    x, y = queue.popleft()
                    for dx, dy in DIRECTIONS.values():
                        target = x + dx, y + dy
                        if target in self.floor and target != gate and target not in region:
                            region.add(target)
                            queue.append(target)
                if level.traps <= region:
                    self.worker_regions[control] = self.floor - region
        self.distances = {}
        self.free_endpoints = {}
        for kind in (None, "part", "bone", "soldier"):
            extra = {}
            if kind == "bone":
                extra = level.chutes
            table = {}
            for start in self.floor:
                distances = {start: 0}
                queue = deque([start])
                while queue:
                    pos = queue.popleft()
                    edges = [((pos[0] + dx, pos[1] + dy), 1) for dx, dy in DIRECTIONS.values()]
                    if pos in extra:
                        edges.append((extra[pos], 0))
                    for target, cost in edges:
                        distance = distances[pos] + cost
                        if target in self.floor and distance < distances.get(target, 10**6):
                            distances[target] = distance
                            (queue.append if cost else queue.appendleft)(target)
                table[start] = distances
            self.distances[kind] = table
            self.free_endpoints[kind] = {p: [q for q, cost in distances.items() if cost == 0]
                                         for p, distances in table.items()}
        self.visit_cells = sorted(level.traps | level.posts | level.benches | level.levers
                                  | level.mirrors | level.jobs | level.initial_items.keys())
        self.visit_bits = {pos: 1 << i for i, pos in enumerate(self.visit_cells)}

        @lru_cache(maxsize=200_000)
        def visit_tail(pos, mask):
            # 운반 제약을 없애고 수리공도 뼈 투입구로 무료 이동한다고 완화한다.
            # 필수 위치를 한 번씩 방문해 출구에 가는 거리이므로 임시 내려놓기도 허용한다.
            if not mask:
                return self.distance('bone', pos, level.exit)
            best = 10**6
            remaining = mask
            while remaining:
                bit = remaining & -remaining
                target = self.visit_cells[bit.bit_length() - 1]
                best = min(best, self.distance('bone', pos, target) + visit_tail(target, mask ^ bit))
                remaining ^= bit
            return best
        self.visit_tail = visit_tail

    def distance(self, kind, start, end):
        return self.distances[kind][start].get(end, 10**6)

    def __call__(self, state):
        level = self.level
        sources = {kind: [p for p, value in state.items.items() if value == kind]
                   for kind in ("part", "bone", "soldier")}
        # Every loose item must be picked up; a carried item already paid that cost.
        sources["soldier"].extend(state.workers)
        actions = len(state.items) + len(state.workers)
        # 여러 수신기의 회전 작업이 겹칠 수 있으므로 합계가 아닌 최댓값이다.
        rotations = [min(sum((target - state.mirror_rotations.get(pos, 0)) % 4
                             for pos, target in pattern.items()) for pattern in patterns)
                     for region, patterns in self.mirror_regions
                     if any(state.items.get(pos) == 'part' for pos in region)]
        actions += max(rotations, default=0)
        must_visit = set(state.items) | state.workers | (level.traps - state.installed) | (level.posts - state.soldiers)
        if len(level.benches) == 1 and (sources['bone'] or state.carrying == 'bone'):
            must_visit |= level.benches
        if len(level.levers) == 1 and level.traps and not state.active:
            must_visit |= level.levers
        for region, patterns in self.mirror_regions:
            if any(state.items.get(pos) == 'part' for pos in region):
                must_visit |= set.intersection(*({pos for pos, target in pattern.items()
                                                  if state.mirror_rotations.get(pos, 0) != target}
                                                 for pattern in patterns))
        if state.carrying:
            sources[state.carrying].append(state.player)
        traps = level.traps - state.installed
        posts = level.posts - state.soldiers
        actions += len(traps) + len(sources["bone"]) + len(posts)
        if level.traps and not state.active:
            actions += 1
        travel = 0
        if traps:
            travel += min(sum(self.distance("part", p, t) for p, t in zip(sources["part"], targets))
                          for targets in permutations(traps))
        for pos in sources["bone"]:
            travel += min(self.distance("bone", pos, bench) for bench in level.benches)
        # Newly assembled soldiers start in hand at a bench. Relax the bench choice.
        soldiers = list(sources["soldier"])
        soldiers += [None] * (len(posts) - len(soldiers))
        required_job = next((job for job, region in self.worker_regions.items()
                             if job not in state.workers and
                             any(state.items.get(pos) == "part" for pos in region)), None)
        if required_job is not None:
            if not posts:
                return 10**6  # 유일한 병사를 이미 고정 배치해 문을 열 수 없다.
            actions += 2  # 작업 배치와 회수; 최종 초소 배치는 원래 하한에 포함.
            must_visit.add(required_job)
        if posts:
            def soldier_distance(p, t):
                starts = (p,) if p is not None else level.benches
                if required_job is not None:
                    return min(self.distance("soldier", b, required_job) for b in starts) + self.distance("soldier", required_job, t)
                return min(self.distance("soldier", b, t) for b in starts)
            travel += min(sum(soldier_distance(p, t)
                              for p, t in zip(soldiers, targets)) for targets in permutations(posts))
        # Walking to the first pickup and from the final repair to the exit is unloaded.
        if not state.carrying and (state.items or state.workers):
            pickups = [q for p, kind in state.items.items() for q in self.free_endpoints[kind][p]]
            # 인부 회수도 줍기다. 가까운 인부보다 먼 부품을 첫 목적지로
            # 강제하면 실제 최단 비용을 초과해 유효한 풀이를 가지치기한다.
            pickups.extend(state.workers)
            travel += min(self.distance(None, state.player, q) for q in pickups)
        last = set(traps) | set(posts)
        if level.traps and not state.active:
            last |= level.levers
        if last:
            travel += min(self.distance(None, p, level.exit) for p in last)
        elif not state.items and not state.carrying:
            travel += self.distance(None, state.player, level.exit)
        # 위치가 너무 많으면 지수 크기 방문표를 만들지 않고 기존 하한을 사용한다.
        if len(self.visit_cells) <= 14:
            mask = sum(self.visit_bits.get(pos, 0) for pos in must_visit)
            travel = max(travel, self.visit_tail(state.player, mask))
        return actions + travel


def solve(level, max_states=500_000, upper_bound=None, forbidden=None):
    """유효 입력과 최단성을 보존하는 거울 가지치기로 탐색한다. 상한 도달은 미검증이다."""
    game = Game(replace(level, action_limit=None))
    lower_bound = LowerBound(level)
    initial = game.state
    start = key(initial)
    serial = count()
    queue = [(lower_bound(initial), 0, next(serial), initial)]
    best = {start: 0}
    parents = {}
    expanded = 0
    started = time.monotonic()
    while queue:
        estimate, negative_cost, _, state = heappop(queue)
        cost = -negative_cost
        token = key(state)
        if best.get(token) != cost:
            continue
        if upper_bound is not None and estimate > upper_bound:
            continue
        if state.cleared:
            actions = []
            while token != start:
                token, action = parents[token]
                actions.append(action)
            return {"actions": list(reversed(actions)), "minimum": cost,
                    "expanded": expanded, "seconds": round(time.monotonic() - started, 2)}
        expanded += 1
        if expanded > max_states:
            raise RuntimeError(f"{level.id}: 탐색 상한 {max_states}개 상태 도달. 최단성 미검증.")
        for action in (*DIRECTIONS, "interact", "drop"):
            game.state = state
            game.history = []
            if (action == 'interact' and state.player in level.mirrors
                    and lower_bound.monotone_mirrors is not None
                    and (state.mirror_rotations.get(state.player, 0) == lower_bound.monotone_mirrors[state.player])
                    and game._interaction(state)[0] == 'rotate'):
                continue
            if forbidden and forbidden(game, action):
                continue
            if not game.act(action):
                continue
            candidate = game.state
            next_token = key(candidate)
            next_cost = cost + 1
            if next_cost >= best.get(next_token, 10**9):
                continue
            estimate = next_cost + lower_bound(candidate)
            if upper_bound is not None and estimate > upper_bound:
                continue
            best[next_token] = next_cost
            parents[next_token] = (token, action)
            heappush(queue, (estimate, -next_cost, next(serial), candidate))
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, nargs="+")
    parser.add_argument("--max-states", type=int, default=500_000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="최단 풀이와 최소+2회 제한 검증")
    parser.add_argument("--check-mechanics", action="store_true", help="4~8번 핵심 장치를 각각 생략하면 제한 내 완료 불가인지 검사")
    args = parser.parse_args()
    from tests.solutions import MINIMUM_ACTIONS, SOLUTIONS
    results = {}
    for index, level in enumerate(load_levels(), 1):
        if args.stage and index not in args.stage:
            continue
        if args.check and level.id not in MINIMUM_ACTIONS:
            raise ValueError("최단 행동 기준이 없습니다. 먼저 제한 없이 탐색해 기준 풀이를 등록하세요.")
        route = SOLUTIONS.get(level.id, [])
        check = Game(replace(level, action_limit=None))
        valid = all(check.act(a) for a in route) and check.state.cleared
        result = solve(level, args.max_states, len(route) if valid else None)
        if args.check:
            expected_limit = None if index == 1 else MINIMUM_ACTIONS[level.id] + 2
            if (not valid or result is None or result["minimum"] != MINIMUM_ACTIONS[level.id]
                    or len(route) != result["minimum"] or level.action_limit != expected_limit):
                raise ValueError(f"{level.id}: 기준 풀이·최소 행동·제한 규칙 불일치 "
                                 f"(재생={valid}, 탐색={None if result is None else result['minimum']}, "
                                 f"기준={MINIMUM_ACTIONS[level.id]}, 제한={level.action_limit})")
        if result is None:
            raise ValueError(f"{level.id}: 완료 가능한 풀이가 없습니다.")
        required = {4: ("rubble", "plate"), 5: ("mirror", "chute"), 6: ("mirror",),
                    7: ("helper",), 8: ("rubble", "mirror", "helper", "chute")}
        if args.check_mechanics and index in required:
            for mechanic in required[index]:
                def forbidden(game, action):
                    if action in DIRECTIONS:
                        dx, dy = DIRECTIONS[action]
                        target = game.state.player[0] + dx, game.state.player[1] + dy
                        return ((mechanic == "rubble" and target in game.state.rubble)
                                or (mechanic == "plate" and (target in level.plates or
                                    (target in game.state.rubble and (target[0] + dx, target[1] + dy) in level.plates))))
                    operation = (game._drop_interaction(game.state) if action == "drop" else
                                 game._interaction(game.state))[0]
                    return ((mechanic == "plate" and operation == "drop" and game.state.player in level.plates)
                            or (mechanic == "chute" and operation == "send_bone")
                            or (mechanic == "mirror" and operation == "rotate")
                            or (mechanic == "helper" and operation == "assign"))

                bypass = solve(level, args.max_states, level.action_limit, forbidden)
                if bypass is not None:
                    raise ValueError(f"{level.id}: {mechanic} 없이 {bypass['minimum']}회에 완료 가능")
                print(f"{level.id}: {mechanic} 생략 시 제한 내 완료 불가", flush=True)
            result["core_mechanic_required_within_limit"] = True
            result["required_mechanics"] = list(required[index])
        result["action_limit"] = level.action_limit
        result["size"] = [level.width, level.height]
        result["floor_cells"] = level.width * level.height - len(level.walls)
        results[level.id] = result
        print(json.dumps({"stage": level.id, **{k: v for k, v in result.items() if k != "actions"}}), flush=True)
    if args.output:
        root = Path(__file__).resolve().parents[1]
        fingerprints = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                        for name in ("data/stages.json", "game/levels.py", "game/model.py",
                                     "game/mechanics.py", "tools/solve_levels.py", "tests/solutions.py")}
        report = {"sha256": fingerprints, "stages": results}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
