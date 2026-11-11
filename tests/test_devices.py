"""Device changes belong to the same reversible action as the player's input."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from game.levels import load_levels
from game.model import Game


def plate_stage(adjacent=False):
    return {
        "id": "plate_room", "title": "발판 검증", "hint": "부품으로 문을 여세요.",
        "map": [
            "########", "#@FG..E#" if adjacent else "#@F.G.E#",
            "#P..T.L#", "#......#", "#......#", "#......#",
            "#......#", "########",
        ],
        "plate_links": [{"id": "P1", "plate": [2, 1], "gate": [3 if adjacent else 4, 1]}],
    }


def load_stage(stage):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "devices.json"
        path.write_text(json.dumps({"stages": [stage]}), encoding="utf-8")
        return load_levels(path)[0]


def chute_stage(outlet="O"):
    stage = {
        "id": "chute_room", "title": "투입구 검증", "hint": "뼈를 전송하세요.",
        "map": [
            "########", "#@C.." + outlet + "E#", "#BP.TL.#", "#B.A.S.#",
            "#...G..#" if outlet == "F" else "#......#",
            "#......#", "#......#", "########",
        ],
        "chute_links": [{"id": "C1", "inlet": [2, 1], "outlet": [5, 1]}],
    }
    if outlet == "F":
        stage["plate_links"] = [{"id": "P1", "plate": [5, 1], "gate": [4, 4]}]
    return stage


def belt_stage(belts=None):
    rows = [list(row) for row in (
        "########", "#@P..LE#", "#......#", "#......#",
        "#....T.#", "#BBAS..#", "#......#", "########",
    )]
    for (x, y), glyph in (belts or {(3, 3): ">", (4, 3): ">"}).items():
        rows[y][x] = glyph
    return {"id": "belt_room", "title": "벨트 검증", "hint": "끝까지 자동 운반합니다.",
            "map": ["".join(row) for row in rows]}


class ContextDropTests(unittest.TestCase):
    def test_interact_drops_on_supported_surfaces_with_matching_hint_and_undo(self):
        cases = (
            (plate_stage(), (3, 2), "part", (3, 2)),
            (plate_stage(), (2, 1), "part", (2, 1)),
            (plate_stage(), (4, 1), "part", (4, 1)),
            (chute_stage(), (5, 1), "bone", (5, 1)),
            (belt_stage(), (3, 3), "part", (5, 3)),
        )
        for stage, position, kind, destination in cases:
            with self.subTest(position=position, stage=stage["id"]):
                game = Game(load_stage(stage))
                source = next(pos for pos, item in game.state.items.items() if item == kind)
                game.state.carrying = game.state.items.pop(source)
                game.state.player = position
                before = deepcopy(game.state)
                self.assertTrue(game.can_interact())
                self.assertIn("내려놓기", game.context_action())
                self.assertTrue(game.act("interact"))
                self.assertIsNone(game.state.carrying)
                self.assertEqual(game.state.items[destination], kind)
                self.assertEqual(game.state.moves, before.moves + 1)
                self.assertEqual(len(game.history), 1)
                self.assertTrue(game.undo())
                self.assertEqual(game.state, before)

    def test_unavailable_device_actions_never_fall_back_to_drop(self):
        for position, kind in (((2, 1), "part"), ((4, 2), "bone"), ((5, 2), "part"),
                               ((3, 3), "part"), ((5, 3), "part"), ((6, 1), "part"),
                               ((1, 2), "part")):
            with self.subTest(position=position):
                game = Game(load_stage(chute_stage()))
                source = next(pos for pos, item in game.state.items.items() if item == kind)
                game.state.carrying = game.state.items.pop(source)
                game.state.player = position
                before = deepcopy(game.state)
                self.assertFalse(game.can_interact())
                self.assertFalse(game.act("interact"))
                self.assertEqual(game.state, before)
                self.assertEqual(game.history, [])


class PlateTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_stage(plate_stage()))

    def act(self, *actions):
        for action in actions:
            previous = deepcopy(self.game.state)
            count = len(self.game.history)
            self.assertTrue(self.game.act(action), (action, self.game.message))
            self.assertEqual(self.game.history[-1], previous)
            self.assertEqual(len(self.game.history), count + 1)
            self.assertEqual(self.game.state.moves, previous.moves + 1)
            parts = list(self.game.state.items.values()).count("part")
            parts += int(self.game.state.carrying == "part") + len(self.game.state.installed)
            self.assertEqual(parts, 1)

    def rejected(self, action):
        previous, history = deepcopy(self.game.state), deepcopy(self.game.history)
        self.assertFalse(self.game.act(action))
        self.assertEqual(self.game.state, previous)
        self.assertEqual(self.game.history, history)

    def test_player_pressure_and_release_are_restored_by_undo(self):
        self.assertEqual(self.game.gate_status((4, 1)), "closed")
        self.assertFalse(self.game.walkable((4, 1)))
        self.act("right")
        pressed = deepcopy(self.game.state)
        self.assertTrue(self.game.plate_pressed((2, 1)))
        self.assertEqual(self.game.gate_status((4, 1)), "open")
        self.act("right")
        self.assertFalse(self.game.plate_pressed((2, 1)))
        self.assertEqual(self.game.gate_status((4, 1)), "closed")
        self.rejected("right")
        self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, pressed)
        self.assertEqual(self.game.gate_status((4, 1)), "open")

    def test_dropped_part_keeps_gate_open_until_retrieved(self):
        self.act("down", "interact", "up", "right", "drop", "right", "right", "right")
        self.assertEqual(self.game.state.player, (5, 1))
        self.assertEqual(self.game.state.items[(2, 1)], "part")
        self.assertEqual(self.game.gate_status((4, 1)), "open")
        self.act("left", "left", "left", "interact")
        self.assertEqual(self.game.state.carrying, "part")
        self.assertEqual(self.game.gate_status((4, 1)), "open")  # Player still weighs on it.
        self.act("right")
        self.assertEqual(self.game.gate_status((4, 1)), "closed")
        self.rejected("right")
        self.assertTrue(self.game.undo())
        self.assertTrue(self.game.undo())
        self.assertIsNone(self.game.state.carrying)
        self.assertEqual(self.game.state.items[(2, 1)], "part")
        self.assertEqual(self.game.gate_status((4, 1)), "open")
        self.game.restart()
        self.assertEqual(self.game.gate_status((4, 1)), "closed")
        self.assertEqual(self.game.history, [])

    def test_gate_waits_for_occupant_without_allowing_reentry(self):
        self.game = Game(load_stage(plate_stage(adjacent=True)))
        self.act("right", "right")
        held = deepcopy(self.game.state)
        self.assertEqual(self.game.gate_status((3, 1)), "held")
        self.assertFalse(self.game.walkable((3, 1)))
        self.act("right")
        self.assertEqual(self.game.gate_status((3, 1)), "closed")
        self.rejected("left")
        self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, held)
        self.assertEqual(self.game.gate_status((3, 1)), "held")

    def test_item_in_gate_is_preserved_and_can_be_picked_up_after_reopening(self):
        self.game = Game(load_stage(plate_stage(adjacent=True)))
        self.act("down", "interact", "up", "right", "right", "drop", "right")
        self.assertEqual(self.game.gate_status((3, 1)), "held")
        self.assertEqual(self.game.state.items[(3, 1)], "part")
        self.rejected("left")
        self.act("down", "left", "left", "up")
        self.assertEqual(self.game.gate_status((3, 1)), "open")
        self.act("right", "interact", "right")
        self.assertEqual(self.game.state.carrying, "part")
        self.assertEqual(self.game.gate_status((3, 1)), "closed")


class DeviceLevelTests(unittest.TestCase):
    def test_plate_links_cover_real_endpoints_once_with_valid_coordinates(self):
        valid = plate_stage()
        level = load_stage(valid)
        self.assertEqual(level.plates, {(2, 1)})
        self.assertEqual(level.gates, {(4, 1): (2, 1)})
        self.assertEqual(level.device_labels[(2, 1)], "P1")
        self.assertEqual(level.device_labels[(4, 1)], "P1")

        invalid = []
        missing = deepcopy(valid)
        del missing["plate_links"]
        invalid.append(missing)
        for links in ([], "P1", [None], [valid["plate_links"][0]] * 2):
            invalid.append(dict(valid, plate_links=links))
        for field, value in (("id", ""), ("plate", [True, 1]), ("plate", [2]),
                             ("plate", [2, "1"]), ("plate", [99, 1]),
                             ("plate", [1, 1]), ("gate", [5, 1])):
            broken = deepcopy(valid)
            broken["plate_links"][0][field] = value
            invalid.append(broken)
        two_links = deepcopy(valid)
        two_links["map"][3] = "#.F.G..#"
        two_links["plate_links"].append({"id": "P1", "plate": [2, 3], "gate": [4, 3]})
        invalid.append(two_links)
        for stage in invalid:
            with self.subTest(links=stage.get("plate_links")):
                with self.assertRaises(ValueError):
                    load_stage(stage)

    def test_chute_links_reject_missing_or_unsafe_endpoints_and_shared_ids(self):
        for outlet in ("O", ".", "F"):
            with self.subTest(outlet=outlet):
                level = load_stage(chute_stage(outlet))
                self.assertEqual(level.chutes, {(2, 1): (5, 1)})
        invalid = []
        missing = chute_stage()
        del missing["chute_links"]
        invalid.append(missing)
        for field, position in (("inlet", [1, 1]), ("outlet", [2, 1]),
                                ("outlet", [3, 3]), ("outlet", [6, 1]),
                                ("outlet", [0, 1])):
            broken = chute_stage()
            broken["chute_links"][0][field] = position
            invalid.append(broken)
        unlinked_outlet = chute_stage()
        unlinked_outlet["map"][4] = "#.O....#"
        invalid.append(unlinked_outlet)
        shared_outlet = chute_stage()
        shared_outlet["map"][4] = "#.C....#"
        shared_outlet["chute_links"].append({"id": "C2", "inlet": [2, 4], "outlet": [5, 1]})
        invalid.append(shared_outlet)
        duplicate_id = chute_stage("F")
        duplicate_id["chute_links"][0]["id"] = "P1"
        invalid.append(duplicate_id)
        for stage in invalid:
            with self.subTest(links=stage.get("chute_links")):
                with self.assertRaises(ValueError):
                    load_stage(stage)


class ChuteTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(load_stage(chute_stage()))

    def act(self, *actions):
        for action in actions:
            self.assertTrue(self.game.act(action), (action, self.game.message))

    def rejected(self, action):
        previous, history = deepcopy(self.game.state), deepcopy(self.game.history)
        self.assertFalse(self.game.act(action))
        self.assertEqual(self.game.state, previous)
        self.assertEqual(self.game.history, history)

    def test_bone_transfer_and_remote_plate_pressure_form_one_undo(self):
        self.game = Game(load_stage(chute_stage("F")))
        self.act("down", "interact", "up", "right")
        before = deepcopy(self.game.state)
        self.assertEqual(self.game.gate_status((4, 4)), "closed")
        self.act("interact")
        self.assertEqual(self.game.state.items[(5, 1)], "bone")
        self.assertIsNone(self.game.state.carrying)
        self.assertEqual(self.game.state.moves, before.moves + 1)
        self.assertEqual(self.game.gate_status((4, 4)), "open")
        self.assertIn("P1", self.game.level.device_labels[(5, 1)])
        self.assertIn("C1", self.game.level.device_labels[(5, 1)])
        self.assertTrue(self.game.undo())
        self.assertEqual(self.game.state, before)
        self.assertEqual(self.game.gate_status((4, 4)), "closed")

    def test_inlet_rejects_empty_hands_parts_soldiers_and_ordinary_drop(self):
        self.act("right")
        self.rejected("interact")
        self.act("down", "interact", "up")  # Pick up the part below the inlet.
        self.assertEqual(self.game.state.carrying, "part")
        self.rejected("interact")
        self.rejected("drop")

        self.game.restart()
        self.act("down", "interact", "right", "right", "down", "interact",
                 "left", "left", "interact", "right", "right", "interact",
                 "up", "up", "left")
        self.assertEqual(self.game.state.carrying, "soldier")
        self.rejected("interact")

    def test_occupied_outlet_never_consumes_or_overwrites_the_bone(self):
        self.act("down", "interact", "up", "right", "interact")
        self.act("down", "down", "left", "interact", "up", "up", "right")
        self.assertEqual(self.game.state.carrying, "bone")
        self.rejected("interact")
        self.assertEqual(self.game.state.items[(5, 1)], "bone")

        # These defensive states cannot be authored with distinct single-player endpoints.
        del self.game.state.items[(5, 1)]
        self.game.state.soldiers.add((5, 1))
        self.rejected("interact")
        self.game.state.soldiers.clear()
        self.game.level = replace(self.game.level, chutes={(2, 1): (2, 1)})
        self.rejected("interact")

    def test_outlet_allows_retrieval_and_manual_drop(self):
        self.act("down", "interact", "up", "right", "interact", "right", "right", "right",
                 "interact", "drop")
        self.assertEqual(self.game.state.items[(5, 1)], "bone")
        self.assertIsNone(self.game.state.carrying)


class BeltTests(unittest.TestCase):
    def test_all_directions_transport_parts_and_loose_soldiers_one_cell(self):
        directions = {"^": ("up", (3, 2)), "v": ("down", (3, 4)),
                      "<": ("left", (2, 3)), ">": ("right", (4, 3))}
        for glyph, (direction, target) in directions.items():
            for kind in ("part", "soldier"):
                with self.subTest(direction=direction, kind=kind):
                    game = Game(load_stage(belt_stage({(3, 3): glyph})))
                    self.assertEqual(game.level.belts[(3, 3)], direction)
                    if kind == "part":
                        del game.state.items[(2, 1)]
                    else:
                        del game.state.items[(1, 5)], game.state.items[(2, 5)]
                    game.state.items[(3, 3)] = kind
                    self.assertTrue(game.act("down"))
                    self.assertNotIn((3, 3), game.state.items)
                    self.assertEqual(game.state.items[target], kind)
                    self.assertEqual(game.state.player, (1, 2))

    def test_drop_and_full_transport_share_one_undo_and_failed_input_has_no_tick(self):
        game = Game(load_stage(belt_stage()))
        game.state.player = (3, 3)
        game.state.carrying = game.state.items.pop((2, 1))
        before = deepcopy(game.state)
        self.assertTrue(game.act("interact"))
        after_drop = deepcopy(game.state)
        self.assertEqual(game.state.items[(5, 3)], "part")
        self.assertEqual(len(game.belt_steps), 2)
        self.assertEqual(game.belt_steps[0].state.items[(3, 3)], "part")
        self.assertEqual(game.belt_steps[1].state.items[(4, 3)], "part")
        history = deepcopy(game.history)
        self.assertFalse(game.act("interact"))
        self.assertEqual(game.state, after_drop)
        self.assertEqual(game.history, history)
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.items[(5, 3)], "part")
        self.assertTrue(game.undo())
        self.assertEqual(game.state, after_drop)
        self.assertTrue(game.undo())
        self.assertEqual(game.state, before)
        game.restart()
        self.assertEqual(game.state, Game(game.level).state)
        self.assertEqual(game.history, [])

    def test_conflicts_stop_and_queues_follow_vacated_sources_automatically(self):
        cases = (
            ({(3, 3): ">", (5, 3): "<"}, {(3, 3): "part", (5, 3): "soldier"},
             {(3, 3): "part", (5, 3): "soldier"}),
            ({(3, 3): ">", (4, 3): ">"}, {(3, 3): "part", (4, 3): "soldier"},
             {(4, 3): "part", (5, 3): "soldier"}),
        )
        for belts, items, expected in cases:
            for reversed_order in (False, True):
                with self.subTest(belts=belts, reversed_order=reversed_order):
                    game = Game(load_stage(belt_stage(belts)))
                    if reversed_order:
                        game.level = replace(game.level, belts=dict(reversed(list(game.level.belts.items()))))
                    game.state.items = dict(items)
                    before = deepcopy(game.state)
                    self.assertTrue(game.act("down"))
                    self.assertEqual(game.state.items, expected)
                    self.assertTrue(game.undo())
                    self.assertEqual(game.state, before)

    def test_occupied_or_fixed_destination_never_loses_the_transported_item(self):
        target = (4, 3)
        for blocker in ("wall", "player", "item", "soldier", "gate", "trap", "post", "bench", "lever", "inlet", "exit"):
            with self.subTest(blocker=blocker):
                game = Game(load_stage(belt_stage({(3, 3): ">"})))
                game.state.items[(3, 3)] = game.state.items.pop((2, 1))
                # Isolate each occupancy condition without unrelated route setup.
                if blocker == "wall":
                    game.level = replace(game.level, walls=game.level.walls | {target})
                elif blocker == "player":
                    game.state.player = target
                elif blocker == "item":
                    game.state.items[target] = game.state.items.pop((1, 5))
                elif blocker == "soldier":
                    game.level = replace(game.level, posts=frozenset({target}))
                    game.state.soldiers.add(target)
                    del game.state.items[(1, 5)], game.state.items[(2, 5)]
                elif blocker == "gate":
                    game.level = replace(game.level, gates={target: (2, 3)}, plates=frozenset({(2, 3)}))
                elif blocker == "inlet":
                    game.level = replace(game.level, chutes={target: (6, 6)})
                elif blocker == "exit":
                    game.level = replace(game.level, exit=target)
                else:
                    field = {"trap": "traps", "post": "posts", "bench": "benches", "lever": "levers"}[blocker]
                    game.level = replace(game.level, **{field: frozenset({target})})
                items, soldiers, player = deepcopy(game.state.items), set(game.state.soldiers), game.state.player
                # The blocker stays in place while a successful interaction triggers transport.
                game.state.carrying = "part"
                self.assertTrue(game.act("drop"))
                self.assertEqual(game.state.items, items | {player: "part"})
                self.assertEqual(game.state.soldiers, soldiers)
                self.assertEqual(game.state.player, player)

    def test_bones_and_players_are_not_carried_and_bone_drop_is_rejected(self):
        game = Game(load_stage(belt_stage()))
        game.state.player = (3, 3)
        game.state.items[(3, 3)] = game.state.items.pop((1, 5))
        before = deepcopy(game.state)
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.items, before.items)
        self.assertEqual(game.state.player, (3, 4))
        self.assertTrue(game.act("up"))
        self.assertTrue(game.act("interact"))
        carrying = deepcopy(game.state)
        history = deepcopy(game.history)
        self.assertFalse(game.can_interact())
        self.assertFalse(game.act("interact"))
        self.assertFalse(game.act("drop"))
        self.assertEqual(game.state, carrying)
        self.assertEqual(game.history, history)
        game.state.cleared = True
        self.assertFalse(game.act("down"))

    def test_arrival_on_plate_opens_gate_and_resumes_transport_in_the_same_action(self):
        stage = belt_stage({(3, 3): ">", (5, 3): ">"})
        stage["map"][3] = "#..>F>G#"
        stage["plate_links"] = [{"id": "P1", "plate": [4, 3], "gate": [6, 3]}]
        game = Game(load_stage(stage))
        game.state.items = {(3, 3): "part", (5, 3): "soldier"}
        initial = deepcopy(game.state)
        self.assertEqual(game.gate_status((6, 3)), "closed")
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.items, {(4, 3): "part", (6, 3): "soldier"})
        self.assertEqual(game.gate_status((6, 3)), "open")
        self.assertEqual(len(game.belt_steps), 2)
        self.assertEqual(game.belt_steps[1].state.items, {(4, 3): "part", (5, 3): "soldier"})
        after_first = deepcopy(game.state)
        self.assertTrue(game.act("right"))  # A successful ordinary action also advances belts.
        self.assertEqual(game.state.items, {(4, 3): "part", (6, 3): "soldier"})
        self.assertTrue(game.undo())
        self.assertEqual(game.state, after_first)
        self.assertTrue(game.undo())
        self.assertEqual(game.state, initial)
        self.assertEqual(game.gate_status((6, 3)), "closed")

    def test_player_leaving_belt_exit_resumes_transport_without_wait(self):
        game = Game(load_stage(belt_stage()))
        game.state.items[(3, 3)] = game.state.items.pop((2, 1))
        # Entering the first belt exit lets the item approach, then block.
        game.state.player = (5, 2)
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.items[(4, 3)], "part")
        before = deepcopy(game.state)
        self.assertTrue(game.act("up"))
        self.assertEqual(game.state.items[(5, 3)], "part")
        self.assertTrue(game.undo())
        self.assertEqual(game.state, before)

    def test_cyclic_belt_maps_are_rejected_but_bends_are_allowed(self):
        for belts in ({(3, 3): ">", (4, 3): "<"},
                      {(3, 3): ">", (4, 3): "v", (4, 4): "<", (3, 4): "^"}):
            with self.subTest(belts=belts), self.assertRaisesRegex(ValueError, "순환 벨트"):
                load_stage(belt_stage(belts))
        game = Game(load_stage(belt_stage({(3, 3): ">", (4, 3): "v"})))
        game.state.player = (3, 3)
        game.state.carrying = game.state.items.pop((2, 1))
        self.assertTrue(game.act("interact"))
        self.assertEqual(game.state.items[(4, 4)], "part")
        self.assertEqual(len(game.history), 1)


if __name__ == "__main__":
    unittest.main()
