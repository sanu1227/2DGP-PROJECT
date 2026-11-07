"""Scenery remains deterministic and cannot leak atlas tint into game objects."""

from ctypes import POINTER, c_ubyte, cast
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from game.scenery import draw_scars, draw_tinted, floor_style, wall_style


class SceneryTests(unittest.TestCase):
    def test_styles_and_scars_are_stable_and_stay_inside_floor(self):
        floors = set()
        rubble = 0
        fake = ModuleType("pico2d.pico2d")
        package = ModuleType("pico2d")
        package.pico2d = fake
        strokes = []
        fake.draw_line = lambda *args: strokes.append(args)
        with patch.dict(sys.modules, {"pico2d": package, "pico2d.pico2d": fake}):
            for y in range(12):
                for x in range(12):
                    pos = (x, y)
                    floor, tint = floor_style(pos)
                    floors.add(floor)
                    self.assertEqual((floor, tint), floor_style(pos))
                    self.assertTrue(all(0 <= channel <= 255 for channel in tint))
                    wall, tint = wall_style(pos)
                    self.assertEqual((wall, tint), wall_style(pos))
                    self.assertIn(wall, {"wall_low", "rubble"})
                    rubble += wall == "rubble"
                    for near_trap in (False, True):
                        sprite, tint = floor_style(pos, near_trap)
                        self.assertTrue(all(0 <= channel <= 255 for channel in tint))
                        if near_trap:
                            self.assertIn(sprite, {"floor_cracked", "floor_scuffed"})
                        strokes.clear()
                        draw_scars(pos, 200, 100, 1.0, near_trap)
                        first = list(strokes)
                        self.assertLessEqual(len(first), 10)
                        for x1, y1, x2, y2, *_ in first:
                            for px, py in ((x1, y1), (x2, y2)):
                                self.assertLessEqual(abs(px - 200) / 112 + abs(py - 100) / 56, 1)
                        strokes.clear()
                        draw_scars(pos, 200, 100, 1.0, near_trap)
                        self.assertEqual(first, strokes)
        self.assertEqual(floors, {"floor_plain", "floor_cracked", "floor_scuffed", "floor_moss"})
        self.assertGreaterEqual(rubble, 30)
        self.assertLessEqual(rubble, 57)

    def test_shared_atlas_tint_is_restored_after_draw_and_failure(self):
        fake = ModuleType("pico2d.pico2d")
        package = ModuleType("pico2d")
        package.pico2d = fake
        texture = object()
        original = (219, 201, 187)
        color = list(original)
        observed = []

        def get_color(actual, red, green, blue):
            self.assertIs(actual, texture)
            for pointer, value in zip((red, green, blue), color):
                cast(pointer, POINTER(c_ubyte)).contents.value = value
            return 0

        def set_color(actual, red, green, blue):
            self.assertIs(actual, texture)
            color[:] = (red, green, blue)
            return 0

        fake.SDL_GetTextureColorMod = get_color
        fake.SDL_SetTextureColorMod = set_color
        art = SimpleNamespace(
            manifest={"sprites": {"floor_cracked": {"atlas": "environment"}}},
            atlases={"environment": SimpleNamespace(texture=texture)},
        )
        with patch.dict(sys.modules, {"pico2d": package, "pico2d.pico2d": fake}):
            for fail in (False, True):
                with self.subTest(draw_fails=fail):
                    def draw(*args):
                        observed.append((args, tuple(color)))
                        if fail:
                            raise ValueError("draw failed")

                    art.draw = draw
                    if fail:
                        with self.assertRaisesRegex(ValueError, "draw failed"):
                            draw_tinted(art, "floor_cracked", 100, 200, 0.5, (170, 160, 150))
                    else:
                        draw_tinted(art, "floor_cracked", 100, 200, 0.5, (170, 160, 150))
                    self.assertEqual(tuple(color), original)
                    self.assertEqual(observed[-1], (("floor_cracked", 100, 200, 0.5), (170, 160, 150)))


if __name__ == "__main__":
    unittest.main()
