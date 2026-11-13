"""새 장치의 실패 경계, 자원 보존, 되돌리기와 실제 배치 완주 검사."""
from copy import deepcopy
from dataclasses import replace
import unittest

from game.levels import DIRECTIONS, load_levels
from game.model import Game
from game.mechanics import trace_magic
from game.navigation import find_path
from tools.draft_routes import WAYPOINTS, replay
from tools.solve_levels import key
from tests.test_devices import load_stage, plate_stage


class GimmickTests(unittest.TestCase):
    def setUp(self):
        self.levels = load_levels()

    def assert_rejected(self, game, action):
        before, history = deepcopy(game.state), deepcopy(game.history)
        self.assertFalse(game.act(action), game.message)
        self.assertEqual(game.state, before)
        self.assertEqual(game.history, history)

    def test_all_draft_routes_complete_and_reverse_every_new_state(self):
        for level in self.levels[3:]:
            with self.subTest(stage=level.id):
                game, actions = replay(level, WAYPOINTS[level.id])
                self.assertTrue(game.state.cleared)
                self.assertEqual(game.repair_percent, 100)
                expected = Game(level)
                snapshots = [deepcopy(expected.state)]
                for action in actions:
                    self.assertTrue(expected.act(action))
                    snapshots.append(deepcopy(expected.state))
                    objects = list(expected.state.items.values()) + [expected.state.carrying]
                    self.assertEqual(objects.count('part') + len(expected.state.installed), len(level.traps))
                    bones = objects.count('bone') + sum(expected.state.bench_bones.values())
                    bones += 2*(objects.count('soldier')+len(expected.state.soldiers)+len(expected.state.workers))
                    self.assertEqual(bones, 2*len(level.posts))
                for before in reversed(snapshots[:-1]):
                    self.assertTrue(game.undo())
                    self.assertEqual(game.state, before)

    def test_mirror_rotation_opens_gate_and_undo_restores_beam(self):
        game=Game(self.levels[4]); game.state.player=(3,2)
        before=deepcopy(game.state)
        self.assertEqual(game.gate_status((5,5)), 'closed')
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status((5,5)), 'open')
        self.assertEqual(trace_magic(game.level,game.state)[1], {(3,4)})
        self.assertNotEqual(key(before), key(game.state))
        game.undo(); self.assertEqual(game.state,before)
        game.state.carrying='part'; self.assert_rejected(game,'interact')

    def test_mirror_reflects_all_four_incident_directions(self):
        base=self.levels[4]
        center=(3,3)
        for direction,(dx,dy) in DIRECTIONS.items():
            for turned in (False,True):
                outgoing=(dy,dx) if turned else (-dy,-dx)
                receiver=(3+outgoing[0],3+outgoing[1])
                level=replace(base,walls=frozenset(),mirrors=frozenset({center}),
                              sources={(3-dx,3-dy):direction},receivers=frozenset({receiver}))
                game=Game(level)
                game.state.turned_mirrors={center} if turned else set()
                self.assertIn(receiver,trace_magic(level,game.state)[1])

    def test_beam_blockers_and_closed_gate_do_not_create_feedback(self):
        game=Game(self.levels[4]); game.state.turned_mirrors={(3,2)}
        for field in ('rubble','soldiers'):
            getattr(game.state,field).add((3,3))
            self.assertFalse(trace_magic(game.level,game.state)[1])
            getattr(game.state,field).clear()
        game.state.player=(3,3);game.state.items[(3,3)]='bone'
        self.assertEqual(trace_magic(game.level,game.state)[1],{(3,4)})

    def test_closed_mirror_loop_terminates(self):
        level=replace(self.levels[4],walls=frozenset(),receivers=frozenset(),
                      sources={(2,2):'right'}, mirrors=frozenset({(2,2),(4,2),(4,4),(2,4)}))
        game=Game(level);game.state.turned_mirrors={(4,2),(2,4)}
        segments,powered=trace_magic(level,game.state)
        self.assertLessEqual(len(segments),10)
        self.assertFalse(powered)

    def test_water_changes_routes_and_undo_in_one_action(self):
        game=Game(self.levels[5]);game.state.player=(3,4)
        self.assertTrue(game.walkable((5,3)))
        self.assertFalse(game.walkable((5,6)))
        before=deepcopy(game.state);game.act('interact')
        self.assertFalse(game.walkable((5,3)))
        self.assertTrue(game.walkable((5,6)))
        self.assertIsNone(find_path(game,(7,2)))
        self.assertIsNotNone(find_path(game,(7,5)))
        game.undo();self.assertEqual(game.state,before)

    def test_water_rejects_submerging_occupants_without_consuming_action(self):
        for high,cell in ((False,(5,3)),(True,(5,6))):
            for field in ('items','rubble','soldiers','workers'):
                game=Game(self.levels[5]);game.state.player=(3,4);game.state.water_high=high
                if field=='items':game.state.items[cell]='bone'
                else:getattr(game.state,field).add(cell)
                self.assert_rejected(game,'interact')

    def test_water_collision_is_enforced_for_direct_keys_too(self):
        game=Game(self.levels[5]);game.state.player=(4,6)
        self.assert_rejected(game,'right')
        game.state.water_high=True;self.assertTrue(game.act('right'))
        game.state.player=(4,3);self.assert_rejected(game,'right')

    def test_rubble_push_presses_plate_and_undo_restores_gate(self):
        game=Game(self.levels[3]);game.state.player=(3,3)
        before=deepcopy(game.state)
        self.assertEqual(game.gate_status((5,4)),'closed')
        self.assertTrue(game.act('down'))
        self.assertEqual(game.state.player,(3,4))
        self.assertEqual(game.state.rubble,{(3,5)})
        self.assertEqual(game.gate_status((5,4)),'open')
        game.undo();self.assertEqual(game.state,before)

    def test_rubble_rejects_carrying_walls_items_and_devices(self):
        for mode in ('carrying','wall','item','device','rubble'):
            game=Game(self.levels[3]);game.state.player=(3,3)
            if mode=='carrying':game.state.carrying='part'
            elif mode=='wall':game.level=replace(game.level,walls=game.level.walls|{(3,5)})
            elif mode=='item':game.state.items[(3,5)]='bone'
            elif mode=='device':game.level=replace(game.level,mirrors=frozenset({(3,5)}))
            else:game.state.rubble.add((3,5))
            self.assert_rejected(game,'down')

    def test_click_navigation_never_silently_pushes_rubble(self):
        game=Game(self.levels[3])
        self.assertIsNone(find_path(game,(7,2)))
        self.assertIsNone(find_path(game,(3,4)))

    def test_helper_assignment_recall_progress_and_gate(self):
        game=Game(self.levels[6]);game.state.player=(5,4);game.state.carrying='soldier'
        game.state.items={p:k for p,k in game.state.items.items() if k!='bone'}
        progress=game.repair_percent;before=deepcopy(game.state)
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status((6,4)),'open')
        self.assertEqual(game.repair_percent,progress)
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status((6,4)),'closed')
        self.assertEqual(game.state.carrying,'soldier')
        game.undo();game.undo();self.assertEqual(game.state,before)

    def test_helper_rejects_wrong_item_and_full_hands(self):
        game=Game(self.levels[6]);game.state.player=(5,4)
        for item in (None,'bone','part'):
            game.state.carrying=item;self.assert_rejected(game,'interact')
        game.state.workers.add((5,4));game.state.carrying='part'
        self.assert_rejected(game,'interact')

    def test_schema_rejects_retired_belt_and_unlinked_new_devices(self):
        for glyph in ('>','<','^','v','M','Q','Y','V','W','H','J'):
            raw=plate_stage();row=list(raw['map'][3]);row[3]=glyph;raw['map'][3]=''.join(row)
            with self.subTest(glyph=glyph),self.assertRaises(ValueError):load_stage(raw)

    def test_new_state_fields_are_in_solver_key(self):
        game=Game(self.levels[7]);base=key(game.state)
        for field in ('turned_mirrors','workers','rubble'):
            state=deepcopy(game.state);getattr(state,field).add((1,1))
            self.assertNotEqual(base,key(state))
        game.state.water_high=True;self.assertNotEqual(base,key(game.state))


if __name__=='__main__':unittest.main()
