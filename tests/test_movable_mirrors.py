"""이동 거울과 차광 잔해가 수신기·문에 미치는 영향을 검사한다."""

from copy import deepcopy
from dataclasses import replace
import unittest

from game.levels import load_levels
from game.mechanics import mirror_cells, trace_magic
from game.model import Game
from game.optics import trace_display_magic
from tools.solve_levels import key


class MovableMirrorTests(unittest.TestCase):
    def setUp(self):
        self.origin, self.aligned = (2, 2), (3, 2)
        self.receiver, self.gate = (3, 5), (4, 4)
        base = load_levels()[4]
        self.level = replace(base, start=(1, 2), walls=frozenset(), posts=frozenset(),
                             mirrors=frozenset({self.origin}), movable_mirrors=frozenset({self.origin}),
                             mirror_directions={self.origin: "down"}, sources={(1, 2): "right"},
                             receivers=frozenset({self.receiver}), gates={self.gate: self.receiver},
                             plates=frozenset(), initial_items={}, rubble=frozenset({(3, 3)}))

    def test_push_aligns_mirror_and_rubble_opens_then_closes_light_path(self):
        game = Game(self.level)
        initial = deepcopy(game.state)
        self.assertTrue(game.act("right"))
        self.assertEqual(mirror_cells(self.level, game.state), {self.aligned})
        self.assertEqual(game.state.mirror_rotations, {self.aligned: 1})
        self.assertEqual(game.gate_status(self.gate), "closed")
        self.assertTrue(game.act("down"))
        self.assertTrue(game.act("right"))
        self.assertEqual(trace_magic(self.level, game.state)[1], {self.receiver})
        self.assertEqual(game.gate_status(self.gate), "open")
        game.state.player = (5, 3)
        self.assertTrue(game.act("left"))
        self.assertEqual(game.gate_status(self.gate), "closed")
        self.assertTrue(game.undo())
        self.assertEqual(game.gate_status(self.gate), "open")
        for _ in range(3):
            self.assertTrue(game.undo())
        self.assertEqual(game.state, initial)
        self.assertTrue(game.act("right"))
        game.restart()
        self.assertEqual(game.state, initial)

    def test_walk_and_rotate_remain_available_and_failed_push_is_atomic(self):
        game = Game(self.level)
        self.assertTrue(game.act("right"))
        self.assertEqual(game.state.player, self.origin)
        self.assertTrue(game.act("interact"))
        self.assertEqual(game.state.mirror_rotations, {self.aligned: 2})
        self.assertTrue(game.act("left"))
        self.assertTrue(game.act("right"))
        before = deepcopy(game.state)
        game.state.carrying = "bone"
        self.assertFalse(game.act("right"))
        self.assertEqual(game.state.carrying, "bone")
        game.state.carrying = None
        self.assertEqual(game.state, before)
        blocked = Game(replace(self.level, plates=frozenset({self.aligned})))
        before = deepcopy(blocked.state)
        self.assertFalse(blocked.act("push_right"))
        self.assertEqual(blocked.state, before)
        self.assertFalse(blocked.history)
        fixed = Game(replace(self.level, movable_mirrors=frozenset()))
        self.assertFalse(fixed.act("push_right"))

    def test_visual_light_waits_for_animated_block_and_mirror_positions(self):
        game = Game(self.level)
        for action in ("push_right", "down", "right"):
            self.assertTrue(game.act(action))
        state = game.state
        self.assertEqual(trace_magic(self.level, state)[1], {self.receiver})
        self.assertFalse(trace_display_magic(self.level, state, {}, mirrors={self.aligned: self.origin})[1])
        self.assertFalse(trace_display_magic(self.level, state, {}, rubble={(3.25, 3)})[1])
        self.assertEqual(trace_display_magic(self.level, state, {}, rubble={(3.75, 3)})[1], {self.receiver})
        other = deepcopy(state)
        other.movable_mirrors = {self.origin}
        self.assertNotEqual(key(state), key(other))
