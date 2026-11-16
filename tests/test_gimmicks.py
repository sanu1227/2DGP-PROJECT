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

    def test_sewer_rubble_needs_to_be_pushed_off_the_beam(self):
        game = Game(self.levels[4])
        for action in ("down", "push_right", "right"):
            self.assertTrue(game.act(action), game.message)
        gate = next(gate for gate, control in game.level.gates.items() if control in game.level.receivers)
        self.assertTrue(game.act('interact'))
        self.assertEqual(game.gate_status(gate), 'closed')
        self.assertTrue(game.act('down'))  # Along the beam; the receiver stays blocked.
        self.assertEqual(game.gate_status(gate), 'closed')
        self.assertTrue(game.undo())
        self.assertTrue(game.act('left'))
        self.assertTrue(game.act('down'))
        before=deepcopy(game.state)
        self.assertTrue(game.act('right'))  # Park the rubble in the side recess.
        self.assertEqual(game.gate_status(gate), 'open')
        self.assertEqual(trace_magic(game.level,game.state)[1], game.level.receivers)
        self.assertNotEqual(key(before), key(game.state))
        game.undo(); self.assertEqual(game.state,before)
        game.state.player=(3,2)
        game.state.carrying='part'; self.assert_rejected(game,'interact')

    def test_mirror_emits_same_selected_direction_for_each_incident_direction(self):
        center = (3, 3)
        level = replace(self.levels[4], walls=frozenset(), rubble=frozenset(),
                        mirrors=frozenset({center}), receivers=frozenset())
        for direction, (dx, dy) in DIRECTIONS.items():
            source = (3 - 2 * dx, 3 - 2 * dy)
            game = Game(replace(level, sources={source: direction}))
            for rotation, (ox, oy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
                with self.subTest(incoming=direction, rotation=rotation):
                    game.state.mirror_rotations[center] = rotation
                    segments, _ = trace_magic(game.level, game.state)
                    self.assertEqual(segments[2], (center, (3 + ox, 3 + oy)))
                    if (ox, oy) == (-dx, -dy):
                        self.assertEqual(segments[-1][1], source)

    def test_four_rotations_wrap_and_each_undo_restores_orientation(self):
        game = Game(self.levels[4])
        mirror = next(iter(game.level.mirrors))
        game.state.player = mirror
        original = key(game.state)
        states = []
        for expected in (1, 2, 3, 0):
            states.append(deepcopy(game.state))
            self.assertTrue(game.act('interact'))
            self.assertEqual(game.state.mirror_rotations.get(mirror, 0), expected)
        self.assertEqual(game.state.moves, 4)
        self.assertEqual(key(game.state), original)
        for before in reversed(states):
            self.assertTrue(game.undo())
            self.assertEqual(game.state, before)
        game.restart()
        self.assertEqual(game.state.mirror_rotations, {})

    def test_beam_blockers_and_closed_gate_do_not_create_feedback(self):
        game=Game(self.levels[4]); game.state.mirror_rotations={(3,2): 1}
        game.state.movable_mirrors = {(3, 2)}
        for field in ('rubble','soldiers'):
            getattr(game.state,field).add((3,3))
            self.assertFalse(trace_magic(game.level,game.state)[1])
            getattr(game.state,field).clear()
        game.state.player=(3,3);game.state.items[(3,3)]='bone'
        self.assertEqual(trace_magic(game.level,game.state)[1],game.level.receivers)

    def test_closed_mirror_loop_terminates(self):
        level=replace(self.levels[4],walls=frozenset(),receivers=frozenset(),rubble=frozenset(),
                      sources={(1,2):'right'}, mirrors=frozenset({(2,2),(4,2),(4,4),(2,4)}))
        game=Game(level);game.state.mirror_rotations={(2,2): 1, (4,2): 2, (4,4): 3, (2,4): 0}
        segments,powered=trace_magic(level,game.state)
        self.assertEqual(len(segments), 9)
        self.assertFalse(powered)

    def test_later_rooms_require_every_reflection_and_undo_each_rotation(self):
        for index, expected in ((4, (1,)), (7, (1,))):
            count = len(expected)
            level = replace(self.levels[index], rubble=frozenset())
            if level.movable_mirrors:
                level = replace(level, mirrors=frozenset({(3, 2)}), movable_mirrors=frozenset())
            receiver = next(control for gate, control in level.gates.items()
                            if level.device_labels[gate] == 'M1')
            mirrors = sorted(level.mirrors)
            self.assertEqual(len(mirrors), count)
            winning = []
            for rotations in product(range(4), repeat=count):
                game = Game(level)
                game.state.mirror_rotations = dict(zip(mirrors, rotations))
                segments, powered = trace_magic(level, game.state)
                if receiver in powered:
                    winning.append(rotations)
                    hits = [end for _, end in segments if end in level.mirrors]
                    self.assertEqual(len(hits), count)
                    self.assertEqual(set(hits), set(mirrors))
            self.assertEqual(winning, [expected], level.id)
            game = Game(level)
            for mirror, rotation in zip(mirrors, expected):
                game.state.player = mirror
                turns = (rotation - game.state.mirror_rotations.get(mirror, 0)) % 4
                for _ in range(turns):
                    before = deepcopy(game.state)
                    self.assertTrue(game.act('interact'))
                    game.undo()
                    self.assertEqual(game.state, before)
                    self.assertTrue(game.act('interact'))
            self.assertEqual(trace_magic(level, game.state)[1], {receiver})
            # 도달 경로의 거울 하나를 빼면 수신기가 작동할 수 없다.
            for mirror in mirrors:
                broken = replace(level, mirrors=level.mirrors - {mirror})
                self.assertNotIn(receiver, trace_magic(broken, game.state)[1])

    def test_relay_block_alternates_two_gates_and_cannot_leave_its_slots(self):
        level = self.levels[5]
        game = Game(level)
        north, south = sorted(level.gates, key=lambda pos: pos[1])
        before = deepcopy(game.state)
        self.assertEqual(trace_magic(level, game.state)[1], {level.gates[north]})
        self.assertEqual((game.gate_status(north), game.gate_status(south)), ("open", "closed"))
        self.assert_rejected(game, "right")
        for action in ("down", "right", "right", "up", "left"):
            self.assertTrue(game.act(action), game.message)
        self.assertEqual(game.state.rubble, {(2, 3)})
        self.assertEqual(trace_magic(level, game.state)[1], {level.gates[south]})
        self.assertEqual((game.gate_status(north), game.gate_status(south)), ("closed", "open"))
        self.assert_rejected(game, "left")
        for action in ("down", "left", "left", "up", "right"):
            self.assertTrue(game.act(action), game.message)
        self.assertEqual(game.state.rubble, before.rubble)
        self.assertEqual(trace_magic(level, game.state)[1], {level.gates[north]})
        self.assertEqual((game.gate_status(north), game.gate_status(south)), ("open", "closed"))
        self.assertTrue(game.undo())
        self.assertEqual(trace_magic(level, game.state)[1], {level.gates[south]})

    def test_relay_room_requires_staging_the_bone_across_power_modes(self):
        level = self.levels[5]
        game = Game(level)
        lower_bone = max((pos for pos, kind in level.initial_items.items() if kind == 'bone'),
                         key=lambda pos: pos[1])
        bench = next(iter(level.benches))
        picked_up = False
        for action in SOLUTIONS[level.id]:
            pos = game.state.player
            picking = pos == lower_bone and game.state.items.get(pos) == 'bone'
            hauling = picked_up and game.state.carrying == 'bone'
            self.assertTrue(game.act(action), game.message)
            if picking and action == 'interact':
                picked_up = True
                self.assertIsNone(find_path(game, bench))
            if hauling and game.state.items.get(pos) == 'bone':
                self.assertNotEqual(pos, lower_bone)
                break
        else:
            self.fail('남쪽 뼈를 다른 전력 상태로 넘길 임시 보관이 필요합니다.')

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

    def test_prison_requires_open_cells_to_reach_the_armory(self):
        level = self.levels[3]
        game = Game(level)
        armory = next(pos for pos, item in level.initial_items.items() if item == 'part')
        gates = {level.device_labels[gate]: gate for gate in level.gates}
        visited = []
        for action in SOLUTIONS[level.id]:
            self.assertTrue(game.act(action), game.message)
            door = level.device_labels.get(game.state.player)
            if game.state.player in level.gates and door not in visited:
                visited.append(door)
            if door == 'P3' and game.state.player == gates[door] and len(visited) == 3:
                self.assertEqual(visited, ['P1', 'P2', 'P3'])
                self.assertTrue(all(game.gate_status(gate) == 'open' for gate in gates.values()))
                self.assertIn(level.gates[gates['P1']], game.state.rubble)
                for identifier in ('P2', 'P3'):
                    self.assertEqual(game.state.items[level.gates[gates[identifier]]], 'bone')
                self.assertIsNotNone(find_path(game, armory))
                break
        else:
            self.fail('검증 풀이가 무기고 문을 통과하지 않았습니다.')

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

    def test_two_step_recording_starts_on_entry_and_replays_on_later_actions(self):
        game = Game(self.levels[6])
        station = min(game.level.replay_workers)
        spawn = game.level.replay_workers[station]
        gate = next(gate for gate, control in game.level.gates.items() if control == station)
        seals, _ = game.level.echo_links[station]
        game.state.player = (2, 2)
        before = deepcopy(game.state)

        self.assertTrue(game.act("right"))
        self.assertEqual(game.state.recording.origin, station)
        self.assertEqual(game.state.recording.inputs, ())
        self.assertTrue(game.act("up"))
        self.assert_rejected(game, "interact")
        self.assertTrue(game.act("right"))
        self.assertIsNone(game.state.recording)
        self.assertEqual(game.state.player, (4, 1))
        self.assertEqual(game.state.replay_workers[station], spawn)
        self.assertEqual(game.state.echo.remaining, ("up", "right"))
        self.assertEqual(game.gate_status(gate), "closed")

        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.replay_workers[station], seals[gate])
        self.assertEqual(game.gate_status(gate), "open")
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.player, gate)
        self.assertEqual(game.gate_status(gate), "held")
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.replay_workers[station], (2, 1))
        self.assertEqual(game.gate_status(gate), "closed")
        self.assert_rejected(game, "up")
        while game.undo():
            pass
        self.assertEqual(game.state, before)

    def test_treasury_uses_the_first_part_to_open_the_skeleton_locker(self):
        level = self.levels[6]
        game = Game(level)
        gate = next(gate for gate in level.gates if level.device_labels[gate] == "P1")
        soldier = next(pos for pos, kind in level.initial_items.items() if kind == "soldier")
        first_part = min((pos for pos, kind in level.initial_items.items() if kind == "part"), key=lambda pos: pos[1])
        for action in SOLUTIONS[level.id]:
            self.assertTrue(game.act(action), game.message)
            if game.state.player == soldier:
                self.assertNotIn(first_part, game.state.items)
                self.assertEqual(game.state.items[level.gates[gate]], "part")
                self.assertEqual(game.gate_status(gate), "open")
                break
        else:
            self.fail("해골 보관실에 도착하지 못했습니다.")

    def test_schema_rejects_retired_belt_and_unlinked_new_devices(self):
        for glyph in ('>','<','^','v','M','Q','Y','V','W','H','J','U'):
            raw=plate_stage();row=list(raw['map'][3]);row[3]=glyph;raw['map'][3]=''.join(row)
            with self.subTest(glyph=glyph),self.assertRaises(ValueError):load_stage(raw)

    def test_new_state_fields_are_in_solver_key(self):
        game=Game(self.levels[7]);base=key(game.state)
        for rotation in (1, 2, 3):
            state=deepcopy(game.state);state.mirror_rotations[(1,1)]=rotation
            self.assertNotEqual(base,key(state))
        for field in ('workers','rubble'):
            state=deepcopy(game.state);getattr(state,field).add((1,1))
            self.assertNotEqual(base,key(state))
        game.state.player = (1, 3)
        self.assertTrue(game.act('right'))
        recorded = key(game.state)
        state = deepcopy(game.state)
        state.recording = None
        self.assertNotEqual(recorded, key(state))
        state = deepcopy(game.state)
        state.replay_workers[state.player] = state.player
        self.assertNotEqual(recorded, key(state))

if __name__=='__main__':unittest.main()
