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
