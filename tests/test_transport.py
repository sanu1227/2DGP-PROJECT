"""Transport playback never spends extra actions or changes puzzle state."""

from copy import deepcopy
import unittest

from game.model import Game
from game.transport import BELT_SECONDS, BeltAnimation
from tests.test_devices import belt_stage, load_stage


class TransportAnimationTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_stage(belt_stage()))
        self.game.state.player = (3, 3)
        self.game.state.carrying = self.game.state.items.pop((2, 1))
        self.before = deepcopy(self.game.state)
        self.assertTrue(self.game.act("interact"))
        self.animation = BeltAnimation()
        self.animation.start(self.game, 0)

    def test_each_segment_replays_then_unlocks_without_changing_state(self):
        final = deepcopy(self.game.state)
        for when, source, target, fraction in (
                (0, (3, 3), (4, 3), 0),
                (BELT_SECONDS / 2, (3, 3), (4, 3), .5),
                (BELT_SECONDS, (4, 3), (5, 3), 0),
                (BELT_SECONDS * 1.5, (4, 3), (5, 3), .5)):
            state, moves, progress = self.animation.sample(self.game, when)
            self.assertEqual(state.items[source], "part")
            self.assertEqual(moves, ((source, target, "part"),))
            self.assertAlmostEqual(progress, fraction)
        self.assertIsNone(self.animation.sample(self.game, BELT_SECONDS * 2))
        self.assertEqual(self.game.state, final)
        self.assertEqual(len(self.game.history), 1)

    def test_undo_restart_and_room_change_cancel_playback(self):
        self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, self.before)
        self.assertIsNone(self.animation.sample(self.game, .01))
        self.assertTrue(self.game.act("interact"))
        self.animation.start(self.game, 0)
        self.assertIsNone(self.animation.sample(Game(self.game.level), .01))
        self.game.restart()
        self.assertIsNone(self.animation.sample(self.game, .01))

    def test_wait_action_is_removed(self):
        with self.assertRaises(ValueError):
            self.game.act("wait")


if __name__ == "__main__":
    unittest.main()
