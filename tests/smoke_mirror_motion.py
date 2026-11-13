"""네 방향 회전의 보간, 연속 입력, 표시 광선, 일시정지와 초기화를 검사한다."""

import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_RENDER_DRIVER'] = 'software'

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import argparse
import ctypes
import subprocess
import tempfile

import pico2d.pico2d as p

from game.levels import load_levels
from game.model import Game
from game.navigation import IsoBoard
from game.view import View, WIDTH, HEIGHT, MIRROR_SECONDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    level = replace(load_levels()[4], id='mirror_motion_probe', start=(3, 3), exit=(6, 6), action_limit=None,
                    walls=frozenset(), traps=frozenset(), posts=frozenset(), benches=frozenset(),
                    levers=frozenset(), gates={(5, 5): (3, 5)}, chutes={}, plates=frozenset(), initial_items={},
                    mirrors=frozenset({(3, 3)}), sources={(1, 3): 'right'}, receivers=frozenset({(3, 5)}),
                    device_labels={(3, 5): 'M1', (5, 5): 'M1'})
    game = Game(level)
    mirror = (3, 3)
    projection = IsoBoard(8, 8)
    sx, sy = projection.screen(mirror)
    scale = projection.half_width * 2 / 224
    p.open_canvas(WIDTH, HEIGHT)
    view = None
    frames = []
    try:
        view = View()

        def rotate(now):
            previous = game.state
            assert game.act('interact')
            with patch('game.view.perf_counter', return_value=now):
                view.animate_devices(game, previous)

        def frame(now):
            before = deepcopy(game.state)
            with patch('game.view.perf_counter', return_value=now), patch.object(view, 'text', wraps=view.text) as text:
                view.draw(game, 0, 1)
                angle = view.mirror_rotation(game, mirror, view.now())
            assert game.state == before
            mask = next(mask for region, mask in view.hit_masks.items() if region[0] == mirror and mask[0] == 'mirror')
            assert mask[-1] == angle
            for polygon, _, _ in view.art.mirror_faces(sx, sy, scale, angle):
                center = tuple(sum(point[i] for point in polygon) / 4 for i in (0, 1))
                assert view.art.hit_test('mirror', sx, sy, scale, center, rotation=angle)
            return angle, [call.args[2] for call in text.call_args_list]

        def capture(angle):
            if args.capture is None:
                return
            # 실제 SDL 렌더러의 판과 화살표를 잘라 GIF로 기록한다. 원본 에셋은 수정하지 않는다.
            p.clear_canvas()
            p.draw_rectangle(0, 0, WIDTH, HEIGHT, 20, 31, 37, filled=True)
            view.art.draw_mirror(800, 400, 1.8, angle)
            view.centered(800, 640, '거울 90도씩 부드럽게 회전', 26)
            surface = p.SDL_CreateRGBSurfaceWithFormat(0, WIDTH, HEIGHT, 32, p.SDL_PIXELFORMAT_RGBA32)
            try:
                assert p.SDL_RenderReadPixels(p.renderer, None, p.SDL_PIXELFORMAT_RGBA32,
                                             surface.contents.pixels, surface.contents.pitch) == 0
                raw = ctypes.string_at(surface.contents.pixels, surface.contents.pitch * HEIGHT)
                pitch = surface.contents.pitch
                frames.append(b''.join(raw[y * pitch + 520 * 4:y * pitch + 1080 * 4] for y in range(285, 675)))
            finally:
                p.SDL_FreeSurface(surface)

        for orientation in range(4):
            began = 1 + orientation
            frame(began - .1)
            rotate(began)
            angles = []
            for i in range(13):
                angle, labels = frame(began + MIRROR_SECONDS * i / 12)
                angles.append(angle)
                if i < 12:
                    assert 'M1 수신 완료' not in labels
                    assert view.gate_motions[(5, 5)][1] == 0, '거울 정렬 전에 연결문이 열리기 시작했습니다.'
                capture(angle)
            assert abs(angles[0] - orientation) < 1e-8
            assert abs(angles[6] - (orientation + .5)) < 1e-8
            assert all(a < b for a, b in zip(angles[:-2], angles[1:-1]))
            final, labels = frame(began + MIRROR_SECONDS + .001)
            assert final == (orientation + 1) % 4
            assert ('M1 수신 완료' in labels) == (orientation == 0)
            assert view.gate_motions[(5, 5)][1] == int(orientation == 0)
            for _ in range(7):
                capture(final)

        # 4→1 경계와 빠른 연속 입력에서도 현재 각도를 유지하며 같은 방향으로 이어진다.
        rotate(6)
        start = frame(6.08)[0]
        rotate(6.08)
        assert frame(6.08)[0] == start
        rotate(6.08)
        assert frame(6.08)[0] == start
        assert frame(6.2)[0] > start
        frozen = frame(6.25)[0]
        with patch('game.view.perf_counter', return_value=6.25):
            view.pause()
        assert frame(26.25)[0] == frozen
        with patch('game.view.perf_counter', return_value=26.25):
            view.resume()
        assert frame(26.25)[0] == frozen
        assert frame(27)[0] == 3
        assert not view.mirror_motions
        rotate(28)
        assert game.undo()
        view.reset_player()
        assert frame(28.1)[0] == 3 and not view.mirror_motions
        game.restart()
        view.reset_player()
        assert frame(28.2)[0] == 0 and not view.mirror_motions
        rotate(29)
        game = Game(level)
        assert frame(29.1)[0] == 0 and not view.mirror_motions
        if args.capture:
            args.capture.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix='.rgba', delete=False) as capture_file:
                raw_path = Path(capture_file.name)
                for pixels in frames:
                    capture_file.write(pixels)
            try:
                # 프로젝트 아트 도구에 이미 설치된 sharp만 사용한다. 게임에는 추가 의존성이 없다.
                script = """import sharp from 'sharp'; import fs from 'node:fs/promises';
const raw = await fs.readFile(process.argv[1]);
await sharp(raw, {raw:{width:560,height:raw.length/2240,channels:4,pageHeight:390}})
  .gif({delay:25,loop:0}).toFile(process.argv[2]);
await sharp(raw.subarray(6*560*390*4,7*560*390*4), {raw:{width:560,height:390,channels:4}})
  .png().toFile(process.argv[2].replace(/\\.gif$/, '-mid.png'));
"""
                subprocess.run(['node', '--input-type=module', '-e', script, str(raw_path), str(args.capture.resolve())],
                               cwd=Path(__file__).resolve().parents[1] / 'tools/art', check=True)
            finally:
                raw_path.unlink()
        print('Mirror motion OK: four eased quarter turns, 4-to-1 wrap, live mesh/picking, beam waits, rapid input, pause, undo, restart and room change; model unchanged.')
    finally:
        if view:
            view.close()
        p.close_canvas()


if __name__ == '__main__':
    main()
