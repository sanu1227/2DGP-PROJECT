"""실제 규칙으로 최소 행동 풀이를 찾는 오프라인 A* 검사. 게임 실행에는 사용하지 않는다."""

from collections import deque
from dataclasses import replace
from heapq import heappop, heappush
from itertools import count, permutations
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.levels import load_levels
from game.model import DIRECTIONS, Game


def key(state):
    return (state.player, state.carrying, tuple(sorted(state.items.items())),
            frozenset(state.installed), state.active, frozenset(state.soldiers),
            tuple(sorted(state.bench_bones.items())))


class LowerBound:
    """문·복구물의 차단을 무시하고 필요한 운반 거리와 상호작용만 센다.

    물건별 벨트/투입구 이동 비용은 0으로 완화한다. 따라서 동시 자동 운반을
    중복 과금하지 않으며 실제 최적 비용보다 큰 값을 반환하지 않는다.
    """

    def __init__(self, level):
        self.level = level
        self.floor = {(x, y) for y in range(level.height) for x in range(level.width)} - level.walls
        self.distances = {}
        self.free_endpoints = {}
        for kind in (None, "part", "bone", "soldier"):
            extra = {}
            if kind in {"part", "soldier"}:
                extra = {p: (p[0] + DIRECTIONS[d][0], p[1] + DIRECTIONS[d][1])
                         for p, d in level.belts.items()}
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

    def distance(self, kind, start, end):
        return self.distances[kind][start].get(end, 10**6)

    def __call__(self, state):
        level = self.level
        sources = {kind: [p for p, value in state.items.items() if value == kind]
                   for kind in ("part", "bone", "soldier")}
        # Every loose item must be picked up; a carried item already paid that cost.
        actions = len(state.items)
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
        if posts:
            travel += min(sum(self.distance("soldier", p, t) if p is not None else
                              min(self.distance("soldier", b, t) for b in level.benches)
                              for p, t in zip(soldiers, targets)) for targets in permutations(posts))
        # Walking to the first pickup and from the final repair to the exit is unloaded.
        if not state.carrying and state.items:
            travel += min(self.distance(None, state.player, q)
                          for p, kind in state.items.items() for q in self.free_endpoints[kind][p])
        last = set(traps) | set(posts)
        if level.traps and not state.active:
            last |= level.levers
        if last:
            travel += min(self.distance(None, p, level.exit) for p in last)
        elif not state.items and not state.carrying:
            travel += self.distance(None, state.player, level.exit)
        return actions + travel


def solve(level, max_states=500_000, upper_bound=None, forbidden=None):
    """모든 유효 입력을 탐색한다. 탐색 상한에 도달하면 미검증 예외를 반환한다."""
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
    args = parser.parse_args()
    from tests.test_game import SOLUTIONS
    results = {}
    for index, level in enumerate(load_levels(), 1):
        if args.stage and index not in args.stage:
            continue
        route = SOLUTIONS.get(level.id, [])
        check = Game(replace(level, action_limit=None))
        valid = all(check.act(a) for a in route) and check.state.cleared
        result = solve(level, args.max_states, len(route) if valid else None)
        results[level.id] = result
        print(json.dumps({"stage": level.id, **(result or {"solvable": False})}), flush=True)
    if args.output:
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
