"""발판 애니메이션과 물건·잔해의 지지 높이를 실제 SDL로 검사한다."""
from copy import deepcopy
from unittest.mock import patch
import pico2d.pico2d as p
from game.model import Game
from game.navigation import IsoBoard
from game.view import View, WIDTH, HEIGHT, PLATE_SECONDS, ITEM_SPRITES
from tests.test_devices import load_stage, plate_stage


def main():
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        view = View()
        for kind in ('player', 'bone', 'part', 'rubble'):
            game = Game(load_stage(plate_stage()))
            plate = next(iter(game.level.plates))
            projection = IsoBoard(game.level.width, game.level.height)
            sx, sy = projection.screen(plate)
            scale = projection.half_width * 2 / 224

            def frame(now):
                before = deepcopy(game.state)
                with patch('game.view.perf_counter', return_value=now), patch.object(view.art, 'draw', wraps=view.art.draw) as draw:
                    view.draw(game, 0, 1)
                assert game.state == before
                fraction = view.plate_depths[plate]
                height = view.support_height(game, plate)
                assert abs(height - (60 - 28 * fraction)) < 1e-8
                if kind in ITEM_SPRITES and plate in game.state.items:
                    assert any(c.args[0] == ITEM_SPRITES[kind] and abs(c.args[1] - sx) < 1e-8
                               and abs(c.args[2] - sy - height * scale) < 1e-8 for c in draw.call_args_list)
                if kind == 'rubble' and plate in game.state.rubble:
                    assert any(c.args[0] == 'push_rubble' and abs(c.args[2] - sy - height * scale) < 1e-8
                               for c in draw.call_args_list)
                return fraction

            assert frame(0) == 0
            original = deepcopy(game.state)
            if kind == 'player':
                game.state.player = plate
            elif kind == 'rubble':
                game.state.rubble.add(plate)
            else:
                game.state.items[plate] = kind
            assert frame(10) == 0
            values = [frame(10 + PLATE_SECONDS * i / 12) for i in range(13)]
            assert values[0] == 0 and abs(values[-1] - 1) < 1e-8
            assert all(a < b for a, b in zip(values, values[1:]))
            game.state = original
            assert frame(11) == 1
            assert abs(frame(11 + PLATE_SECONDS / 2) - .5) < 1e-8
            assert frame(12) == 0
        print('Plate smoke OK: player, bone, part, rubble; 13 travel samples, heights and release.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
