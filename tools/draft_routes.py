"""초안의 실제 행동열을 재생한다. 최단 풀이를 주장하지 않는다."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game.levels import load_levels, DIRECTIONS
from game.model import Game
from game.navigation import find_path

# (x,y)는 이동, 'E'는 상호작용, 다른 문자열은 직접 방향 입력이다.
WAYPOINTS = {
    'stage_04': [(3,3),'down',(7,2),'E',(6,8),'E',(5,6),'E',(7,6),'E',
                 (5,8),'E',(7,6),'E',(7,7),'E',(7,8),'E',(8,8)],
    'stage_05': [(3,2),'E',(7,2),'E',(7,4),'E',(4,6),'E',(3,7),'E',
                 (2,6),'E',(3,7),'E',(4,7),'E',(1,8)],
    'stage_06': [(7,2),'E',(3,6),'E',(3,4),'E',(7,5),'E',(7,6),'E',
                 (8,7),'E',(7,6),'E',(7,8),'E',(3,7),'E',(1,8)],
    'stage_07': [(2,2),'E',(3,3),'E',(4,2),'E',(3,3),'E',(3,5),'E',
                 (8,3),'E',(4,7),'E',(3,5),'E',(5,7),'E',(3,8),'E',(2,10)],
    'stage_08': [(4,2),'E',(8,5),'E',(8,6),'E',(4,6),'E',(3,7),'E',
                 (2,7),'E',(3,7),'E',(7,2),'E',(10,2),'E',(4,8),'E',
                 (2,5),'E',(7,9),'right','right',(10,8),'E',(4,9),'E',
                 (7,2),'E',(3,9),'E',(2,9),'E',(1,10)],
}

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
        results[level.id]={'verified_actions':len(actions),'minimum_proven':False,
                           'waypoints':WAYPOINTS[level.id],'actions':actions}
        while game.history: game.undo()
        assert game.state == Game(level).state
        print(level.id,len(actions),'complete; full undo OK')
    path=Path(__file__).resolve().parents[1]/'data/gimmick_draft_routes.json'
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
