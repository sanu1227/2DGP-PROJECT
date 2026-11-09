"""Low-wall art follows grid topology without changing collision data."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from game.levels import load_levels
from game.scenery import wall_style
from game.themes import low_wall_sprite, scene_for


class WallConnectionTests(unittest.TestCase):
    def setUp(self):
        self.scene = {"connected_low_walls": True, "low_wall_variants": ["wall_low"]}
        self.center = (3, 3)
        self.neighbors = ((3, 2), (4, 3), (3, 4), (2, 3))  # N/E/S/W

    def level_for(self, exposed):
        walls = {self.center} | {p for i, p in enumerate(self.neighbors) if not exposed & (1 << i)}
        return SimpleNamespace(width=7, height=7, walls=frozenset(walls))

    def test_all_sixteen_neighbor_masks_have_correct_direction(self):
        expected = (
            "wall_low_axis_y", "wall_low", "wall_low_axis_y", "wall_low_corner_sw",
            "wall_low", "wall_low", "wall_low_corner_nw", "wall_low_pier",
            "wall_low_axis_y", "wall_low_corner_se", "wall_low_axis_y", "wall_low_pier",
            "wall_low_corner_ne", "wall_low_pier", "wall_low_pier", "wall_low_pier",
        )
        with patch("game.themes.wall_style", return_value=("wall_low", (255, 255, 255))):
            for mask, sprite in enumerate(expected):
                with self.subTest(mask=mask):
                    level = self.level_for(mask)
                    self.assertEqual(low_wall_sprite(self.scene, self.center, level), sprite)

    def test_rubble_ends_visible_wall_but_remains_a_collision_cell(self):
        level = self.level_for(0)
        original = level.walls

        def style(pos):
            return ("wall_low" if pos == (3, 2) else "rubble"), (255, 255, 255)

        with patch("game.themes.wall_style", side_effect=style):
            self.assertEqual(low_wall_sprite(self.scene, self.center, level), "wall_low_pier")
        self.assertEqual(level.walls, original)
        self.assertIn((4, 3), level.walls)

    def test_back_boundary_ignores_rubble_and_handles_outside_neighbors(self):
        level = SimpleNamespace(width=3, height=3,
                                walls=frozenset({(0, 0), (1, 0), (0, 1)}))
        with patch("game.themes.wall_style", return_value=("rubble", (255, 255, 255))):
            self.assertEqual(low_wall_sprite(self.scene, (0, 0), level), "wall_low_corner_se")

    def test_solid_map_without_floor_has_safe_fallback(self):
        level = SimpleNamespace(width=7, height=7,
                                walls=frozenset((x, y) for x in range(7) for y in range(7)))
        with patch("game.themes.wall_style", return_value=("wall_low", (255, 255, 255))):
            self.assertEqual(low_wall_sprite(self.scene, self.center, level), "wall_low")

    def test_actual_rooms_use_existing_assets_and_keep_maps_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        sprites = json.loads((root / "assets/art_v1/manifest.json").read_text(encoding="utf-8"))["sprites"]
        levels = load_levels()
        original = deepcopy(levels)
        used = set()
        for index, level in enumerate(levels):
            scene = scene_for(level)
            for pos in level.walls:
                sprite = low_wall_sprite(scene, pos, level)
                self.assertIn(sprite, sprites)
                self.assertEqual(sprite, low_wall_sprite(scene, pos, level))
                if index:
                    self.assertEqual(sprite, "wall_low")
                elif 0 in pos or wall_style(pos)[0] != "rubble":
                    used.add(sprite)
        self.assertEqual(levels, original)
        self.assertTrue({"wall_low_axis_y", "wall_low_pier",
                         "wall_low_corner_nw", "wall_low_corner_ne",
                         "wall_low_corner_se", "wall_low_corner_sw"} <= used)


if __name__ == "__main__":
    unittest.main()
