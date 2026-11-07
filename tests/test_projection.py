"""The front-facing board keeps logical directions aligned with screen axes."""

import unittest

from game.model import DIRECTIONS
from game.projection import BoardProjection


class ProjectionTests(unittest.TestCase):
    def test_logical_directions_move_on_exactly_one_matching_screen_axis(self):
        for width, height in ((8, 8), (8, 12), (12, 8), (12, 12)):
            projection = BoardProjection(width, height)
            origin = projection.screen((3, 3))
            expected = {"up": (0, projection.cell_height),
                        "down": (0, -projection.cell_height),
                        "left": (-projection.cell_width, 0),
                        "right": (projection.cell_width, 0)}
            for action, (dx, dy) in DIRECTIONS.items():
                with self.subTest(size=(width, height), action=action):
                    destination = projection.screen((3 + dx, 3 + dy))
                    self.assertEqual((destination[0] - origin[0], destination[1] - origin[1]), expected[action])

    def test_supported_rectangular_boards_fit_and_adjacent_cells_share_edges(self):
        for width in range(8, 13):
            for height in range(8, 13):
                with self.subTest(size=(width, height)):
                    projection = BoardProjection(width, height)
                    left, _, _, top = projection.bounds((0, 0))
                    _, bottom, right, _ = projection.bounds((width - 1, height - 1))
                    self.assertGreaterEqual(left, 64)
                    self.assertLessEqual(right, 1216)
                    self.assertGreaterEqual(bottom, 174)
                    self.assertLessEqual(top, 702)
                    self.assertEqual((left + right) / 2, 640)
                    self.assertEqual((bottom + top) / 2, 438)
                    self.assertEqual(right - left, width * projection.cell_width)
                    self.assertEqual(top - bottom, height * projection.cell_height)
                    for y in range(height):
                        for x in range(width):
                            cell = projection.bounds((x, y))
                            if x + 1 < width:
                                self.assertEqual(cell[2], projection.bounds((x + 1, y))[0])
                            if y + 1 < height:
                                self.assertEqual(cell[1], projection.bounds((x, y + 1))[3])
                    inset = projection.bounds((0, 0), inset=2)
                    full = projection.bounds((0, 0))
                    self.assertEqual(inset, (full[0] + 2, full[1] + 2, full[2] - 2, full[3] - 2))

    def test_fractional_positions_preserve_animation_interpolation_and_center(self):
        projection = BoardProjection(12, 8)
        self.assertEqual(projection.screen((5.5, 3.5)), (640, 438))
        start, end = (1, 1), (9, 6)
        screen_start, screen_end = projection.screen(start), projection.screen(end)
        for progress in (0, 0.25, 0.5, 0.75, 1):
            with self.subTest(progress=progress):
                logical = tuple(a + (b - a) * progress for a, b in zip(start, end))
                expected = tuple(a + (b - a) * progress for a, b in zip(screen_start, screen_end))
                self.assertEqual(projection.screen(logical), expected)

    def test_isometric_ground_corners_and_neighbor_vectors_map_to_rectangle(self):
        projection = BoardProjection(12, 12)
        center_x, center_y = projection.screen((4, 6))
        left, bottom, right, top = projection.bounds((4, 6))
        corners = (((0, 56), (left, top)), ((112, 0), (right, top)),
                   ((0, -56), (right, bottom)), ((-112, 0), (left, bottom)))
        for source, expected in corners:
            with self.subTest(source=source):
                dx, dy = projection.ground_offset(*source)
                self.assertEqual((center_x + dx, center_y + dy), expected)
        self.assertEqual(projection.ground_offset(0, 0), (0, 0))
        self.assertEqual(projection.ground_offset(112, -56), (projection.cell_width, 0))
        self.assertEqual(projection.ground_offset(-112, -56), (0, -projection.cell_height))


if __name__ == "__main__":
    unittest.main()
