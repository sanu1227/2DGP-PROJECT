"""검증된 기믹 방의 풀이를 재생하고 이전 초안 파일 형식으로 내보낸다."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.levels import load_levels, DIRECTIONS
from game.model import Game
from game.navigation import find_path

# 기존 초안 도구의 진입점을 유지하되 검증한 행동열을 단일 기준으로 사용한다.
from tests.solutions import MINIMUM_ACTIONS, SOLUTIONS
WAYPOINTS = {name: actions for name, actions in SOLUTIONS.items() if int(name[-2:]) >= 4}


def replay(level, route):
    game, actions = Game(level), []
    reverse = {delta: action for action, delta in DIRECTIONS.items()}
    def act(action):
        if not game.act(action):
            raise AssertionError((level.id, game.state.player, action, game.message))
        actions.append(action)
    for command in route:
        if isinstance(command, str):
            act('interact' if command == 'E' else command)
        else:
            target=tuple(command)
            path=find_path(game,target)
            if path is None:
                raise AssertionError((level.id, game.state.player, 'no path', target))
            for cell in path:
                x,y=game.state.player
                act(reverse[cell[0]-x,cell[1]-y])
    assert game.state.cleared, (level.id,game.state)
    return game, actions

def main():
    results={}
    for level in load_levels()[3:]:
        game,actions=replay(level,WAYPOINTS[level.id])
        assert len(actions) == MINIMUM_ACTIONS[level.id]
        results[level.id]={'verified_actions':len(actions),'minimum_proven':True, 'minimum':MINIMUM_ACTIONS[level.id],
                           'waypoints':WAYPOINTS[level.id],'actions':actions}
        while game.history: game.undo()
        assert game.state == Game(level).state
        print(level.id,len(actions),'complete; full undo OK')
    path=Path(__file__).resolve().parents[1]/'data/gimmick_draft_routes.json'
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
