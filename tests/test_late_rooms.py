"""보물창고의 추 재사용과 왕좌실의 최종 봉쇄 순서를 검사한다."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from game.levels import load_levels
from game.model import DIRECTIONS, Game
from game.navigation import find_path, IsoBoard
from game.themes import scene_for, themed_floor
from tests.solutions import SOLUTIONS


class LateRoomTests(unittest.TestCase):
    def go(self, game, target):
        path = find_path(game, target)
        self.assertIsNotNone(path, target)
        reverse = {delta: action for action, delta in DIRECTIONS.items()}
        for cell in path:
            x, y = game.state.player
            self.assertTrue(game.act(reverse[(cell[0] - x, cell[1] - y)]), game.message)

    def test_two_gates_change_independently_and_every_action_is_reversible(self):
        for level in load_levels()[6:]:
            with self.subTest(stage=level.id):
                game = Game(level)
                snapshots = [deepcopy(game.state)]
                observed = set()
                for action in SOLUTIONS[level.id]:
                    self.assertTrue(game.act(action), game.message)
                    snapshots.append(deepcopy(game.state))
                    observed.add(tuple(game.gate_status(gate) for gate in level.gates))
                self.assertTrue(game.state.cleared)
                self.assertEqual(game.remaining_actions, 2)
                self.assertIn(("closed", "closed"), observed)
                self.assertIn(("open", "closed"), observed)
                self.assertTrue(any(second == "open" for _, second in observed))
                for expected in reversed(snapshots[:-1]):
                    self.assertTrue(game.undo())
                    self.assertEqual(game.state, expected)
                self.assertFalse(game.history)
                self.assertEqual(game.state, Game(level).state)

    def test_boss_guard_deployed_early_seals_away_the_unfinished_part(self):
        game = Game(load_levels()[7])
        for target in ((2, 9), (3, 9), (5, 8), (5, 7), (6, 7), (6, 3), (2, 3), (5, 7)):
            self.go(game, target)
            self.assertTrue(game.act("interact"), game.message)
        self.assertEqual(game.state.carrying, "soldier")
        self.assertEqual(game.state.items[(9, 2)], "part")
        self.go(game, (6, 5))
        self.assertTrue(game.act("interact"))
        deployed = deepcopy(game.state)
        self.assertTrue(game.act("down"))
        self.assertIsNone(find_path(game, (9, 2)))
        self.assertFalse(game.state.cleared)
        self.assertTrue(game.undo())
        self.assertEqual(game.state, deployed)
        self.assertTrue(game.undo())
        self.assertIsNotNone(find_path(game, (9, 2)))

    def test_new_themes_and_twelve_cell_boards_resolve_real_assets(self):
        root = Path(__file__).resolve().parents[1]
        for level in load_levels()[6:]:
            scene = scene_for(level)
            pack = scene["packs"][0]
            manifest = json.loads((root / "assets/map_pack_v1" / pack / "manifest.json").read_text(encoding="utf-8"))
            validation = json.loads((root / "assets/map_pack_v1" / pack / "validation.json").read_text(encoding="utf-8"))
            self.assertEqual(validation["count"], 16)
            self.assertTrue(validation["source_cells_unclipped"] and validation["output_padding"])
            for decoration in scene["decorations"]:
                self.assertIn(decoration["sprite"], manifest["sprites"])
            projection = IsoBoard(level.width, level.height)
            for y in range(level.height):
                for x in range(level.width):
                    pos = (x, y)
                    self.assertEqual(projection.pick(*projection.screen(pos)), pos)
                    self.assertIn(themed_floor(scene, pos)[0], manifest["sprites"])


if __name__ == "__main__":
    unittest.main()
