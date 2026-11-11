"""수리공이 걷기를 마친 뒤 서서 한숨을 쉬는 순서를 검증한다."""

import unittest

from game.character_motion import (ACCEL_SECONDS, EXHALE_END, EXHALE_START, INHALE_START,
                                   MOTION_END, WALK_START, WALK_END, worker_motion)
from game.story import ComicPlayback, PANEL_DURATIONS


class CharacterMotionTests(unittest.TestCase):
    def test_walk_uses_twelve_foot_poses_and_moves_forward(self):
        samples = [worker_motion(WALK_START + i / 60) for i in range(120)]
        self.assertEqual({pose.frame for pose in samples}, set(range(12)))
        self.assertTrue(all(a.x <= b.x for a, b in zip(samples, samples[1:])))
        self.assertGreater(samples[-1].x - samples[0].x, .16)
        self.assertTrue(all(pose.bob == 0 and pose.stretch == 1 for pose in samples))
        self.assertTrue(all(pose.breath is None for pose in samples))

    def test_stop_then_inhale_then_sigh_without_more_walking(self):
        samples = [worker_motion(t) for t in (2.6, 3.2, 3.7, 4.2, 5.2)]
        self.assertEqual([pose.phase for pose in samples], ["stop", "inhale", "sigh", "sigh", "rest"])
        self.assertLess(samples[0].x, samples[1].x)
        self.assertEqual(len({pose.x for pose in samples[1:]}), 1)
        self.assertTrue(all(pose.bob == 0 for pose in samples))
        self.assertTrue(all(pose.stretch == 1 for pose in samples))
        self.assertLess(samples[2].breath, samples[3].breath)
        self.assertIsNone(samples[-1].breath)

    def test_all_transition_poses_play_in_order_at_game_frame_rate(self):
        samples = [worker_motion(i / 60) for i in range(round(MOTION_END * 60) + 1)]
        self.assertEqual({pose.frame for pose in samples}, set(range(36)))
        transitions = [pose.frame for pose in samples if pose.phase in ("stop", "inhale", "sigh", "rest")]
        self.assertEqual(sorted(set(transitions)), list(range(12, 36)))
        self.assertEqual(transitions, sorted(transitions))

    def test_position_and_velocity_are_continuous_at_acceleration_boundaries(self):
        dt = .0001
        for t in (WALK_START, WALK_START + ACCEL_SECONDS, WALK_END, INHALE_START,
                  EXHALE_START, EXHALE_END):
            with self.subTest(time=t):
                before, at, after = [worker_motion(age).x for age in (t - dt, t, t + dt)]
                self.assertLess(abs(after - before), .00003)
                self.assertAlmostEqual((at - before) / dt, (after - at) / dt, delta=.0001)
        self.assertAlmostEqual(worker_motion(0).x, .24)
        self.assertAlmostEqual(worker_motion(MOTION_END).x, .44)

    def test_last_step_decelerates_before_breathing(self):
        times = [WALK_END + i * (INHALE_START - WALK_END) / 6 for i in range(7)]
        positions = [worker_motion(t).x for t in times]
        distances = [b - a for a, b in zip(positions, positions[1:])]
        self.assertTrue(all(d > 0 for d in distances))
        self.assertEqual(distances, sorted(distances, reverse=True))
        self.assertEqual(worker_motion(INHALE_START).x, worker_motion(EXHALE_END).x)

    def test_finished_and_previous_panel_hold_the_rest_pose(self):
        rest = worker_motion(MOTION_END)
        self.assertEqual(worker_motion(PANEL_DURATIONS[2]), rest)
        self.assertEqual(worker_motion(1000), rest)
        comic = ComicPlayback(index=3)
        self.assertEqual(worker_motion(comic.age(2)), rest)
        comic.back()
        self.assertEqual(comic.index, 2)
        self.assertGreaterEqual(comic.elapsed, EXHALE_END)
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
        comic.update(sum(PANEL_DURATIONS[:2]))
        self.assertEqual(worker_motion(comic.age(2)), worker_motion(0))


if __name__ == "__main__":
    unittest.main()
