import unittest
from unittest.mock import Mock, patch

from game.music import BackgroundMusic, FADE_IN_MS, TRACKS, VOLUMES


class BackgroundMusicTests(unittest.TestCase):
    def setUp(self):
        self.mixer = Mock()
        self.mixer.Mix_QuerySpec.return_value = 1
        self.mixer.Mix_FadeInMusic.return_value = 0
        self.mixer.load_music.side_effect = lambda path: Mock()
        self.modules = patch.dict("sys.modules", {
            "pico2d": Mock(pico2d=self.mixer), "pico2d.pico2d": self.mixer})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.music = BackgroundMusic()
        self.addCleanup(self.music.close)

    def test_title_controls_share_track_and_story_keeps_effect_channels(self):
        self.music.update("logo")
        self.mixer.load_music.assert_not_called()
        self.music.update("title")
        self.music.update("controls")
        self.mixer.load_music.assert_called_once_with(str(TRACKS["title"]))
        self.mixer.Mix_FadeInMusic.assert_called_once_with(
            self.music.tracks["title"].music, -1, FADE_IN_MS)
        self.music.update("story")
        self.music.update("story")
        self.mixer.Mix_HaltMusic.assert_called_once()
        self.mixer.Mix_HaltChannel.assert_not_called()

    def test_pause_resume_and_room_changes_do_not_restart_music(self):
        self.music.update("playing")
        track = self.music.tracks["playing"]
        for quiet in (True, True, False, False):
            self.music.update("playing", quiet=quiet)
        self.mixer.Mix_FadeInMusic.assert_called_once()
        self.assertEqual([call.args[0] for call in track.set_volume.call_args_list],
                         [VOLUMES["playing"], VOLUMES["playing"] // 2, VOLUMES["playing"]])
        self.music.update("title")
        self.music.update("playing")
        self.assertEqual(self.mixer.load_music.call_count, 2)
        self.assertEqual(self.mixer.Mix_FadeInMusic.call_count, 3)
        self.music.close()
        self.assertFalse(self.music.tracks)
        self.assertIsNone(self.music.current)

    def test_bad_track_warns_once_and_other_track_still_plays(self):
        self.mixer.load_music.side_effect = [OSError("broken MP3"), Mock()]
        with self.assertWarnsRegex(RuntimeWarning, "Dungeon Title Theme"):
            self.music.update("title")
        self.music.update("title")
        self.music.update("controls")
        self.assertEqual(self.mixer.load_music.call_count, 1)
        self.music.update("playing")
        self.assertEqual(self.music.current, "playing")

    def test_unavailable_audio_skips_loading(self):
        self.mixer.Mix_QuerySpec.return_value = 0
        with self.assertWarnsRegex(RuntimeWarning, "audio device unavailable"):
            self.music.update("playing")
        self.music.update("playing")
        self.mixer.load_music.assert_not_called()

    def test_playback_failure_does_not_retry_each_frame(self):
        self.mixer.Mix_FadeInMusic.return_value = -1
        with self.assertWarns(RuntimeWarning):
            self.music.update("title")
        self.music.update("title")
        self.mixer.Mix_FadeInMusic.assert_called_once()
        self.assertIsNone(self.music.current)


if __name__ == "__main__":
    unittest.main()
