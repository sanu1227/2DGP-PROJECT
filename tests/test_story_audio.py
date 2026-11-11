import unittest

from game.story_audio import CUES, StoryAudio
from game.story import PANEL_DURATIONS


class Recorder:
    def __init__(self):
        self.played = []
        self.paused = False
        self.stops = 0

    def play(self, name):
        self.played.append(name)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.stops += 1
        self.paused = False

    def close(self):
        self.stop()


class StoryAudioTests(unittest.TestCase):
    def test_regular_frames_play_each_cue_once(self):
        backend = Recorder()
        audio = StoryAudio(backend)
        for index, duration in enumerate(PANEL_DURATIONS):
            for step in range(round(duration * 60) + 1):
                audio.update(index, step / 60)
                audio.update(index, step / 60)
        self.assertEqual(backend.played, [name for cues in CUES for _, name in cues])

    def test_pause_resume_preserves_cursor_without_replaying_sigh(self):
        backend = Recorder()
        audio = StoryAudio(backend)
        audio.seek(2, 3.4)
        audio.update(2, 3.46)
        self.assertEqual(backend.played, ["worker_sigh"])
        audio.update(2, 3.46, paused=True)
        self.assertTrue(backend.paused)
        audio.update(2, 3.46, paused=True)
        audio.update(2, 3.51)
        self.assertFalse(backend.paused)
        self.assertEqual(backend.played, ["worker_sigh"])

    def test_skip_and_slow_frames_do_not_play_stale_sounds(self):
        backend = Recorder()
        audio = StoryAudio(backend)
        audio.update(0, 2.0)
        audio.update(2, 4.0)
        self.assertFalse(backend.played)
        audio.seek(3, 3.5, paused=True)
        audio.update(3, 3.5, paused=True)
        self.assertFalse(backend.played)
        audio.seek(0)
        audio.update(0, .43)
        self.assertEqual(backend.played, ["hero_arrival"])
        audio.stop()
        self.assertIsNone(audio.index)
        self.assertGreater(backend.stops, 0)


if __name__ == "__main__":
    unittest.main()
