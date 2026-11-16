"""보물창고의 추 재사용과 왕좌실의 최종 봉쇄 순서를 검사한다."""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from game.levels import load_levels
from game.model import DIRECTIONS, Game
from game.navigation import find_path, IsoBoard
from game.themes import scene_for, themed_floor
from game.worker_view import draw_worker_status
from tests.solutions import SOLUTIONS


class LateRoomTests(unittest.TestCase):
    def go(self, game, target):
        path = find_path(game, target)
        self.assertIsNotNone(path, target)
        reverse = {delta: action for action, delta in DIRECTIONS.items()}
        for cell in path:
            x, y = game.state.player
            self.assertTrue(game.act(reverse[(cell[0] - x, cell[1] - y)]), game.message)

    def play(self, game, *directions):
        for action in directions:
            self.assertTrue(game.act(action), game.message)

    def test_second_worker_replays_and_holds_an_ordinary_plate(self):
        level = load_levels()[6]
        gate = next(pos for pos in level.gates if level.device_labels[pos] == "J2")
        station = next(pos for pos, (seals, _) in level.echo_links.items() if gate in seals)
        plate = level.gates[gate]
        self.assertIn(plate, level.plates)
        game = Game(level)
        game.state.player = (5, 4)

        self.play(game, "down", "up", "up")
        self.assertEqual(game.state.replay_workers[station], (6, 5))
        self.assertEqual(game.gate_status(gate), "closed")
        self.play(game, "right", "right")
        self.assertEqual(game.state.replay_workers[station], plate)
        self.assertTrue(game.plate_pressed(plate))
        self.play(game, "down", "down", "right")
        self.assertEqual(game.state.player, gate)
        self.assertEqual(game.gate_status(gate), "open")

    def test_recording_is_single_use_and_successful_interaction_advances_worker(self):
        level = load_levels()[6]
        game = Game(level)
        station = min(level.replay_workers)
        game.state.player = (2, 2)
        part = next(pos for pos, kind in game.state.items.items() if kind == "part")
        game.state.carrying = game.state.items.pop(part)
        self.play(game, "right", "up", "down", "up")
        self.assertEqual(game.state.recorded_stations, {station})
        self.assertTrue(game.undo())
        self.assertEqual(game.state.recording.inputs, ("up", "down"))
        self.assertFalse(game.state.recorded_stations)
        self.play(game, "up", "interact")
        self.assertEqual(game.state.player, (3, 1))
        self.assertEqual(game.state.replay_workers[station], (1, 1))
        self.play(game, "down", "up", "down")
        self.assertEqual(game.state.player, station)
        self.assertIsNone(game.state.recording)
        self.assertFalse(game.can_interact())
        game.restart()
        self.assertFalse(game.state.recorded_stations)

    def test_boss_worker_stops_on_one_plate_and_holds_both_doors(self):
        level = load_levels()[7]
        game = Game(level)
        station, = level.jobs
        lever, = level.levers
        seals, steps = level.echo_links[station]
        plate, = set(seals.values())
        doors = tuple(seals)
        self.assertEqual(steps, 4)
        self.assertTrue(all(level.gates[door] == plate for door in doors))

        for action in SOLUTIONS[level.id]:
            self.play(game, action)
            if game.state.player == station:
                break
        self.play(game, "up", "up", "right", "right")
        self.assertEqual(game.state.replay_workers[station], level.replay_workers[station])
        self.play(game, "right", "left", "right")
        self.assertTrue(all(game.gate_status(door) == "closed" for door in doors))
        self.play(game, "right")
        self.assertEqual(game.state.replay_workers[station], plate)
        self.assertTrue(all(game.gate_status(door) == "open" for door in doors))
        self.go(game, lever)
        self.play(game, "interact")
        self.go(game, level.exit)
        self.assertTrue(game.state.cleared)

    def test_worker_status_shows_recording_order_and_open_doors(self):
        level = load_levels()[7]
        game = Game(level)
        game.state.player = (1, 3)

        def hud():
            view = Mock()
            with (patch("game.worker_view.p.draw_rectangle"),
                  patch("game.worker_view.draw_direction_arrow") as arrow):
                self.assertTrue(draw_worker_status(view, game, "", (0, 0, 0)))
            directions = [call.args[2] for call in arrow.call_args_list]
            labels = {call.args[2] for calls in (view.text, view.centered) for call in calls.call_args_list}
            return directions, labels

        self.play(game, "right", "up", "up", "right")
        directions, labels = hud()
        self.assertEqual(directions, ["up", "up", "right"])
        self.assertIn("발걸음 기록 3/4", labels)

        self.play(game, "right")
        directions, labels = hud()
        self.assertEqual(directions, ["up", "up", "right", "right"])
        self.assertTrue({"인부 재생 0/4", "J1 닫힘", "J2 닫힘"} <= labels)
        self.play(game, "right", "left", "right", "right")
        self.assertTrue({"재생 완료 4/4", "J1 통과", "J2 통과"} <= hud()[1])
        self.assertTrue(game.undo())
        self.assertTrue({"인부 재생 3/4", "J1 닫힘", "J2 닫힘"} <= hud()[1])

    def test_new_themes_and_twelve_cell_boards_resolve_real_assets(self):
        root = Path(__file__).resolve().parents[1]
        for level in load_levels()[6:]:
            scene = scene_for(level)
            pack = scene["packs"][0]
            manifest = json.loads((root / "assets/map_pack_v1" / pack / "manifest.json").read_text(encoding="utf-8"))
            validation = json.loads((root / "assets/map_pack_v1" / pack / "validation.json").read_text(encoding="utf-8"))
            self.assertEqual(validation["count"], 16)
            self.assertTrue(validation["source_cells_unclipped"] and validation["output_padding"])
            for decoration in scene["decorations"]:
                self.assertIn(decoration["sprite"], manifest["sprites"])
            projection = IsoBoard(level.width, level.height)
            for y in range(level.height):
                for x in range(level.width):
                    pos = (x, y)
                    self.assertEqual(projection.pick(*projection.screen(pos)), pos)
                    self.assertIn(themed_floor(scene, pos)[0], manifest["sprites"])


if __name__ == "__main__":
    unittest.main()
