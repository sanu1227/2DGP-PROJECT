"""수리공이 걷기를 마친 뒤 서서 한숨을 쉬는 순서를 검증한다."""

import unittest

from game.character_motion import MOTION_END, WALK_START, WALK_END, worker_motion
from game.story import ComicPlayback, PANEL_SECONDS, REVEAL_SECONDS


class CharacterMotionTests(unittest.TestCase):
    def test_walk_uses_six_foot_poses_and_moves_forward(self):
        samples = [worker_motion(WALK_START + i / 60) for i in range(120)]
        self.assertEqual({pose.frame for pose in samples}, set(range(6)))
        self.assertTrue(all(a.x <= b.x for a, b in zip(samples, samples[1:])))
        self.assertGreater(samples[-1].x - samples[0].x, .18)
        self.assertTrue(any(pose.bob < -1 for pose in samples))
        self.assertTrue(all(pose.breath is None for pose in samples))

    def test_stop_then_inhale_then_sigh_without_more_walking(self):
        samples = [worker_motion(t) for t in (2.8, 3.2, 3.7, 4.2, 5.2)]
        self.assertEqual([pose.phase for pose in samples], ["stop", "inhale", "sigh", "sigh", "rest"])
        self.assertEqual(len({pose.x for pose in samples}), 1)
        self.assertTrue(all(pose.bob == 0 for pose in samples))
        self.assertGreater(samples[1].stretch, samples[-1].stretch)
        self.assertEqual([pose.frame for pose in samples], [6, 7, 8, 9, 10])
        self.assertLess(samples[2].breath, samples[3].breath)
        self.assertIsNone(samples[-1].breath)

    def test_finished_and_previous_panel_hold_the_rest_pose(self):
        rest = worker_motion(MOTION_END)
        self.assertEqual(worker_motion(PANEL_SECONDS), rest)
        self.assertEqual(worker_motion(1000), rest)
        comic = ComicPlayback(index=3)
        self.assertEqual(worker_motion(comic.age(2)), rest)
        comic.back()
        self.assertEqual(comic.index, 2)
        self.assertGreaterEqual(REVEAL_SECONDS, MOTION_END)
        self.assertEqual(worker_motion(comic.elapsed), rest)

    def test_pause_freezes_pose_and_replay_returns_to_entry(self):
        comic = ComicPlayback(index=2, elapsed=3.8, paused=True)
        pose = worker_motion(comic.age(2))
        comic.update(20)
        self.assertEqual(worker_motion(comic.age(2)), pose)
        comic.paused = False
        comic.update(.3)
        self.assertNotEqual(worker_motion(comic.age(2)), pose)
        comic.reset()
        comic.update(PANEL_SECONDS * 2)
        self.assertEqual(worker_motion(comic.age(2)), worker_motion(0))


if __name__ == "__main__":
    unittest.main()
