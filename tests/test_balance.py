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
            (levels[0], levels[0].start, levels[0].exit, levels[0].traps),
            (levels[1], levels[1].start, (5, 1), levels[1].posts),
            (levels[2], levels[2].start, (6, 2), levels[2].posts),
            (levels[2], levels[2].start, (6, 5), {(4, 5)}),
            (levels[5], levels[5].start, levels[5].exit, levels[5].traps),
            (levels[6], levels[6].start, (6, 2), levels[6].posts),
            (levels[6], levels[6].start, levels[6].exit, levels[6].traps),
            (levels[7], levels[7].start, (7, 8), {(4, 7)}),
        ]
        for level, start, target, blocked in checks:
            with self.subTest(stage=level.id, blocked=blocked):
                self.assertTrue(blocked <= level.traps | level.posts)
                self.assertIn(target, reachable(level, start, set()))
                self.assertNotIn(target, reachable(level, start, blocked))


if __name__ == "__main__":
    unittest.main()
