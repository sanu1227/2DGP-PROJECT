"""Click paths remain ordinary, reversible grid actions even when devices change."""

from copy import deepcopy
from dataclasses import replace
import unittest

from game.model import Game
from game.navigation import ClickNavigator, IsoBoard, find_path
from tests.test_devices import load_stage, plate_stage
from tests.test_game import make_level


class NavigationTests(unittest.TestCase):
    def test_isometric_pick_roundtrip_and_outer_boundaries_for_supported_sizes(self):
        for width in range(6, 13):
            for height in range(6, 13):
                with self.subTest(size=(width, height)):
                    board = IsoBoard(width, height)
                    for y in range(height):
                        for x in range(width):
                            self.assertEqual(board.pick(*board.screen((x, y))), (x, y))
                    self.assertEqual(board.pick(*board.screen((-0.49, 0))), (0, 0))
                    self.assertEqual(board.pick(*board.screen((width - 0.51, height - 1))), (width - 1, height - 1))
                    for outside in ((-0.51, 0), (width - 0.49, 0),
                                    (0, -0.51), (0, height - 0.49)):
                        self.assertIsNone(board.pick(*board.screen(outside)))
                    self.assertEqual(board.pick(*board.screen((2.49, 3.49))), (2, 3))
                    self.assertEqual(board.pick(*board.screen((2.51, 3.49))), (3, 3))

    def test_path_is_shortest_avoids_walls_and_reports_unreachable_targets(self):
        game = Game(make_level([
            "########", "#@.#..E#", "#..#...#", "#..#...#",
            "#......#", "#PT..L.#", "#......#", "########",
        ]))
        before = deepcopy(game.state)
        path = find_path(game, (5, 1))
        self.assertEqual(len(path), 10)  # Four horizontal and six vertical steps around the wall.
        self.assertEqual(path[-1], (5, 1))
        self.assertNotIn(game.state.player, path)
        previous = game.state.player
        for position in path:
            self.assertEqual(sum(abs(a - b) for a, b in zip(previous, position)), 1)
            self.assertTrue(game.walkable(position))
            previous = position
        self.assertEqual(find_path(game, game.state.player), [])
        self.assertIsNone(find_path(game, (3, 1)))
        self.assertIsNone(find_path(game, (-1, 1)))
        game.level = replace(game.level, walls=game.level.walls | {(3, 4), (3, 5), (3, 6)})
        self.assertIsNone(find_path(game, (5, 1)))
        self.assertEqual(game.state, before)
        self.assertEqual(game.history, [])

    def test_held_gate_allows_a_path_out_of_the_occupied_start(self):
        game = Game(load_stage(plate_stage(adjacent=True)))
        self.assertTrue(game.act("right"))
        self.assertTrue(game.act("right"))
        self.assertEqual(game.gate_status((3, 1)), "held")
        self.assertFalse(game.walkable(game.state.player))
        self.assertEqual(find_path(game, (4, 1)), [(4, 1)])
        navigation = ClickNavigator()
        self.assertTrue(navigation.start(game, (4, 1), 0))
        self.assertEqual(navigation.tick(game, 0), "right")
        self.assertEqual(game.gate_status((3, 1)), "closed")
        self.assertFalse(navigation.active)

    def test_path_stops_when_leaving_a_plate_closes_the_next_gate(self):
        game = Game(load_stage(plate_stage()))
        self.assertTrue(game.act("right"))
        navigation = ClickNavigator()
        self.assertTrue(navigation.start(game, (5, 1), 0))
        self.assertEqual(navigation.path, [(3, 1), (4, 1), (5, 1)])
        self.assertEqual(navigation.tick(game, 0), "right")
        self.assertEqual(game.gate_status((4, 1)), "closed")
        stopped, history = deepcopy(game.state), deepcopy(game.history)
        self.assertIsNone(navigation.tick(game, 0.18))
        self.assertFalse(navigation.active)
        self.assertEqual(navigation.path, [])
        self.assertEqual(game.state, stopped)
        self.assertEqual(game.history, history)

    def test_current_cell_cancel_and_invalid_retarget_do_not_consume_turns(self):
        game = Game(make_level(["########", "#@P.TLE#", "#......#", "#......#", "#......#", "#......#", "#......#", "########"]))
        initial = deepcopy(game.state)
        navigation = ClickNavigator()
        self.assertTrue(navigation.start(game, (4, 1), 0))
        self.assertTrue(navigation.active)
        self.assertTrue(navigation.start(game, game.state.player, 0))
        self.assertFalse(navigation.active)
        self.assertIsNone(navigation.tick(game, 100))
        self.assertTrue(navigation.start(game, (4, 1), 0))
        navigation.cancel()
        self.assertFalse(navigation.active)
        self.assertEqual(navigation.path, [])
        self.assertIsNone(navigation.target)
        self.assertTrue(navigation.start(game, (4, 1), 0))
        self.assertFalse(navigation.start(game, (0, 0), 0))
        self.assertFalse(navigation.active)
        self.assertEqual(game.state, initial)
        self.assertEqual(game.history, [])

    def test_ready_time_and_late_frames_never_batch_multiple_actions(self):
        game = Game(make_level(["########", "#@P.TLE#", "#......#", "#......#", "#......#", "#......#", "#......#", "########"]))
        navigation = ClickNavigator()
        self.assertTrue(navigation.start(game, (4, 1), now=1, ready_at=2))
        self.assertIsNone(navigation.tick(game, 1.99))
        self.assertEqual(game.state.moves, 0)
        self.assertEqual(navigation.tick(game, 2), "right")
        self.assertEqual(game.state.moves, 1)
        self.assertEqual(navigation.tick(game, 100), "right")
        self.assertEqual(game.state.moves, 2)
        self.assertIsNone(navigation.tick(game, 100))
        self.assertEqual(navigation.tick(game, 100.18), "right")
        self.assertEqual(game.state.moves, 3)
        self.assertFalse(navigation.active)

    def test_clear_on_an_intermediate_tile_cancels_the_remaining_path(self):
        game = Game(make_level([
            "########", "#@P.TL.#", "######.#", "#...E..#",
            "#......#", "#......#", "#......#", "########",
        ]))
        for action in "right interact right right interact right interact right down down left".split():
            self.assertTrue(game.act(action), game.message)
        self.assertEqual(game.state.player, (5, 3))
        navigation = ClickNavigator()
        self.assertTrue(navigation.start(game, (3, 3), 0))
        self.assertEqual(navigation.path, [(4, 3), (3, 3)])
        self.assertEqual(navigation.tick(game, 0), "left")
        self.assertTrue(game.state.cleared)
        self.assertEqual(game.state.player, game.level.exit)
        cleared, history = deepcopy(game.state), deepcopy(game.history)
        self.assertFalse(navigation.active)
        self.assertEqual(navigation.path, [])
        self.assertIsNone(navigation.tick(game, 10))
        self.assertEqual(game.state, cleared)
        self.assertEqual(game.history, history)


if __name__ == "__main__":
    unittest.main()
