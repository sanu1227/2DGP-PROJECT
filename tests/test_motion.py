"""표시 보간이 빠른 입력의 코너와 실제 이동 순서를 보존하는지 검사한다."""

import unittest

from game.motion import GridMotion


class GridMotionTests(unittest.TestCase):
    def assert_position(self, actual, expected):
        for value, target in zip(actual, expected):
            self.assertAlmostEqual(value, target)

    def test_single_step_eases_along_one_axis_and_finishes_at_model_position(self):
        motion = GridMotion()
        motion.start((2, 2), (2, 1), 10.0)
        self.assertEqual(motion.position((2, 1), 10.0), (2.0, 2.0))
        self.assert_position(motion.position((2, 1), 10.035), (2.0, 1.84375))
        self.assertEqual(motion.direction, "up")
        self.assertAlmostEqual(motion.phase, 0.25)
        self.assert_position(motion.position((2, 1), 10.07), (2.0, 1.5))
        self.assertEqual(motion.position((2, 1), 10.15), (2.0, 1.0))
        self.assertFalse(motion.moving)
        self.assertIsNone(motion.direction)

    def test_quick_turn_keeps_the_corner_and_current_facing(self):
        motion = GridMotion()
        motion.start((2, 2), (2, 1), 0.0)
        before = motion.position((2, 1), 0.035)
        motion.start((2, 1), (3, 1), 0.035)
        self.assertEqual(motion.position((3, 1), 0.035), before)
        self.assert_position(motion.position((3, 1), 0.07), (2.0, 1.5))
        self.assertEqual(motion.direction, "up")
        self.assertEqual(motion.position((3, 1), 0.14), (2.0, 1.0))
        self.assertEqual(motion.direction, "right")
        self.assert_position(motion.position((3, 1), 0.175), (2.5, 1.0))
        self.assertEqual(motion.position((3, 1), 0.22), (3.0, 1.0))

    def test_burst_replays_every_leg_without_replacing_pending_steps(self):
        motion = GridMotion()
        route = ((1, 2), (1, 1), (2, 1), (2, 2), (3, 2))
        for previous, destination in zip(route, route[1:]):
            motion.start(previous, destination, 0.0)
        for now, position, direction in (
            (0.07, (1.0, 1.5), "up"),
            (0.175, (1.5, 1.0), "right"),
            (0.245, (2.0, 1.5), "down"),
            (0.315, (2.5, 2.0), "right"),
        ):
            with self.subTest(now=now):
                self.assert_position(motion.position(route[-1], now), position)
                self.assertEqual(motion.direction, direction)
        self.assertEqual(motion.position(route[-1], 1.0), (3.0, 2.0))
        self.assertFalse(motion.moving)

    def test_new_input_after_idle_uses_full_duration(self):
        motion = GridMotion()
        motion.start((1, 1), (2, 1), 0.0)
        motion.start((2, 1), (2, 2), 1.0)
        self.assert_position(motion.position((2, 2), 1.07), (2.0, 1.5))
        self.assertTrue(motion.moving)
        self.assertEqual(motion.position((2, 2), 1.15), (2.0, 2.0))

    def test_reset_discards_old_display_path_after_undo_or_interaction(self):
        motion = GridMotion()
        motion.start((1, 1), (2, 1), 0.0)
        motion.start((2, 1), (2, 2), 0.01)
        motion.reset()
        self.assertEqual(motion.position((1, 1), 0.02), (1.0, 1.0))
        self.assertFalse(motion.moving)
        self.assertEqual(motion.phase, 0.0)
        motion.start((1, 1), (1, 2), 0.03)
        self.assert_position(motion.position((1, 2), 0.10), (1.0, 1.5))

    def test_rejects_diagonal_disconnected_and_invalid_timed_paths(self):
        for duration in (0, -1, float("inf"), float("nan")):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                GridMotion(duration)
        motion = GridMotion()
        for target in ((2, 2), (3, 1), (1, 1)):
            with self.subTest(target=target), self.assertRaises(ValueError):
                motion.start((1, 1), target, 0.0)
        motion.start((1, 1), (2, 1), 0.0)
        with self.assertRaises(ValueError):
            motion.start((5, 5), (6, 5), 0.01)
        self.assert_position(motion.position((2, 1), 0.07), (1.5, 1.0))


if __name__ == "__main__":
    unittest.main()
