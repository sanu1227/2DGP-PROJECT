"""네 컷 순차 재생과 읽기·되돌아보기 동작을 화면 없이 검사한다."""

import unittest

from game.front_end import FrontEnd
from game.story import ComicPlayback, ENDING, ENDING_DURATIONS, PANEL_DURATIONS, REVEAL_SECONDS, STORY


class ComicTests(unittest.TestCase):
    def test_automatic_reveal_keeps_earlier_panels_and_hides_future_ones(self):
        comic = ComicPlayback()
        self.assertEqual(len(STORY), 4)
        for index in range(4):
            self.assertEqual(comic.index, index)
            self.assertEqual([i for i in range(4) if comic.age(i) is not None], list(range(index + 1)))
            for earlier in range(index):
                self.assertEqual(comic.age(earlier), PANEL_DURATIONS[earlier])
            comic.update(comic.duration - comic.elapsed - 0.01)
            self.assertEqual(comic.index, index)
            comic.update(0.02)
        self.assertTrue(comic.finished)
        comic.update(1000)
        self.assertEqual((comic.index, comic.elapsed), (3, PANEL_DURATIONS[3]))

    def test_variable_frame_times_produce_the_same_sequence(self):
        one_frame, many_frames = ComicPlayback(), ComicPlayback()
        one_frame.update(15)
        for _ in range(150):
            many_frames.update(0.1)
        self.assertEqual(one_frame.index, many_frames.index)
        self.assertAlmostEqual(one_frame.elapsed, many_frames.elapsed)

    def test_pause_and_back_allow_reading_without_timer_advancing(self):
        comic = ComicPlayback()
        comic.update(sum(PANEL_DURATIONS[:2]) + 1)
        self.assertTrue(comic.back())
        rest_time = min(REVEAL_SECONDS, comic.duration)
        self.assertEqual((comic.index, comic.elapsed, comic.paused), (1, rest_time, True))
        comic.update(100)
        self.assertEqual(comic.index, 1)
        self.assertEqual(comic.elapsed, rest_time)
        comic.paused = False
        comic.update(comic.duration - rest_time + 0.01)
        self.assertEqual(comic.index, 2)

    def test_manual_navigation_and_replay_reset_visibility(self):
        comic = ComicPlayback()
        self.assertFalse(comic.back())
        for _ in range(3):
            self.assertTrue(comic.advance())
            self.assertEqual(comic.elapsed, 0)
        self.assertFalse(comic.advance())
        comic.paused = True
        comic.reset()
        self.assertEqual((comic.index, comic.elapsed, comic.paused), (0, 0, False))
        self.assertIsNone(comic.age(1))

    def test_ending_stops_on_last_panel_and_replay_returns_to_room_selection(self):
        menu = FrontEnd()
        self.addCleanup(menu.close)
        menu.ending_return = "rooms"
        menu.activate("ending")
        menu.update(menu.story_clock + sum(ENDING_DURATIONS) + 1)
        self.assertEqual(menu.screen, "ending")
        self.assertEqual(menu.story_page, len(ENDING) - 1)
        self.assertTrue(menu.ending.finished)
        self.assertEqual(menu.buttons[0].label, "방 선택으로")
        menu.activate("story_play")
        self.assertEqual(menu.story_page, 0)
        menu.activate("story_next")
        menu.activate("story_back")
        self.assertTrue(menu.ending.paused)
        for _ in ENDING:
            menu.activate("story_next")
        self.assertEqual(menu.screen, "rooms")


if __name__ == "__main__":
    unittest.main()
