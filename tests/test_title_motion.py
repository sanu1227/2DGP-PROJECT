import unittest

from game.title_motion import MANIFEST, sample_title


class TitleMotionTests(unittest.TestCase):
    def test_animation_uses_available_poses_and_stays_within_background_margin(self):
        poses = [sample_title(i / 120) for i in range(1200)]
        self.assertEqual({pose.skeleton for pose in poses}, set(range(4)))
        self.assertEqual({pose.worker for pose in poses}, set(range(4)))
        self.assertEqual({pose.flame for pose in poses}, set(range(8)))
        self.assertTrue(all(abs(pose.background_x) <= 6 and abs(pose.background_y) <= 3 for pose in poses))
        self.assertTrue(all(.88 <= pose.logo_scale <= 1.02 for pose in poses))
        self.assertEqual(len(MANIFEST["sprites"]), 17)

    def test_replay_resets_logo_and_frame_sampling_is_deterministic(self):
        self.assertNotEqual(sample_title(0), sample_title(3.75))
        self.assertEqual(sample_title(0), sample_title(-1))
        self.assertEqual(sample_title(3.75), sample_title(3.75))


if __name__ == "__main__":
    unittest.main()
