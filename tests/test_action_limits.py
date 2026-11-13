"""Action budget boundaries, recovery and level validation."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from game.levels import load_levels
from game.model import Game
from game.navigation import ClickNavigator, find_path
from tests.test_game import SOLUTIONS


class ActionLimitTests(unittest.TestCase):
    def setUp(self):
        self.levels = load_levels()

    def test_unlimited_tutorial_and_authored_budgets(self):
        self.assertEqual([l.action_limit for l in self.levels], [None, 35, 47, 34, 37, 42, 43, 85])
        game = Game(self.levels[0])
        for index in range(200):
            self.assertTrue(game.act("right" if index % 2 == 0 else "left"))
        self.assertIsNone(game.remaining_actions)
        self.assertFalse(game.failed)
        for level in self.levels:
            game = Game(level)
            for action in SOLUTIONS[level.id]:
                before = game.state.moves
                self.assertTrue(game.act(action), (level.id, game.message))
                self.assertEqual(game.state.moves, before + 1)
            self.assertTrue(game.state.cleared)
            self.assertFalse(game.failed)

    def test_invalid_inputs_do_not_spend_budget(self):
        game = Game(replace(self.levels[1], action_limit=2))
        before = deepcopy(game.state)
        for action in ("up", "left", "interact", "drop"):
            self.assertFalse(game.act(action))
            self.assertEqual(game.state, before)
            self.assertEqual(game.remaining_actions, 2)
            self.assertFalse(game.history)

    def test_last_action_success_takes_priority_over_failure(self):
        actions = SOLUTIONS[self.levels[0].id]
        for budget, cleared in ((len(actions), True), (len(actions) - 1, False)):
            game = Game(replace(self.levels[0], action_limit=budget))
            for action in actions[:budget]:
                self.assertTrue(game.act(action))
            self.assertEqual(game.remaining_actions, 0)
            self.assertEqual(game.state.cleared, cleared)
            self.assertEqual(game.failed, not cleared)
            self.assertFalse(game.act("right"))

    def test_failure_freezes_devices_and_undo_restores_last_action(self):
        game = Game(replace(self.levels[5], action_limit=6))
        actions = SOLUTIONS[game.level.id][:6]
        for action in actions[:-1]:
            self.assertTrue(game.act(action))
        before = deepcopy(game.state)
        self.assertTrue(game.act(actions[-1]))
        self.assertTrue(game.failed)
        frozen, history = deepcopy(game.state), deepcopy(game.history)
        for action in ("right", "interact", "drop"):
            self.assertFalse(game.act(action))
            self.assertEqual(game.state, frozen)
            self.assertEqual(game.history, history)
        self.assertFalse(game.can_interact())
        self.assertTrue(game.undo())
        self.assertEqual(game.state, before)
        self.assertEqual(game.remaining_actions, 1)
        self.assertFalse(game.failed)
        self.assertTrue(game.act(actions[-1]))
        self.assertEqual(game.state, frozen)
        game.restart()
        self.assertEqual(game.state, Game(game.level).state)
        self.assertEqual(game.remaining_actions, 6)
        self.assertFalse(game.failed)
        self.assertFalse(game.history)

    def test_auto_movement_stops_at_budget_and_can_resume_after_undo(self):
        game = Game(replace(self.levels[0], action_limit=2))
        nav = ClickNavigator()
        self.assertTrue(nav.start(game, (3, 1), 0))
        self.assertEqual(nav.tick(game, 0), "right")
        self.assertEqual(nav.tick(game, .2), "right")
        self.assertTrue(game.failed)
        self.assertFalse(nav.active)
        self.assertEqual(game.state.player, (3, 1))
        message = game.message
        self.assertIsNone(nav.tick(game, 1))
        self.assertIsNone(find_path(game, (3, 1)))
        self.assertFalse(nav.start(game, (3, 1), 1))
        self.assertEqual(game.message, message)
        self.assertTrue(game.undo())
        self.assertTrue(nav.start(game, (3, 1), 2))
        self.assertEqual(nav.tick(game, 2), "right")
        self.assertTrue(game.failed)

    def test_budget_validation(self):
        source = Path(__file__).resolve().parents[1] / "data" / "stages.json"
        document = json.loads(source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "levels.json"
            for value in (0, -1, True, 1.5, "30", [], {}):
                document["stages"][1]["action_limit"] = value
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "action_limit"):
                    load_levels(path)
            del document["stages"][1]["action_limit"]
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertIsNone(load_levels(path)[1].action_limit)


if __name__ == "__main__":
    unittest.main()
