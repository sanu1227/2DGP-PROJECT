"""배치의 통로 차단 목적과 엄격한 행동 제한 경계를 검사한다."""

from collections import deque
from dataclasses import replace
import unittest

from game.levels import load_levels
from game.model import DIRECTIONS, Game
from tests.solutions import MINIMUM_ACTIONS, SOLUTIONS


class BalanceTests(unittest.TestCase):
    def test_reference_routes_finish_on_exact_budget_and_have_two_spare_actions(self):
        for index, level in enumerate(load_levels()):
            minimum = MINIMUM_ACTIONS[level.id]
            with self.subTest(stage=level.id):
                self.assertEqual(level.action_limit, None if index == 0 else minimum + 2)
                self.assertEqual(len(SOLUTIONS[level.id]), minimum)
                for budget in (minimum - 1, minimum):
                    game = Game(replace(level, action_limit=budget))
                    for action in SOLUTIONS[level.id][:budget]:
                        self.assertTrue(game.act(action), game.message)
                    self.assertEqual(game.state.cleared, budget == minimum)
                    self.assertEqual(game.failed, budget != minimum)
                    self.assertTrue(game.undo())
                    self.assertEqual(game.remaining_actions, 1)
                    self.assertFalse(game.failed)

    def test_route_closing_repairs_are_actual_bottlenecks(self):
        levels = load_levels()

        def reachable(level, start, blocked):
            seen = {start}
            queue = deque(seen)
            while queue:
                x, y = queue.popleft()
                for dx, dy in DIRECTIONS.values():
                    target = (x + dx, y + dy)
                    if (0 <= target[0] < level.width and 0 <= target[1] < level.height
                            and target not in level.walls | blocked and target not in seen):
                        seen.add(target)
                        queue.append(target)
            return seen

        # Open doors isolate the effect of the repaired obstacle itself.
        checks = [
            (levels[1], levels[1].start, (7, 2), {(5, 5)}),
            (levels[2], levels[2].start, (7, 2), {(3, 3)}),
            (levels[3], levels[3].start, (4, 4), {(3, 4)}),
            (levels[3], levels[3].start, (6, 2), {(5, 4)}),
            (levels[5], levels[5].start, (6, 4), {(5, 4)}),
            (levels[5], levels[5].start, (8, 8), {(7, 6)}),
        ]
        for level, start, target, blocked in checks:
            with self.subTest(stage=level.id, blocked=blocked):
                self.assertTrue(blocked <= level.traps | level.posts)
                self.assertIn(target, reachable(level, start, set()))
                self.assertNotIn(target, reachable(level, start, blocked))


if __name__ == "__main__":
    unittest.main()
