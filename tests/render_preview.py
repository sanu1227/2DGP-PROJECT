"""진단용 실제 SDL 화면 저장: python -m tests.render_preview 4 --steps 6 --output path.png"""

import argparse
from pathlib import Path
from time import perf_counter

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.view import View, WIDTH, HEIGHT
from tests.test_game import SOLUTIONS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=int)
    parser.add_argument("--steps", type=int, default=0, help="정답의 처음 N개 행동 적용 (-1: 완료)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=int, nargs=2, metavar=("X", "Y"), help="선택한 이동 경로도 표시")
    parser.add_argument("--hide-coordinates", action="store_true", help="F2 좌표를 숨긴 게임 화면 저장")
    parser.add_argument("--isometric", action="store_true", help="기존 사선 시점으로 저장")
    args = parser.parse_args()
    levels = load_levels()
    if not 1 <= args.stage <= len(levels):
        parser.error("스테이지 번호가 범위를 벗어났습니다.")
    game = Game(levels[args.stage - 1])
    actions = SOLUTIONS[game.level.id]
    if args.steps < -1 or args.steps > len(actions):
        parser.error("정답 행동 수가 범위를 벗어났습니다.")
    for action in actions if args.steps == -1 else actions[:args.steps]:
        if not game.act(action):
            raise RuntimeError(game.message)
    p.open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        view = View()
        view.top_down = not args.isometric
        if args.hide_coordinates:
            view.show_coordinates = False
        if args.target is not None and not view.navigation.start(game, tuple(args.target), perf_counter()):
            parser.error("현재 상태에서 목표 칸까지 이동할 수 없습니다.")
        view.draw(game, args.stage - 1, len(levels))
        surface = p.SDL_CreateRGBSurfaceWithFormat(0, WIDTH, HEIGHT, 32, p.SDL_PIXELFORMAT_RGBA32)
        if not surface:
            raise RuntimeError("SDL surface 생성 실패")
        try:
            if p.SDL_RenderReadPixels(p.renderer, None, surface.contents.format.contents.format,
                                      surface.contents.pixels, surface.contents.pitch) != 0:
                raise RuntimeError("SDL 화면 읽기 실패")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            if p.IMG_SavePNG(surface, str(args.output).encode("utf-8")) != 0:
                raise OSError("PNG 저장 실패")
        finally:
            p.SDL_FreeSurface(surface)
        p.update_canvas()
        print(f"{game.level.id}: {game.state.moves} actions, cleared={game.state.cleared}; {args.output}")
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == "__main__":
    main()
