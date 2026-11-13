"""모니터를 열지 않고 새 방의 첫 화면·작동 상태를 SDL에서 캡처한다."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import pico2d.pico2d as p
from game.levels import load_levels
from game.model import Game
from game.view import View, WIDTH, HEIGHT
from tests.solutions import SOLUTIONS
from tests.smoke_gate_animation import save_frame


def main():
    levels = load_levels()
    folder = Path(__file__).resolve().parents[1] / 'docs/screenshots/gimmicks-v1'
    folder.mkdir(parents=True, exist_ok=True)
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    count = 0
    try:
        view = View()
        for index, level in enumerate(levels[3:], 3):
            game = Game(level)
            captured = set()
            def capture(suffix):
                nonlocal count
                before = deepcopy(game.state)
                now = 1000 + game.state.moves * 2
                with patch('game.view.perf_counter', return_value=now):
                    view.draw(game, index, len(levels))
                with patch('game.view.perf_counter', return_value=now + 1):
                    view.draw(game, index, len(levels))
                assert before == game.state
                save_frame(folder / f'stage-{index+1:02d}{suffix}.png')
                count += 1
            capture('')
            for action in SOLUTIONS[level.id]:
                before = deepcopy(game.state)
                assert game.act(action), (level.id, game.message)
                for name, changed in (
                        ('mirror', game.state.turned_mirrors != before.turned_mirrors),
                        ('water', game.state.water_high != before.water_high),
                        ('rubble', game.state.rubble != before.rubble),
                        ('helper', game.state.workers != before.workers)):
                    if changed and name not in captured:
                        capture('-' + name)
                        captured.add(name)
            assert game.state.cleared
            expected = {name for name, cells in (('mirror', level.mirrors), ('water', level.valves),
                        ('rubble', level.rubble), ('helper', level.jobs)) if cells}
            assert captured == expected
        print(f'Gimmick SDL smoke OK: {count} snapshots, all four mechanics and five complete routes.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
