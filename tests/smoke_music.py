"""창과 스피커 없이 실제 MP3 디코딩·반복·화면 전환을 검사한다."""

import ctypes
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_RENDER_DRIVER"] = "software"

import pico2d.pico2d as p
from sdl2.sdlmixer import mix_func

from game import view
from game.levels import load_levels
from game.music import BackgroundMusic, VOLUMES
from game.story_audio import SDLStorySounds


def decoder_checks():
    p.open_canvas(32, 32)
    music, sounds = BackgroundMusic(), SDLStorySounds()
    audible = []

    @mix_func
    def capture(_, stream, length):
        audible.append(any(ctypes.string_at(stream, length)))

    try:
        assert p.SDL_GetCurrentAudioDriver() == b"dummy"
        assert p.SDL_GetCurrentVideoDriver() == b"dummy"
        p.Mix_SetPostMix(capture, None)
        for name in ("title", "playing"):
            music.update(name)
            assert music.current == name and p.Mix_PlayingMusic()
            duration = p.Mix_MusicDuration(music.tracks[name].music)
            assert duration > 1
            assert p.Mix_SetMusicPosition(min(15, duration / 2)) == 0
            # 페이드 시작 직후 메뉴를 열어도 최종 음량이 정상적으로 낮아지는지 확인한다.
            music.update(name, quiet=True)
            audible.clear()
            p.SDL_Delay(800)
            assert any(audible), f"{name}: MP3 디코딩 결과가 무음"
            expected_volume = VOLUMES[name] // 2 if name == "playing" else VOLUMES[name]
            assert p.Mix_VolumeMusic(-1) == expected_volume, (name, p.Mix_VolumeMusic(-1))
            music.update(name)
            assert p.Mix_VolumeMusic(-1) == VOLUMES[name]
            assert p.Mix_SetMusicPosition(duration - .15) == 0
            p.SDL_Delay(500)
            assert p.Mix_PlayingMusic(), f"{name}: 곡이 끝난 뒤 반복하지 않음"
            position = p.Mix_GetMusicPosition(music.tracks[name].music)
            assert 0 <= position < 2, (name, duration, position)
            print(f"{name}: {duration:.2f}s, decoded audio and end-to-start repeat OK")

        sounds.play("dungeon_collapse")
        channels = sounds.active_channels()
        assert channels
        music.update("story")
        assert not p.Mix_PlayingMusic()
        assert all(p.Mix_Playing(channel) for channel in channels)
    finally:
        p.Mix_SetPostMix(mix_func(), None)
        music.close()
        sounds.close()
        p.close_canvas()


def input_checks():
    instances = []
    frame = -1

    def key(value):
        return SimpleNamespace(type=p.SDL_KEYDOWN, key=value)

    def click(x, y):
        return SimpleNamespace(type=p.SDL_MOUSEBUTTONDOWN, button=p.SDL_BUTTON_LEFT,
                               x=x, y=view.HEIGHT - 1 - y)

    # 입력, 예상 곡, 예상 음량, 곡 시작 횟수. 방 이동·메뉴에서는 시작 횟수가 늘지 않는다.
    steps = [
        ([], None, None, 0),
        ([key(p.SDLK_ESCAPE)], "title", 48, 1),
        ([key(p.SDLK_RETURN)], None, None, 1),
        ([click(1460, 900)], "title", 48, 2),
        ([key(p.SDLK_RETURN)], "title", 48, 2),
        ([key(p.SDLK_RETURN)], "playing", 20, 3),
        ([key(p.SDLK_ESCAPE)], "playing", 40, 3),
        ([key(p.SDLK_r)], "playing", 40, 3),
        ([key(p.SDLK_4)], "playing", 20, 3),
        ([key(p.SDLK_ESCAPE)], "playing", 40, 3),
        ([key(p.SDLK_ESCAPE)], "playing", 20, 3),
        ([click(800, 285)], "title", 48, 4),
        ([key(p.SDLK_1)], "playing", 40, 5),
        ([SimpleNamespace(type=p.SDL_QUIT)], "playing", 40, 5),
    ]

    class ObservedMusic(BackgroundMusic):
        def __init__(self):
            super().__init__()
            instances.append(self)

    original_update, original_close = p.update_canvas, p.close_canvas

    def events():
        nonlocal frame
        frame += 1
        assert frame < len(steps), "게임 종료 입력 미처리"
        return steps[frame][0]

    def update():
        if frame >= 0:
            _, expected, volume, starts = steps[frame]
            music = instances[-1]
            assert (music.current, music.volume) == (expected, volume), (frame, music.current, music.volume)
            assert bool(p.Mix_PlayingMusic()) == (expected is not None), frame
            assert played.call_count == starts, (frame, played.call_count)
        original_update()

    def close():
        assert instances[-1].current is None and not instances[-1].tracks
        assert not p.Mix_PlayingMusic(), "SDL 종료 전에 음악을 정리하지 않음"
        original_close()

    with patch.object(view, "BackgroundMusic", ObservedMusic), \
            patch.object(p, "get_events", events), patch.object(p, "update_canvas", update), \
            patch.object(p, "close_canvas", close), \
            patch.object(p, "Mix_FadeInMusic", wraps=p.Mix_FadeInMusic) as played:
        view.run(load_levels())
    assert frame == len(steps) - 1
    print("Music input smoke OK: title, story, controls, gameplay, restart, room change, menus, return, shortcut, cleanup")


if __name__ == "__main__":
    decoder_checks()
    input_checks()
