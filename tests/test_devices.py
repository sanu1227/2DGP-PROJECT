"""Device changes belong to the same reversible action as the player's input."""

from copy import deepcopy
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


if __name__ == "__main__":
    unittest.main()
