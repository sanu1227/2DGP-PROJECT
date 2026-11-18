from unittest import TestCase
from unittest.mock import Mock, patch

from game.levels import load_levels
from game.model import Game
from game.view import View
from tests.solutions import SOLUTIONS


class InspectionTests(TestCase):
    def setUp(self):
        self.levels = load_levels()
        self.view = View.__new__(View)
        self.view.inspected = None
        self.view.top_down = True
        self.view.text = Mock()
        self.view.text_width = Mock(return_value=78)
        self.view.centered = Mock()
        self.view.echo_motion = Mock()
        self.view.echo_motion.pose.return_value = None
        self.view.now = Mock(return_value=0)
        self.view.tile_outline = Mock()

    def test_receiver_and_gate_select_same_link(self):
        game = Game(self.levels[5])
        gate, receiver = next((gate, control) for gate, control in game.level.gates.items()
                              if control in game.level.receivers)
        self.view.inspect_cell(game, gate)
        self.assertEqual(self.view.inspected, ("receiver", receiver))
        with patch("game.view.bevel"), patch("game.view.box"):
            self.view.draw_inspection(game)
        self.assertTrue(any(call.args[2].startswith("연결문 ") for call in self.view.text.call_args_list))
        self.view.inspect_cell(game, receiver)
        self.assertIsNone(self.view.inspected)

    def test_pinned_worker_updates_to_next_action(self):
        game = Game(self.levels[7])
        for action in SOLUTIONS[game.level.id]:
            self.assertTrue(game.act(action))
            echo = game.state.echo
            if echo and echo.remaining and echo.origin in game.state.replay_workers:
                break
        else:
            self.fail("풀이에서 재생 중인 인부를 찾지 못했습니다.")
        self.view.inspect_cell(game, echo.position)
        self.assertEqual(self.view.inspected, ("worker", echo.origin))
        with patch("game.view.bevel"), patch("game.view.line"), patch("game.view.draw_direction_arrow") as arrow:
            self.view.draw_inspection(game)
            self.assertEqual(arrow.call_args.args[2], echo.remaining[0])
            self.assertEqual(self.view.centered.call_args.args[2], f"{len(echo.remaining)}걸음 남음")
            px, py = self.view.projection(game.level).screen(echo.position)
            x, y = self.view.centered.call_args.args[:2]
            self.assertLess(abs(x - px), 20)
            self.assertLess(abs(y - py), 100)
