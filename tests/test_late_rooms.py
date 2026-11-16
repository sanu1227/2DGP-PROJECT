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

    def test_second_worker_replays_from_its_own_tile(self):
        level = load_levels()[6]
        gate = next(pos for pos in level.gates if level.device_labels[pos] == "J2")
        station = level.gates[gate]
        seals, steps = level.echo_links[station]
        self.assertEqual(steps, 4)
        game = Game(level)
        game.state.player = (5, 4)

        self.play(game, "down", "up", "up", "right", "down")
        self.assertEqual(game.state.player, (6, 4))
        self.assertEqual(game.state.replay_workers[station], (6, 5))
        self.assertEqual(game.gate_status(gate), "closed")
        self.play(game, "right")
        self.assertEqual(game.state.replay_workers[station], (6, 4))
        self.assertEqual(game.gate_status(gate), "closed")
        self.play(game, "down")
        self.assertEqual(game.state.replay_workers[station], seals[gate])
        self.assertEqual(game.gate_status(gate), "open")
        self.play(game, "right", "right")
        self.assertEqual(game.gate_status(gate), "closed")

    def test_worker_reuses_current_position_and_advances_on_interact(self):
        level = load_levels()[6]
        game = Game(level)
        station = min(level.replay_workers)
        game.state.player = (2, 2)
        part = next(pos for pos, kind in game.state.items.items() if kind == "part")
        game.state.carrying = game.state.items.pop(part)

        self.play(game, "right", "right", "up")
        self.assertEqual(game.state.replay_workers[station], (1, 2))
        self.play(game, "interact")  # The player drops the part without moving.
        self.assertEqual(game.state.player, (4, 1))
        self.assertEqual(game.state.replay_workers[station], (2, 2))
        self.play(game, "left", "down", "right", "up")
        self.assertEqual(game.state.replay_workers[station], (2, 1))
        self.play(game, "interact")
        self.assertEqual(game.state.replay_workers[station], (3, 1))

    def test_boss_worker_follows_two_different_recordings_from_its_own_tile(self):
        level = load_levels()[7]
        game = Game(level)
        mirror, = level.mirrors
        station, = level.jobs
        trap, = level.traps
        lever, = level.levers
        part = next(pos for pos, item in level.initial_items.items() if item == "part")
        gates = {level.device_labels[gate]: gate for gate in level.gates}
        first, second = gates["J1"], gates["J2"]

        def use(target):
            self.go(game, target)
            self.play(game, "interact")

        use(mirror)
        use(part)
        use(trap)
        use(mirror)
        self.go(game, station)
        self.assertEqual(game.state.recording.inputs, ())
        start = game.state.moves

        self.play(game, "up", "up", "right", "left", "right")
        self.play(game, "right", "right", "right", "right", "right", "right")
        self.assertEqual(game.state.replay_workers[station], (2, 1))
        self.assertEqual(game.gate_status(first), "closed")
        self.assertEqual(game.gate_status(second), "closed")
        self.assertFalse(game.act("right"))
        while game.state.moves > start:
            self.assertTrue(game.undo())

        self.play(game, "up", "up", "right", "right", "right")
        self.assertEqual(game.state.player, (5, 1))
        self.assertEqual(game.state.replay_workers[station], (1, 3))
        for worker, statuses in (
            ((1, 2), ("closed", "closed")), ((1, 1), ("open", "closed")),
            ((2, 1), ("held", "closed")), ((3, 1), ("closed", "open")),
            ((4, 1), ("closed", "held")),
        ):
            self.play(game, "right")
            self.assertEqual(game.state.replay_workers[station], worker)
            self.assertEqual((game.gate_status(first), game.gate_status(second)), statuses)
        use(lever)
        self.go(game, level.exit)
        self.assertTrue(game.state.cleared)

    def test_worker_status_shows_recording_order_and_each_boss_gate(self):
        levels = load_levels()
        for level in levels:
            self.assertEqual(level.jobs, level.replay_workers.keys(), level.id)
        game = Game(levels[7])
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
        self.assertIn("발걸음 기록 3/5", labels)

        self.play(game, "right", "right")
        directions, labels = hud()
        self.assertEqual(directions, ["up", "up", "right", "right", "right"])
        self.assertTrue({"인부 재생 0/5", "J1 닫힘", "J2 닫힘"} <= labels)

        self.play(game, "right", "right")
        self.assertTrue({"인부 재생 2/5", "J1 통과", "J2 닫힘"} <= hud()[1])
        self.play(game, "right", "right")
        self.assertTrue({"인부 재생 4/5", "J1 닫힘", "J2 통과"} <= hud()[1])

        self.play(game, "right")
        self.assertTrue({"인부 재생 5/5", "J2 통과 중"} <= hud()[1])
        self.assertTrue(game.undo())
        self.assertTrue({"인부 재생 4/5", "J2 통과"} <= hud()[1])

        self.play(game, "right", "down")
        self.assertFalse(draw_worker_status(Mock(), game, "", (0, 0, 0)))

        game.restart()
        game.state.player = (1, 3)
        self.play(game, "right", "up", "up", "right", "left", "right")
        self.play(game, "left", "down", "up", "right", "right")
        self.assertTrue({"재생 완료 5/5", "J1 닫힘", "J2 닫힘"} <= hud()[1])

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
