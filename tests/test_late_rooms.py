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

    def record(self, game, *directions):
        self.assertTrue(game.act("interact"))
        for action in directions:
            self.assertTrue(game.act(action), game.message)

    def test_second_treasury_gate_rejects_finishing_on_the_seal(self):
        level = load_levels()[6]
        gate = next(pos for pos in level.gates if level.device_labels[pos] == "J2")
        station = level.gates[gate]
        seals, steps = level.echo_links[station]
        seal = seals[gate]
        self.assertEqual(steps, 4)

        game = Game(level)
        game.state.player = station
        self.record(game, "right", "left", "right", "up")
        for action in ("right", "left", "right"):
            self.assertTrue(game.act(action))
            self.assertEqual(game.gate_status(gate), "closed")
        self.assertEqual(game.state.echo.position, seal)
        self.assertFalse(game.state.echo.remaining)

        game = Game(level)
        game.state.player = station
        self.record(game, "right", "up", "left", "left")
        self.assertEqual(game.state.player, station)
        self.assertEqual(game.gate_status(gate), "closed")
        self.assertTrue(game.act("right"))
        self.assertEqual(game.state.echo.position, seal)
        self.assertEqual(game.gate_status(gate), "open")
        self.assertTrue(game.act("right"))
        self.assertEqual(game.state.player, gate)
        self.assertEqual(game.gate_status(gate), "held")
        self.assertTrue(game.act("right"))
        self.assertEqual(game.gate_status(gate), "closed")

    def test_boss_crosses_both_gates_with_one_echo_recording(self):
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
        first, second = gates["J1"], gates["J2"]
        seals, steps = level.echo_links[job]
        self.assertEqual(steps, 5)
        self.assertEqual(set(seals), {first, second})

        def use(target):
            self.go(game, target)
            self.assertTrue(game.act("interact"), game.message)

        use(mirror)
        use(worker)
        use(post)
        self.assertEqual(game.gate_status(gates["M1"]), "closed")
        use(mirror)
        self.go(game, job)
        self.assertEqual(game.gate_status(gates["M2"]), "open")
        self.assertIsNone(find_path(game, part))
        before_recording = game.state.moves

        def doors():
            return game.gate_status(first), game.gate_status(second)

        self.record(game, "up", "up", "right", "left", "right")
        for expected in (("open", "closed"), ("held", "closed"), ("open", "closed")):
            self.assertTrue(game.act("right"))
            self.assertEqual(doors(), expected)
        before_rejected_move = game.state
        self.assertFalse(game.act("right"))
        self.assertEqual(game.state, before_rejected_move)
        while game.state.moves > before_recording:
            self.assertTrue(game.undo())

        self.record(game, "up", "up", "right", "right", "right")
        self.assertEqual(doors(), ("closed", "closed"))
        for expected in (("open", "closed"), ("held", "closed"),
                         ("closed", "open"), ("closed", "held"), ("closed", "closed")):
            self.assertTrue(game.act("right"))
            self.assertEqual(doors(), expected)
        self.assertIn(game.state.player, level.initial_items)
        self.assertIsNone(find_path(game, job))

        use(part)
        use(trap)
        use(lever)
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
