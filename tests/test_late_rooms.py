"""보물창고의 추 재사용과 왕좌실의 최종 봉쇄 순서를 검사한다."""

import json
from pathlib import Path
import unittest

from game.levels import load_levels
from game.model import DIRECTIONS, Game
from game.navigation import find_path, IsoBoard
from game.themes import scene_for, themed_floor


class LateRoomTests(unittest.TestCase):
    def go(self, game, target):
        path = find_path(game, target)
        self.assertIsNotNone(path, target)
        reverse = {delta: action for action, delta in DIRECTIONS.items()}
        for cell in path:
            x, y = game.state.player
            self.assertTrue(game.act(reverse[(cell[0] - x, cell[1] - y)]), game.message)

    def test_second_treasury_gate_opens_after_four_recorded_steps(self):
        level = load_levels()[6]
        game = Game(level)
        gate = next(pos for pos in level.gates if level.device_labels[pos] == "J2")
        station = level.gates[gate]
        seal, steps = level.echo_links[station]
        self.assertEqual(steps, 4)
        game.state.player = station

        self.assertTrue(game.act("interact"))
        for action in ("right", "up", "right"):
            self.assertTrue(game.act(action))
            self.assertIsNotNone(game.state.recording)
        self.assertTrue(game.act("up"))
        self.assertEqual(game.state.player, station)
        self.assertEqual(len(game.state.echo.remaining), steps - 1)

        for action in ("right", "up"):
            self.assertTrue(game.act(action))
            self.assertEqual(game.gate_status(gate), "closed")
        self.assertTrue(game.act("right"))
        self.assertEqual(game.state.echo.position, seal)
        self.assertEqual(game.gate_status(gate), "open")
        self.assertTrue(game.act("down"))
        self.assertEqual(game.state.player, gate)

    def test_boss_echo_keeps_vault_open_after_east_wing_closes(self):
        level = load_levels()[7]
        game = Game(level)
        mirror, = level.mirrors
        job, = level.jobs
        post, = level.posts
        trap, = level.traps
        lever, = level.levers
        worker = next(pos for pos, item in level.initial_items.items() if item == "soldier")
        part = next(pos for pos, item in level.initial_items.items() if item == "part")
        gates = {level.device_labels[gate]: gate for gate in level.gates}

        def use(target, times=1):
            self.go(game, target)
            for _ in range(times):
                self.assertTrue(game.act("interact"), game.message)

        def assert_open(*labels):
            self.assertEqual({label for label, gate in gates.items() if game.gate_status(gate) == "open"},
                             set(labels))

        use(mirror, 2)
        assert_open("M2")
        self.assertIsNone(find_path(game, part))
        self.assertIsNone(find_path(game, worker))
        self.assertTrue(game.undo())
        assert_open("M1")

        use(job)
        self.go(game, level.echo_links[job][0])
        self.assertEqual(game.state.player, job)
        assert_open("M1")
        use(worker)
        assert_open("M1", "J1")
        use(post)
        assert_open("J1")
        self.assertIsNone(find_path(game, job))
        self.assertIsNone(find_path(game, part))
        use(mirror)
        assert_open("M2", "J1")
        use(part)
        use(trap)
        use(lever)
        self.assertIsNone(find_path(game, mirror))
        self.go(game, level.exit)
        self.assertTrue(game.state.cleared)

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
