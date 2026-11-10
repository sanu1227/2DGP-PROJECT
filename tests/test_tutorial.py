"""Tutorial goals follow real puzzle state, including recovery actions."""

from copy import deepcopy
import unittest

from game.levels import load_levels
from game.model import Game
from game.navigation import ClickNavigator
from game.tutorial import first_room_hint
from tests.test_game import SOLUTIONS


class TutorialTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_levels()[0])

    def test_solution_and_every_undo_restore_matching_guidance(self):
        game = self.game
        hints, seen = [], set()
        for action in SOLUTIONS[game.level.id]:
            before = deepcopy((game.state, game.history, game.message))
            hint = first_room_hint(game)
            self.assertEqual((game.state, game.history, game.message), before)
            self.assertIsNotNone(hint.target)
            self.assertNotIn(hint.target, game.level.walls)
            hints.append(hint)
            seen.add(hint.step)
            self.assertTrue(game.act(action))
        self.assertEqual(seen, {1, 2, 3, 4, 5})
        self.assertTrue(first_room_hint(game).complete)
        self.assertIsNone(first_room_hint(game).target)
        for hint in reversed(hints):
            self.assertTrue(game.undo())
            self.assertEqual(first_room_hint(game), hint)

    def test_mouse_arrival_waits_for_explicit_pickup_and_drop_tracks_new_location(self):
        game = self.game
        navigation = ClickNavigator()
        target = first_room_hint(game).target
        self.assertTrue(navigation.start(game, target, 0))
        for now in range(10):
            navigation.tick(game, now)
        self.assertEqual(first_room_hint(game).step, 2)
        self.assertIsNone(game.state.carrying)
        game.act("interact")
        self.assertEqual(first_room_hint(game).step, 3)
        game.act("right")
        dropped = game.state.player
        game.act("drop")
        self.assertEqual(first_room_hint(game).step, 2)
        game.act("left")
        self.assertEqual(first_room_hint(game).target, dropped)
        self.assertEqual(first_room_hint(game).step, 1)
        game.undo()
        game.undo()
        self.assertEqual(first_room_hint(game).step, 3)

    def test_invalid_actions_and_early_exit_do_not_advance_tutorial(self):
        game = self.game
        original = first_room_hint(game)
        for action in ("up", "left", "interact", "drop"):
            self.assertFalse(game.act(action))
            self.assertEqual(first_room_hint(game), original)
        navigation = ClickNavigator()
        self.assertTrue(navigation.start(game, game.level.exit, 0))
        for now in range(30):
            navigation.tick(game, now)
        self.assertEqual(game.state.player, game.level.exit)
        self.assertFalse(game.state.cleared)
        self.assertEqual(first_room_hint(game).step, 1)

    def test_restart_resets_guidance_and_other_rooms_have_no_overlay(self):
        game = self.game
        initial = first_room_hint(game)
        for action in SOLUTIONS[game.level.id]:
            game.act(action)
        game.restart()
        self.assertEqual(first_room_hint(game), initial)
        for level in load_levels()[1:]:
            self.assertIsNone(first_room_hint(Game(level)))


if __name__ == "__main__":
    unittest.main()
