"""Repair flows, conservation rules, and undo must work without opening SDL."""

from collections import deque
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from game.levels import load_levels
from game.model import Game


DIRECTIONS = {
    "up": (0, -1), "down": (0, 1),
    "left": (-1, 0), "right": (1, 0),
}

# Authored walkthroughs double as regression checks for the actual room data.
SOLUTIONS = {
    "stage_01": (
        "down right interact down right right right right right right down down "
        "interact down down down down left left left left left interact left left"
    ).split(),
    "stage_02": (
        "down down down down down right right right right right right right right "
        "right up up up up left interact down down right down down left left left "
        "left left left left interact right right right right down down down right "
        "right interact up up up left left left left left left interact right right "
        "right interact left down down down down left left left left"
    ).split(),
    "stage_03": (
        "down down right right right right right up right right right interact down "
        "left left left left interact right right right interact left left left left "
        "left down down down left interact up up up right right right right down "
        "right right right right interact up left left left left left left left down "
        "down down left interact up up up right right interact left down down down "
        "down down right right right down right right right interact up left left "
        "left left interact right right right interact left left left left left up "
        "up left interact down down right right right right up right right right "
        "right interact down left left left left left left left up up left interact "
        "down down right right interact left down left interact down left"
    ).split(),
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

    def test_three_shipped_rooms_clear_and_can_restart_after_completion(self):
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

    def test_third_room_early_activation_blocks_supplies_and_undo_recovers(self):
        self.game = Game(load_levels()[2])
        for part, trap in (((9, 2), (5, 3)), ((9, 9), (5, 8))):
            self.go(part)
            self.act("interact")
            self.go(trap)
            self.act("interact")
        self.go((2, 9))
        before = deepcopy(self.game.state)
        self.act("interact")
        self.assertTrue(self.game.state.active)
        self.assertTrue(self.game.state.items.keys().isdisjoint(self.reachable()))
        for post in ((4, 3), (4, 8)):
            self.go(post)
            self.assert_rejected("right")
        while self.game.state.active:
            self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, before)
        self.go((8, 3))
        self.act("interact")
        self.assertEqual(self.game.state.carrying, "bone")

    def test_third_room_first_guard_requires_leaving_toward_remaining_work(self):
        self.game = Game(load_levels()[2])
        # Finish the upper storeroom before closing its only entrance.
        for target in ((9, 2), (5, 3), (8, 3), (2, 6), (10, 4), (2, 6), (4, 3)):
            self.go(target)
            self.act("interact")
        self.assertEqual(self.game.state.soldiers, {(4, 3)})
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
