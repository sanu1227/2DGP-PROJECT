"""새 장치의 실패 경계, 자원 보존, 되돌리기와 실제 배치 완주 검사."""
from copy import deepcopy
from dataclasses import replace
from itertools import product
import unittest

from game.levels import DIRECTIONS, load_levels
from game.model import Game
from game.mechanics import trace_magic
from game.navigation import find_path
from tests.solutions import SOLUTIONS
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

    def test_all_routes_complete_and_reverse_every_new_state(self):
        for level in self.levels[3:]:
            with self.subTest(stage=level.id):
                game, actions = Game(level), SOLUTIONS[level.id]
                for action in actions:
                    self.assertTrue(game.act(action), game.message)
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
        self.assertEqual(game.gate_status(next(iter(game.level.gates))), 'closed')
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status(next(iter(game.level.gates))), 'open')
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

    def test_later_rooms_require_every_reflection_and_undo_each_rotation(self):
        for index, count in ((4, 1), (5, 2), (7, 3)):
            level = self.levels[index]
            mirrors = sorted(level.mirrors)
            self.assertEqual(len(mirrors), count)
            winning = []
            for bits in product((False, True), repeat=count):
                game = Game(level)
                game.state.turned_mirrors = {m for m, bit in zip(mirrors, bits) if bit}
                segments, powered = trace_magic(level, game.state)
                if powered:
                    winning.append(bits)
                    hits = [end for _, end in segments if end in level.mirrors]
                    self.assertEqual(len(hits), count)
                    self.assertEqual(set(hits), set(mirrors))
            self.assertEqual(winning, [(True,) * count], level.id)
            game = Game(level)
            for mirror in mirrors:
                game.state.player = mirror
                before = deepcopy(game.state)
                self.assertTrue(game.act('interact'))
                game.undo()
                self.assertEqual(game.state, before)
                self.assertTrue(game.act('interact'))
            self.assertEqual(trace_magic(level, game.state)[1], set(level.receivers))
            # 도달 경로의 거울 하나를 빼면 수신기가 작동할 수 없다.
            for mirror in mirrors:
                broken = replace(level, mirrors=level.mirrors - {mirror})
                self.assertFalse(trace_magic(broken, game.state)[1])

    def test_retired_water_is_absent_from_levels_state_and_catalog(self):
        from game.device_catalog import CARDS
        from game.tutorial import device_lessons
        self.assertNotIn('water', {card.kind for card in CARDS})
        for level in self.levels:
            self.assertFalse(set(''.join(level.rows)) & set('VWH'))
            self.assertFalse(hasattr(Game(level).state, 'water_high'))
            self.assertNotIn('water', {lesson.kind for lesson in device_lessons(level)})

    def test_rubble_push_presses_plate_and_undo_restores_gate(self):
        game=Game(self.levels[3]);game.state.player=(2,2)
        before=deepcopy(game.state)
        self.assertEqual(game.gate_status(next(iter(game.level.gates))),'closed')
        self.assertTrue(game.act('down'))
        self.assertEqual(game.state.player,(2,3))
        self.assertEqual(game.state.rubble,{(2,4)})
        self.assertEqual(game.gate_status(next(iter(game.level.gates))),'open')
        game.undo();self.assertEqual(game.state,before)

    def test_rubble_rejects_carrying_walls_items_and_devices(self):
        for mode in ('carrying','wall','item','device','rubble'):
            game=Game(self.levels[3]);game.state.player=(2,2)
            if mode=='carrying':game.state.carrying='part'
            elif mode=='wall':game.level=replace(game.level,walls=game.level.walls|{(2,4)})
            elif mode=='item':game.state.items[(2,4)]='bone'
            elif mode=='device':game.level=replace(game.level,mirrors=frozenset({(2,4)}))
            else:game.state.rubble.add((2,4))
            self.assert_rejected(game,'down')

    def test_click_navigation_never_silently_pushes_rubble(self):
        game=Game(self.levels[3])
        self.assertIsNone(find_path(game,next(p for p,k in game.level.initial_items.items() if k=="part")))
        self.assertIsNone(find_path(game,(2,3)))

    def test_helper_assignment_recall_progress_and_gate(self):
        game=Game(self.levels[6]);game.state.player=next(iter(game.level.jobs));game.state.carrying='soldier'
        game.state.items={p:k for p,k in game.state.items.items() if k!='bone'}
        progress=game.repair_percent;before=deepcopy(game.state)
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status(next(iter(game.level.gates))),'open')
        self.assertEqual(game.repair_percent,progress)
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status(next(iter(game.level.gates))),'closed')
        self.assertEqual(game.state.carrying,'soldier')
        game.undo();game.undo();self.assertEqual(game.state,before)

    def test_helper_rejects_wrong_item_and_full_hands(self):
        game=Game(self.levels[6]);game.state.player=next(iter(game.level.jobs))
        for item in (None,'bone','part'):
            game.state.carrying=item;self.assert_rejected(game,'interact')
        game.state.workers.add(next(iter(game.level.jobs)));game.state.carrying='part'
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

    def test_boss_mirror_gate_cannot_be_bypassed_through_the_material_room(self):
        game = Game(self.levels[7])
        job = next(iter(game.level.jobs))
        vault_part = min((p for p, kind in game.level.initial_items.items() if kind == 'part'), key=lambda p: p[1])
        self.assertIsNone(find_path(game, job))
        self.assertIsNone(find_path(game, vault_part))
        for mirror in sorted(game.level.mirrors):
            game.state.player = mirror
            self.assertTrue(game.act('interact'))
        self.assertIsNotNone(find_path(game, job))
        self.assertIsNone(find_path(game, vault_part))
        game.state.player = job
        game.state.carrying = 'soldier'
        self.assertTrue(game.act('interact'))
        self.assertIsNotNone(find_path(game, vault_part))


if __name__=='__main__':unittest.main()
