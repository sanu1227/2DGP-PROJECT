from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from game.front_end import FrontEnd
from game.levels import load_levels
from game.progress import Progress


class ProgressTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "progress.json"
        self.levels = load_levels()

    def load(self):
        return Progress(self.path, self.levels)

    def test_reload_backup_and_continue(self):
        progress = self.load()
        self.assertEqual(progress.checkpoint, 0)
        progress.complete("stage_01", 18)
        progress.complete("stage_02", 32)
        self.assertEqual(self.load().checkpoint, 2)

        self.path.write_text("{", encoding="utf-8")
        recovered = self.load()
        self.assertEqual(recovered.completed, {"stage_01"})
        self.assertEqual(recovered.checkpoint, 1)
        recovered.complete("stage_02", 31)
        self.assertEqual(self.load().checkpoint, 2)

    def test_future_version_is_preserved(self):
        future = '{"version": 3, "completed": []}'
        self.path.write_text(future, encoding="utf-8")
        progress = self.load()
        progress.complete("stage_01", 14)
        self.assertTrue(progress.read_only)
        self.assertEqual(self.path.read_text(encoding="utf-8"), future)

    def test_legacy_clear_retains_unlock_and_later_keeps_best_score(self):
        self.path.write_text('{"version": 1, "completed": ["stage_01"]}', encoding="utf-8")
        progress = self.load()
        self.assertIsNone(progress.records["stage_01"])
        self.assertEqual(progress.checkpoint, 1)
        progress.complete("stage_01", 20)
        progress.complete("stage_01", 17)
        progress.complete("stage_01", 22)
        self.assertEqual(self.load().records["stage_01"], 17)

    def test_title_exposes_only_cleared_rooms(self):
        menu = FrontEnd()
        self.addCleanup(menu.close)
        menu.levels = self.levels
        menu.progress = self.load()
        menu.activate("title")
        self.assertEqual([button.action for button in menu.buttons], ["story", "quit"])
        menu.progress.complete("stage_01", 14)
        self.assertEqual(menu.buttons[0].action, "continue")
        menu.activate("rooms")
        self.assertEqual([button.action for button in menu.buttons], ["room:0", "title"])
        self.assertEqual(menu.activate("room:0"), "room:0")
        self.assertEqual(menu.screen, "playing")
