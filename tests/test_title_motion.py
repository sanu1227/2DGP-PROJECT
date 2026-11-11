import unittest

from game.title_motion import BLINK_PERIOD, SPRITES, sample_title


class TitleMotionTests(unittest.TestCase):
    def test_animation_uses_available_poses_and_stays_within_background_margin(self):
        poses = [sample_title(i / 120) for i in range(1200)]
        self.assertEqual({pose.skeleton for pose in poses}, set(range(8)))
        self.assertEqual({pose.worker for pose in poses}, set(range(4)))
        self.assertEqual({pose.flame for pose in poses}, set(range(8)))
        self.assertTrue(all(abs(pose.background_x) <= 6 and abs(pose.background_y) <= 3 for pose in poses))
        self.assertTrue(all(.88 <= pose.logo_scale <= 1.02 for pose in poses))
        self.assertTrue(all(f"wave_{pose.skeleton}" in SPRITES for pose in poses))
        self.assertTrue(all(0 <= pose.worker_dip <= 1 for pose in poses))

    def test_replay_resets_logo_and_frame_sampling_is_deterministic(self):
        self.assertNotEqual(sample_title(0), sample_title(3.75))
        self.assertEqual(sample_title(0), sample_title(-1))

    def test_first_greeting_is_visible_early_and_closed_eyes_are_held(self):
        self.assertIn(sample_title(.9).skeleton, (3, 4))
        self.assertEqual(sample_title(.9).worker, 2)
        self.assertEqual(sample_title(1.6).worker, 2)
        self.assertEqual(sample_title(2.1).worker, 0)
        frames = [sample_title(i / 120) for i in range(round(BLINK_PERIOD * 120))]
        self.assertGreaterEqual(sum(pose.worker == 2 for pose in frames) / 120, .53)
        self.assertAlmostEqual(sample_title(.9).worker_dip, 1)


if __name__ == "__main__":
    unittest.main()
