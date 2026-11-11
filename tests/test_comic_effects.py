"""카메라 충격의 여백·종료·재생 일관성을 검사한다."""

import unittest

from game.comic_effects import CAMERA_MARGIN, Impact, sample_impact
from game.story import PANEL_DURATIONS, ComicPlayback


class ComicEffectsTests(unittest.TestCase):
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
