"""연속 방출과 정지 상태의 규칙 일치. 화면 축척과 독립된 지도 평면에서 검사한다."""

from copy import deepcopy
from dataclasses import replace
from math import dist, hypot
import unittest

from game.levels import load_levels
from game.magic import mirror_output
from game.mechanics import trace_magic
from game.model import Game
from game.optics import TOPDOWN_SOURCE_REACH, trace_display_magic, source_origin
from tests.solutions import SOLUTIONS


class OpticsTests(unittest.TestCase):
    def fixture(self):
        return replace(load_levels()[4], walls=frozenset(), mirrors=frozenset({(3, 3)}),
                       sources={(1, 3): 'right'}, receivers=frozenset(), rubble=frozenset(), posts=frozenset())

    def test_output_is_cardinal_at_each_stop_and_unit_length_during_motion(self):
        self.assertEqual([mirror_output(angle) for angle in range(5)],
                         [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 0)])
        for step in range(401):
            self.assertAlmostEqual(hypot(*mirror_output(step / 100)), 1)

    def test_beam_sweeps_all_the_way_around_without_disappearing(self):
        game = Game(self.fixture())
        previous = None
        for step in range(401):
            rotation = step / 100
            segments, _ = trace_display_magic(game.level, game.state, {(3, 3): rotation})
            self.assertEqual(len(segments), 2)
            self.assertEqual(segments[0][0], source_origin((1, 3), 'right'))
            self.assertEqual(segments[0][1], segments[1][0])
            start, end = segments[1]
            direction = tuple((end[i] - start[i]) / dist(start, end) for i in (0, 1))
            self.assertLess(dist(direction, mirror_output(rotation)), 1e-8)
            if previous is not None:
                self.assertGreater(dist(direction, previous), .01)
                self.assertLess(dist(direction, previous), .03)
            previous = direction

    def test_backtracking_beam_stops_at_source_casing(self):
        game = Game(self.fixture())
        rays, powered = trace_display_magic(game.level, game.state, {(3, 3): 2})
        self.assertEqual(rays[-1], ((3, 3), (1.5, 3)))
        self.assertFalse(powered)

    def test_adjacent_block_cuts_visible_ray_at_surface_from_topdown_nozzle(self):
        level = replace(self.fixture(), mirrors=frozenset(), rubble=frozenset({(2, 3)}))
        rays, powered = trace_display_magic(level, Game(level).state, {}, source_reach=TOPDOWN_SOURCE_REACH)
        self.assertEqual(rays, [((1.275, 3), (1.62, 3))])
        self.assertFalse(powered)

    def test_moving_block_never_leaves_parallel_beams_both_open(self):
        left, right = (2, 1), (3, 5)
        level = replace(self.fixture(), mirrors=frozenset(), sources={(2, 4): "up", (3, 2): "down"},
                        receivers=frozenset({left, right}))
        state = Game(level).state
        for reach in (None, TOPDOWN_SOURCE_REACH):
            for step in range(101):
                x = 2 + step / 100
                _, powered = trace_display_magic(level, state, {}, rubble={(x, 3)}, source_reach=reach)
                expected = {right} if step < 50 else {left} if step > 50 else set()
                self.assertEqual(powered, expected, (reach, x))

    def test_nearest_blocker_and_receiver_stop_the_ray(self):
        level = replace(self.fixture(), mirrors=frozenset(), sources={(1, 3): 'right'}, receivers=frozenset({(6, 3)}))
        for kind in ('walls', 'rubble', 'soldiers'):
            game = Game(replace(level, walls=frozenset({(4, 3)})) if kind == 'walls' else level)
            if kind != 'walls':
                getattr(game.state, kind).add((4, 3))
            rays, powered = trace_display_magic(game.level, game.state, {})
            self.assertFalse(powered)
            self.assertEqual(rays[-1][1], (3.62 if kind == "rubble" else 3.5, 3))
        game = Game(level)
        rays, powered = trace_display_magic(level, game.state, {})
        self.assertEqual(powered, {(6, 3)})
        self.assertAlmostEqual(rays[-1][1][0], 5.78)

    def test_multi_mirror_routes_match_logical_receivers_without_state_mutation(self):
        for level in load_levels():
            if not level.mirrors:
                continue
            game = Game(level)
            for action in SOLUTIONS[level.id]:
                self.assertTrue(game.act(action))
                before = deepcopy(game.state)
                rays, powered = trace_display_magic(level, game.state, game.state.mirror_rotations)
                self.assertEqual(powered, trace_magic(level, game.state)[1])
                self.assertLessEqual(len(rays), 64 * len(level.sources))
                self.assertEqual(game.state, before)

    def test_cycle_and_source_facing_outside_board_terminate(self):
        level = replace(self.fixture(), sources={(1, 2): 'right'},
                        mirrors=frozenset({(2, 2), (4, 2), (4, 4), (2, 4)}))
        game = Game(level)
        rays, _ = trace_display_magic(level, game.state, {(2, 2): 1, (4, 2): 2, (4, 4): 3, (2, 4): 0})
        self.assertEqual(len(rays), 5)
        level = replace(level, sources={(0, 0): 'left'})
        self.assertEqual(trace_display_magic(level, Game(level).state, {}), ([], set()))


if __name__ == '__main__':
    unittest.main()
