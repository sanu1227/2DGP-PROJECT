"""작은 퍼즐의 전체 상태 그래프로 탐색기의 최단성과 하한을 독립 검사한다."""

from collections import defaultdict, deque
import unittest

from game.model import DIRECTIONS, Game
from tests.test_devices import load_stage
from tools.solve_levels import LowerBound, key, solve


class SolverTests(unittest.TestCase):
    def test_astar_and_lower_bound_match_exhaustive_graph_with_devices(self):
        rooms = [
            {"map": ["########", "#@PTLE##", "#.....##"]},
            {"map": ["########", "#@P...E#", "#...FTL#", "#...G..#"],
             "plate_links": [{"id": "P1", "plate": [4, 2], "gate": [4, 3]}]},
            {"map": ["########", "#@BC####", "#..GFAE#", "####BS##"],
             "plate_links": [{"id": "P1", "plate": [4, 2], "gate": [3, 2]}],
             "chute_links": [{"id": "C1", "inlet": [3, 1], "outlet": [4, 2]}]},
            {"map": ["########", "#@BBAJ##", "#ELTSGP#"],
             "worker_links": [{"id": "J1", "station": [5, 1], "gate": [5, 2]}]},
        ]
        for index, room in enumerate(rooms):
            room.update(id=f"solver_{index}", title="탐색 검사", hint="복구 후 복귀")
            room["map"] += ["########"] * (8 - len(room["map"]))
            level = load_stage(room)
            with self.subTest(room=level.id):
                game = Game(level)
                first = key(game.state)
                states = {first: game.state}
                reverse = defaultdict(set)
                queue = deque([first])
                goals = []
                while queue:
                    source = queue.popleft()
                    state = states[source]
                    if state.cleared:
                        goals.append(source)
                        continue
                    for action in (*DIRECTIONS, "interact", "drop"):
                        game.state, game.history = state, []
                        if game.act(action):
                            target = key(game.state)
                            reverse[target].add(source)
                            if target not in states:
                                states[target] = game.state
                                queue.append(target)
                self.assertTrue(goals)
                costs = dict.fromkeys(goals, 0)
                queue = deque(goals)
                while queue:
                    target = queue.popleft()
                    for source in reverse[target]:
                        if source not in costs:
                            costs[source] = costs[target] + 1
                            queue.append(source)
                bound = LowerBound(level)
                for token, cost in costs.items():
                    self.assertLessEqual(bound(states[token]), cost, token)
                result = solve(level)
                self.assertEqual(result["minimum"], costs[first])
                replay = Game(level)
                for action in result["actions"]:
                    self.assertTrue(replay.act(action))
                self.assertTrue(replay.state.cleared)
                self.assertIsNone(solve(level, upper_bound=result["minimum"] - 1))
                with self.assertRaisesRegex(RuntimeError, "최단성 미검증"):
                    solve(level, max_states=0)


if __name__ == "__main__":
    unittest.main()
