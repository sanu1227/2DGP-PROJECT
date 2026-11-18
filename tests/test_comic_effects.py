"""카메라 충격의 여백·종료·재생 일관성을 검사한다."""

import unittest

from game.comic_effects import CAMERA_MARGIN, PANEL_BEATS, Impact, impact_at, panel_frames, sample_impact
from game.story import ENDING, MIDPOINT, PANEL_DURATIONS, ComicPlayback


class ComicEffectsTests(unittest.TestCase):
    def test_later_comic_beat_frames_settle_and_stay_inside_camera_margin(self):
        for page in (*MIDPOINT, *ENDING):
            beat = PANEL_BEATS[page.atlas]
            with self.subTest(panel=page.atlas):
                self.assertEqual(panel_frames(page.atlas, beat, 0), ((beat.before or page.atlas, 1),))
                self.assertEqual(panel_frames(page.atlas, beat, 3), ((beat.after or page.atlas, 1),))
                if beat.before or beat.after:
                    first, second = panel_frames(page.atlas, beat, beat.time + .05)
                    self.assertEqual(first, (beat.before or page.atlas, 1))
                    self.assertEqual(second[0], beat.after or page.atlas)
                    self.assertAlmostEqual(second[1], .5)
                for i in range(46):
                    effect = impact_at(((beat.time, .46, beat.shake),), beat.time + i / 100)
                    self.assertLess(max(abs(effect.x), abs(effect.y)), CAMERA_MARGIN)
                self.assertEqual(impact_at(((beat.time, .46, beat.shake),), beat.time + 1), Impact())

    def test_shake_stays_inside_background_margin_and_finishes_before_next_panel(self):
        for panel, duration in enumerate(PANEL_DURATIONS):
            samples = [sample_impact(panel, i / 120) for i in range(round(duration * 120))]
            self.assertTrue(all(abs(effect.x) < CAMERA_MARGIN and abs(effect.y) < CAMERA_MARGIN
                                for effect in samples))
            self.assertEqual(sample_impact(panel, 0), Impact())
            self.assertEqual(sample_impact(panel, duration - .01), Impact())
            self.assertEqual(sample_impact(panel, duration), Impact())
            if panel != 2:
                self.assertTrue(any(abs(effect.x) > 1 for effect in samples))
            else:
                self.assertTrue(all(effect == Impact() for effect in samples))

    def test_pause_freezes_shake_and_replay_repeats_it(self):
        comic = ComicPlayback(index=3, elapsed=.67, paused=True)
        effect = sample_impact(comic.index, comic.elapsed)
        self.assertNotEqual(effect, Impact())
        comic.update(10)
        self.assertEqual(sample_impact(comic.index, comic.elapsed), effect)
        comic.paused = False
        comic.update(.1)
        self.assertNotEqual(sample_impact(comic.index, comic.elapsed), effect)
        comic.reset()
        comic.update(sum(PANEL_DURATIONS[:3]))
        comic.update(.67)
        self.assertEqual(sample_impact(comic.index, comic.elapsed), effect)


if __name__ == "__main__":
    unittest.main()
