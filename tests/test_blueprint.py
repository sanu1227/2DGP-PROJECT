"""방의 실제 풀이 중 외부 PNG 저장과 되돌리기를 검증한다."""

import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from game.blueprint_editor import BlueprintEditor, paper_point
from game.blueprint_rooms import blueprint_rooms
from game.levels import load_levels
from game.model import Game
from tests.solutions import SOLUTIONS


class BlueprintTests(unittest.TestCase):
    def setUp(self):
        self.levels = blueprint_rooms(load_levels())
        self.editor = BlueprintEditor()
        self.addCleanup(self.editor.close)
        self.now = 0

    def play(self, game, start, end):
        for action in SOLUTIONS[game.level.id][start:end]:
            self.assertTrue(game.act(action), game.message)

    def open(self, game):
        with patch("game.blueprint_editor.launch_paint") as launch:
            self.editor.open(game)
            launch.assert_called_once_with(self.editor.path)

    def save(self, game, edits):
        path = self.editor.path
        with Image.open(path) as original:
            paper = original.convert("RGB")
        for index, color in edits:
            points = tuple(map(paper_point, game.level.circuits[index - 1].gap))
            ImageDraw.Draw(paper).line(points, fill=color, width=5)
        paper.save(path)
        self.now += 1
        self.editor.update(game, self.now)
        self.editor.update(game, self.now + .25)

    def test_workshop_requires_the_wiring_then_the_lever(self):
        game = Game(self.levels[0])
        self.assertIsNotNone(game.blueprint_blocker())
        self.play(game, 0, 9)
        self.assertFalse(game.act("interact"))
        self.open(game)
        self.save(game, [(1, "black")])
        self.assertEqual(game.state.circuit, 1)
        self.assertFalse(game.state.active)
        self.assertEqual(game.state.moves, 9)
        self.assertTrue(game.undo())
        self.assertFalse(game.act("interact"))
        self.editor.reset()
        self.open(game)
        self.save(game, [(1, "black")])
        self.play(game, 9, None)
        self.assertTrue(game.state.cleared)

    def test_sewer_keeps_wiring_on_invalid_save_and_reroutes_on_valid_save(self):
        game = Game(self.levels[4])
        warehouse, exit_gate = (circuit.path[-1] for circuit in game.level.circuits)
        self.play(game, 0, 6)
        self.assertEqual(game.gate_status(warehouse), "closed")
        self.open(game)
        self.save(game, [(1, "black")])
        self.assertEqual(game.gate_status(warehouse), "open")
        self.assertEqual(game.gate_status(exit_gate), "closed")
        self.save(game, [(2, "black")])
        self.assertEqual(game.state.circuit, 1)
        self.assertIn("도선은 하나", self.editor.notice)
        self.play(game, 6, 62)
        self.assertEqual(game.gate_status(exit_gate), "closed")
        self.save(game, [(1, "white")])
        self.assertEqual(game.gate_status(exit_gate), "open")
        self.assertEqual(game.gate_status(warehouse), "closed")
        self.play(game, 62, None)
        self.assertTrue(game.state.cleared)
        self.assertEqual(game.state.moves, 64)
