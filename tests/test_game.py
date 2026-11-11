"""Repair flows, conservation rules, and undo must work without opening SDL."""

from collections import deque
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from game.levels import load_levels
from game.model import Game
from tests.solutions import SOLUTIONS


DIRECTIONS = {
    "up": (0, -1), "down": (0, 1),
    "left": (-1, 0), "right": (1, 0),
}

def make_level(rows=None):
    """A small mixed room keeps the test scenarios independent of shipped maps."""
    stage = {
        "id": "test_room", "title": "검증용 방", "hint": "복구하고 돌아오세요.",
        "map": rows or [
            "########",
            "#@P.TLE#",
            "#......#",
            "#B.A.S.#",
            "#B.....#",
            "#......#",
            "#......#",
            "########",
        ],
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "room.json"
        path.write_text(json.dumps({"stages": [stage]}), encoding="utf-8")
        return load_levels(path)[0]


class GameTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(make_level())

    def assert_resources(self, game):
        state = game.state
        objects = list(state.items.values()) + [state.carrying]
        self.assertEqual(objects.count("part") + len(state.installed), len(game.level.traps))
        bone_units = objects.count("bone") + sum(state.bench_bones.values())
        bone_units += 2 * (objects.count("soldier") + len(state.soldiers))
        self.assertEqual(bone_units, 2 * len(game.level.posts))

    def act(self, action):
        previous = deepcopy(self.game.state)
        history_size = len(self.game.history)
        self.assertTrue(self.game.act(action), (action, self.game.message))
        self.assertEqual(self.game.state.moves, previous.moves + 1)
        self.assertEqual(len(self.game.history), history_size + 1)
        self.assertEqual(self.game.history[-1], previous)
        self.assert_resources(self.game)

    def go(self, target):
        """Find a walking route only; repair actions remain explicit in each test."""
        game = self.game
        blocked = set(game.level.walls) | game.state.soldiers
        if game.state.active:
            blocked |= game.level.traps
        queue = deque([(game.state.player, [])])
        visited = {game.state.player}
        while queue:
            position, actions = queue.popleft()
            if position == target:
                for action in actions:
                    self.act(action)
                return
            for action, (dx, dy) in DIRECTIONS.items():
                neighbor = (position[0] + dx, position[1] + dy)
                if (0 <= neighbor[0] < game.level.width
                        and 0 <= neighbor[1] < game.level.height
                        and neighbor not in blocked and neighbor not in visited):
                    visited.add(neighbor)
                    queue.append((neighbor, actions + [action]))
        self.fail(f"No route from {game.state.player} to {target}")

    def assert_rejected(self, action):
        previous = deepcopy(self.game.state)
        history = deepcopy(self.game.history)
        self.assertFalse(self.game.act(action), action)
        self.assertEqual(self.game.state, previous)
        self.assertEqual(self.game.history, history)
        self.assertTrue(self.game.message)

    def reachable(self):
        """Check room topology after a route-closing repair without solving it."""
        game = self.game
        blocked = game.level.walls | game.state.soldiers
        if game.state.active:
            blocked |= game.level.traps
        reachable = {game.state.player}
        queue = deque(reachable)
        while queue:
            x, y = queue.popleft()
            for dx, dy in DIRECTIONS.values():
                neighbor = x + dx, y + dy
                if (0 <= neighbor[0] < game.level.width
                        and 0 <= neighbor[1] < game.level.height
                        and neighbor not in blocked and neighbor not in reachable):
                    reachable.add(neighbor)
                    queue.append(neighbor)
        return reachable

    def test_full_repair_conserves_resources_and_every_action_can_be_undone(self):
        initial = deepcopy(self.game.state)
        self.go((2, 1))
        self.act("interact")
        self.assertEqual(self.game.state.carrying, "part")
        self.act("drop")
        self.assertEqual(self.game.state.items[(2, 1)], "part")
        self.act("interact")
        self.go((4, 1))
        self.act("interact")
        self.assertEqual(self.game.state.installed, {(4, 1)})
        self.assertFalse(self.game.state.active)
        self.go((5, 1))
        self.act("interact")
        self.assertTrue(self.game.state.active)
        self.assert_rejected("left")
        self.assert_rejected("interact")
        self.go((6, 1))
        self.assertFalse(self.game.state.cleared)

        for index, bone in enumerate(((1, 3), (1, 4))):
            self.go(bone)
            self.act("interact")
            self.go((3, 3))
            self.act("interact")
            if index == 0:
                self.assertIsNone(self.game.state.carrying)
                self.assertEqual(self.game.state.bench_bones[(3, 3)], 1)
            else:
                self.assertEqual(self.game.state.carrying, "soldier")
                self.assertEqual(self.game.state.bench_bones.get((3, 3), 0), 0)

        self.go((5, 3))
        self.act("interact")
        self.assertEqual(self.game.state.soldiers, {(5, 3)})
        self.assert_rejected("interact")
        self.act("right")
        self.assert_rejected("left")
        self.go((6, 1))
        self.assertTrue(self.game.state.cleared)
        for action in ("left", "interact", "drop"):
            self.assert_rejected(action)

        count = len(self.game.history)
        for _ in range(count):
            expected = deepcopy(self.game.history[-1])
            self.assertTrue(self.game.undo())
            self.assertEqual(self.game.state, expected)
            self.assert_resources(self.game)
        self.assertEqual(self.game.state, initial)
        self.assertFalse(self.game.undo())
        self.assertEqual(self.game.state, initial)

    def test_repair_percent_counts_work_and_preserves_assembled_progress(self):
        game = self.game
        self.assertEqual(game.repair_percent, 0)
        self.go((2, 1))
        self.act("interact")
        self.assertEqual(game.repair_percent, 0)
        self.go((4, 1))
        self.act("interact")
        self.assertEqual(game.repair_percent, 20)
        self.go((5, 1))
        self.act("interact")
        self.assertEqual(game.repair_percent, 40)
        for bone, expected in (((1, 3), 60), ((1, 4), 80)):
            self.go(bone)
            self.act("interact")
            self.go((3, 3))
            self.act("interact")
            self.assertEqual(game.repair_percent, expected)
        self.go((3, 4))
        self.act("interact")  # A loose assembled soldier retains both delivered bones.
        self.assertEqual(game.repair_percent, 80)
        self.act("interact")
        self.assertEqual(game.repair_percent, 80)
        self.go((5, 3))
        self.act("interact")
        self.assertEqual(game.repair_percent, 100)
        self.assertFalse(game.state.cleared)
        self.assertTrue(game.undo())
        self.assertEqual(game.repair_percent, 80)
        game.restart()
        self.assertEqual(game.repair_percent, 0)

    def test_repair_percent_for_traps_only_and_soldiers_only(self):
        for level, expected in zip(load_levels()[:2], ([0, 50, 100], [0, 33, 66, 100])):
            with self.subTest(level=level.id):
                game = Game(level)
                changes, before_actions = [game.repair_percent], []
                for action in SOLUTIONS[level.id]:
                    before_actions.append(game.repair_percent)
                    self.assertTrue(game.act(action))
                    if game.repair_percent != changes[-1]:
                        changes.append(game.repair_percent)
                self.assertEqual(changes, expected)
                for percent in reversed(before_actions):
                    self.assertTrue(game.undo())
                    self.assertEqual(game.repair_percent, percent)

    def test_failed_inputs_do_not_change_inventory_or_history(self):
        for action in ("up", "left", "interact", "drop"):
            self.assert_rejected(action)
        with self.assertRaises(ValueError):
            self.game.act("teleport")
        self.assertEqual(self.game.state.moves, 0)
        self.go((2, 1))
        self.act("interact")
        self.go((1, 3))
        self.assert_rejected("interact")
        self.assert_rejected("drop")
        for target in ((4, 1), (5, 1), (6, 1), (3, 3), (5, 3)):
            self.go(target)
            self.assert_rejected("drop")
        self.go((5, 1))
        self.assert_rejected("interact")

    def test_restart_discards_partial_assembly_and_preserves_level_data(self):
        initial = deepcopy(self.game.state)
        original_items = deepcopy(self.game.level.initial_items)
        self.go((1, 3))
        self.act("interact")
        self.go((3, 3))
        self.act("interact")
        self.assertEqual(self.game.state.bench_bones[(3, 3)], 1)
        self.assertEqual(self.game.level.initial_items, original_items)
        self.game.restart()
        self.assertEqual(self.game.state, initial)
        self.assertEqual(self.game.history, [])
        self.assertFalse(self.game.undo())
        other_game = Game(self.game.level)
        self.go((2, 1))
        self.act("interact")
        self.assertEqual(other_game.state, initial)

    def test_lever_requires_all_traps_and_undo_restores_activation(self):
        self.game = Game(make_level([
            "########", "#@P.TLE#", "#.P.T..#", "#......#",
            "#......#", "#......#", "#......#", "########",
        ]))
        self.go((5, 1))
        self.assert_rejected("interact")
        self.go((2, 1))
        self.act("interact")
        self.go((4, 1))
        self.act("interact")
        self.go((5, 1))
        self.assert_rejected("interact")
        self.go((2, 2))
        self.act("interact")
        self.go((4, 2))
        self.act("interact")
        self.go((5, 1))
        before = deepcopy(self.game.state)
        self.act("interact")
        self.assertTrue(self.game.state.active)
        self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, before)
        self.act("left")

    def test_shipped_rooms_clear_and_can_restart_after_completion(self):
        for level in load_levels():
            with self.subTest(stage=level.id):
                self.game = Game(level)
                initial = deepcopy(self.game.state)
                actions = SOLUTIONS[level.id]
                for action in actions:
                    self.act(action)
                self.assertTrue(self.game.state.cleared)
                self.assertEqual(self.game.state.moves, len(actions))
                self.assertTrue(self.game.undo())
                self.assertFalse(self.game.state.cleared)
                self.act(actions[-1])
                self.assertTrue(self.game.state.cleared)
                self.game.restart()
                self.assertEqual(self.game.state, initial)
                self.assertEqual(self.game.history, [])

    def test_first_room_activation_closes_return_route_but_preserves_exit(self):
        self.game = Game(load_levels()[0])
        self.go((2, 2))
        self.act("interact")
        self.go((6, 4))
        self.act("interact")
        self.go((3, 7))
        self.assertIn(self.game.level.start, self.reachable())
        self.act("interact")
        self.assertNotIn(self.game.level.start, self.reachable())
        self.assertIn(self.game.level.exit, self.reachable())
        self.assertTrue(self.game.undo())
        self.assertIn(self.game.level.start, self.reachable())

    def test_third_room_early_activation_blocks_supplies_and_undo_recovers(self):
        self.game = Game(load_levels()[2])
        for part, trap in (((7, 2), (4, 3)), ((7, 7), (4, 6))):
            self.go(part)
            self.act("interact")
            self.go(trap)
            self.act("interact")
        self.go((2, 7))
        before = deepcopy(self.game.state)
        self.act("interact")
        self.assertTrue(self.game.state.active)
        self.assertTrue(self.game.state.items.keys().isdisjoint(self.reachable()))
        for post in ((3, 3), (3, 6)):
            self.go(post)
            self.assert_rejected("right")
        while self.game.state.active:
            self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, before)
        self.go((6, 3))
        self.act("interact")
        self.assertEqual(self.game.state.carrying, "bone")

    def test_third_room_first_guard_requires_leaving_toward_remaining_work(self):
        self.game = Game(load_levels()[2])
        # Collect both rooms' bones before closing the upper entrance.
        for target in ((7, 2), (4, 3), (6, 3), (2, 5), (8, 8), (2, 5), (3, 3)):
            self.go(target)
            self.act("interact")
        self.assertEqual(self.game.state.soldiers, {(3, 3)})
        self.act("right")
        self.assert_rejected("left")
        self.assertNotIn(self.game.level.exit, self.reachable())
        self.assertTrue(self.game.undo())
        self.act("left")
        reachable = self.reachable()
        self.assertTrue(self.game.state.items.keys() <= reachable)
        self.assertTrue((self.game.level.posts - self.game.state.soldiers) <= reachable)
        self.assertTrue(self.game.level.benches | self.game.level.levers | {self.game.level.exit} <= reachable)


if __name__ == "__main__":
    unittest.main()
