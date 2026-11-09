"""SDL checks for discoverable targets, action prompts and marker picking."""

from copy import deepcopy
from unittest.mock import patch

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.view import View, WIDTH, HEIGHT
from tests.test_game import SOLUTIONS


def main():
    levels = load_levels()
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    checked = 0
    try:
        view = View()
        for index, level in enumerate(levels):
            game = Game(level)

            def check():
                nonlocal checked
                before = deepcopy(game.state)
                with patch.object(view, "text", wraps=view.text) as text:
                    view.draw(game, index, len(levels))
                assert game.state == before
                prompts = [call for call in text.call_args_list if call.args[2] == "E"]
                assert bool(prompts) == game.can_interact()
                for pos, (left, bottom, right, top) in view.interaction_regions.items():
                    picked = view.pick_cell(game, (left + right) / 2, (bottom + top) / 2)
                    assert picked == pos, (level.id, game.state.moves, pos, picked)
                    assert pos not in level.walls
                if game.state.cleared:
                    assert not view.interaction_regions
                else:
                    assert game.state.items.keys() <= view.interaction_regions.keys()
                    assert not ((game.state.installed | game.state.soldiers)
                                - game.state.items.keys()) & view.interaction_regions.keys()
                checked += 1

            check()
            for action in SOLUTIONS[level.id]:
                if action == "interact":
                    check()
                    assert game.can_interact()
                    before = deepcopy(game.state)
                    assert game.act(action), game.message
                    check()
                    after = deepcopy(game.state)
                    assert game.undo()
                    assert game.state == before
                    check()
                    assert game.act(action)
                    assert game.state == after
                else:
                    assert game.act(action), game.message
            check()

        # A full hand must suppress the E prompt even on a collectible.
        index, level = 0, levels[0]
        game = Game(level)
        game.state.player = next(iter(game.state.items))
        game.state.carrying = "bone"
        check()
        assert not game.can_interact()
        # Hovering the marker exposes the collectible's name and keeps its click target.
        game.state.player = game.level.start
        view.draw(game, 0, len(levels))
        pos = next(iter(game.state.items))
        left, bottom, right, top = view.interaction_regions[pos]
        view.mouse_position = ((left + right) / 2, (bottom + top) / 2)
        with patch.object(view, "text", wraps=view.text) as text:
            view.draw(game, 0, len(levels))
        assert any("상호작용 대상: 함정 부품" in call.args[2] for call in text.call_args_list)
        assert view.pick_cell(game, *view.mouse_position) == pos
        print(f"Interaction smoke OK: {checked} states across six rooms; marker clicks, "
              "E availability, pickup/install/activation, undo, cleared state and hover.")
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
