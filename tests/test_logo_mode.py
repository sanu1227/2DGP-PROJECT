import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pico2d.pico2d as p

from game.front_end import FrontEnd
from game.logo_mode import FADE_SECONDS, LOGO_DURATIONS, LogoPlayback, sample_letter


class LogoModeTests(unittest.TestCase):
    def test_letters_appear_separately_then_settle(self):
        self.assertEqual(sample_letter(0, 0).opacity, 0)
        self.assertEqual(sample_letter(0, 1).opacity, 0)
        self.assertEqual(sample_letter(.5, 0).opacity, 1)
        self.assertEqual(sample_letter(.5, 1).opacity, 0)
        self.assertGreater(sample_letter(.95, 1).opacity, 0)
        for index in (0, 1):
            settled = sample_letter(1.3, index)
            self.assertEqual((settled.opacity, settled.scale, settled.x, settled.y), (1, 1, 0, 0))
            samples = [sample_letter(i / 120, index) for i in range(180)]
            self.assertGreater(max(pose.scale for pose in samples), 1)
            self.assertTrue(all(0 <= pose.opacity <= 1 and .85 < pose.scale < 1.03 for pose in samples))

    def test_sequence_carries_time_and_finishes_without_looping(self):
        playback = LogoPlayback()
        playback.update(LOGO_DURATIONS[0] + .2)
        self.assertEqual(playback.index, 1)
        self.assertAlmostEqual(playback.age, .2)
        playback.update(-1)
        self.assertAlmostEqual(playback.age, .2)
        playback.update(100)
        self.assertTrue(playback.finished)
        self.assertEqual(playback.elapsed, sum(LOGO_DURATIONS))
        self.assertEqual(playback.opacity, 0)

    def test_both_logos_fade_in_hold_and_fade_out(self):
        offset = 0
        for duration in LOGO_DURATIONS:
            values = [LogoPlayback(offset + age).opacity for age in
                      (0, FADE_SECONDS / 2, FADE_SECONDS, duration / 2,
                       duration - FADE_SECONDS / 2)]
            for actual, expected in zip(values, (0, .5, 1, 1, .5)):
                self.assertAlmostEqual(actual, expected)
            offset += duration

    def test_automatic_title_starts_its_own_clock_and_returns_directly(self):
        menu = FrontEnd(audio=Mock())
        self.assertEqual(menu.screen, "logo")
        menu.update(100)
        menu.update(102.3)
        self.assertEqual(menu.logos.index, 1)
        menu.update(104.9)
        self.assertEqual(menu.screen, "title")
        self.assertEqual(menu.title_elapsed, 0)
        self.assertTrue(menu.title_fade_in)
        menu.update(105.4)
        self.assertAlmostEqual(menu.title_elapsed, .5)
        menu.activate("story")
        menu.activate("title")
        self.assertEqual(menu.screen, "title")
        self.assertFalse(menu.title_fade_in)
        menu.close()

    def test_logo_inputs_are_isolated_and_each_skip_advances_one_card(self):
        menu = FrontEnd(audio=Mock())
        for key in (p.SDLK_TAB, p.SDLK_UP, p.SDLK_LEFT, p.SDLK_1, p.SDLK_e):
            self.assertIsNone(menu.handle(SimpleNamespace(type=p.SDL_KEYDOWN, key=key)))
        self.assertEqual(menu.logos.elapsed, 0)
        with patch("game.front_end.perf_counter", return_value=10):
            menu.handle(SimpleNamespace(type=p.SDL_KEYDOWN, key=p.SDLK_SPACE))
            self.assertEqual(menu.screen, "logo")
            self.assertEqual(menu.logos.index, 1)
            menu.handle(SimpleNamespace(type=p.SDL_MOUSEBUTTONDOWN, button=p.SDL_BUTTON_RIGHT))
            self.assertEqual(menu.screen, "logo")
            menu.handle(SimpleNamespace(type=p.SDL_MOUSEBUTTONDOWN, button=p.SDL_BUTTON_LEFT))
        self.assertEqual(menu.screen, "title")
        self.assertEqual(menu.title_clock, 10)
        self.assertEqual(menu.comic.index, 0)
        menu.close()

    def test_escape_skips_all_logos_and_stage_launch_bypasses_them(self):
        menu = FrontEnd(audio=Mock())
        menu.handle(SimpleNamespace(type=p.SDL_KEYDOWN, key=p.SDLK_ESCAPE))
        self.assertEqual(menu.screen, "title")
        menu.close()
        direct = FrontEnd(show_title=False, audio=Mock())
        direct.update(0)
        direct.update(100)
        self.assertEqual(direct.screen, "playing")
        self.assertEqual(direct.images, {})
        direct.close()


if __name__ == "__main__":
    unittest.main()
