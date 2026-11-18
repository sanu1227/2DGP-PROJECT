from unittest import TestCase
from unittest.mock import Mock, patch

from game.levels import load_levels
from game.model import DIRECTIONS, Echo, Game
from game.view import View
from game.worker_view import DORMANT_TINT, EchoMotion, STRIDE_SECONDS, draw_recording_progress, draw_skeleton_worker
from tests.solutions import SOLUTIONS


class InspectionTests(TestCase):
    def test_worker_walk_follows_actual_step_and_stops_on_idle_pose(self):
        game = Game(load_levels()[7])
        origin, (x, y) = next(iter(game.state.replay_workers.items()))
        for direction, (dx, dy) in DIRECTIONS.items():
            with self.subTest(direction=direction):
                animation = EchoMotion()
                previous = Game(game.level).state
                previous.echo = Echo(origin, (x, y), (direction,))
                game.state.echo = Echo(origin, (x + dx, y + dy), (), True)
                animation.change(game, previous, 10)
                self.assertEqual(animation.pose(game, 10)[0], (x, y))
                self.assertEqual([animation.skeleton_sprite(10 + STRIDE_SECONDS * fraction)
                                  for fraction in (.1, .35, .6, .85, 1.1)],
                                 [f"skeleton_worker_{direction}_{frame}" for frame in (0, 1, 2, 3, 1)])
                self.assertEqual(animation.pose(game, 11)[0], (x + dx, y + dy))

    def test_blocked_worker_does_not_start_walking(self):
        game = Game(load_levels()[7])
        origin, pos = next(iter(game.state.replay_workers.items()))
        previous = Game(game.level).state
        previous.echo = Echo(origin, pos, ("up",))
        game.state.echo = Echo(origin, pos, ())
        animation = EchoMotion()
        animation.change(game, previous, 10)
        self.assertIsNone(animation.motion)
        self.assertEqual(animation.skeleton_sprite(10), "skeleton_worker_down_1")

    def test_recording_only_wakes_the_linked_worker_and_tracks_accepted_steps(self):
        game = Game(load_levels()[7])
        motion, art = EchoMotion(), Mock()
        origin, other = game.state.replay_workers
        draw_skeleton_worker(art, game, origin, motion, 100, 100, 48, 0)
        self.assertEqual(art.draw.call_args.kwargs["tint"], DORMANT_TINT)

        with (patch("game.worker_view.draw_recording_orbit") as orbit,
              patch("game.worker_view.p.draw_circle") as pip,
              patch("game.worker_view.ring") as ring):
            for tick, action in enumerate(SOLUTIONS[game.level.id], start=1):
                previous = game.state
                self.assertTrue(game.act(action))
                motion.change(game, previous, tick)
                recording = game.state.recording
                if recording and recording.origin == origin:
                    count = len(recording.inputs)
                    if count == 0:
                        self.assertEqual(motion.wake_at, tick)
                    else:
                        self.assertEqual(motion.step_at, tick)
                    draw_skeleton_worker(art, game, origin, motion, 100, 100, 48, tick + .25)
                    self.assertIsNone(art.draw.call_args.kwargs["tint"])
                    pip.reset_mock()
                    draw_recording_progress(game, self.view.projection(game.level), motion, tick + .25)
                    marks = pip.call_args_list[1::2]
                    self.assertEqual(len(marks), game.level.echo_links[origin][1])
                    self.assertEqual(sum(mark.kwargs["filled"] for mark in marks), count)
                    draw_skeleton_worker(art, game, other, motion, 300, 100, 48, tick + .25)
                    self.assertEqual(art.draw.call_args.kwargs["tint"], DORMANT_TINT)
                if origin in game.state.recorded_stations:
                    self.assertEqual(motion.confirmation, (origin, tick))
                    draw_skeleton_worker(art, game, origin, motion, 100, 100, 48, tick + .1)
                    self.assertIsNone(art.draw.call_args.kwargs["tint"])
                    break
            self.assertEqual(orbit.call_count, game.level.echo_links[origin][1])
            ring.assert_called_once()

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
