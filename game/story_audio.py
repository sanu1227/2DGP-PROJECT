"""만화의 동작 시간에 맞춰 한 번씩 재생하는 효과음."""

from ctypes import cast, c_void_p
from pathlib import Path
import warnings

from game.character_motion import ACCEL_SECONDS, EXHALE_START, INHALE_START, WALK_END, WALK_START
from game.comic_effects import IMPACTS


AUDIO_ROOT = Path(__file__).resolve().parents[1] / "assets/audio_story_v1"
STEP_TIMES = (WALK_START, *(WALK_START + ACCEL_SECONDS / 2
              + n * (WALK_END - WALK_START - ACCEL_SECONDS / 2) / 4 for n in range(1, 5)),
              WALK_END + (INHALE_START - WALK_END) * .53)
CUES = (
    ((IMPACTS[0][0][0], "hero_arrival"),),
    (),
    (*((time, "step_left" if index % 2 == 0 else "step_right")
       for index, time in enumerate(STEP_TIMES)), (EXHALE_START, "worker_sigh")),
    tuple((start, "boss_bark") for start, _, _ in IMPACTS[3]),
)
MAX_LATENESS = .20


class SDLStorySounds:
    """자신이 재생한 채널만 제어한다. 시스템 음량은 변경하지 않는다."""
    def __init__(self):
        self.sounds = {}
        self.channels = {}
        self.disabled = False

    def active_channels(self):
        import pico2d.pico2d as p
        for channel, sound in list(self.channels.items()):
            current = p.Mix_GetChunk(channel)
            if not p.Mix_Playing(channel) or cast(current, c_void_p).value != cast(sound.wav, c_void_p).value:
                del self.channels[channel]
        return tuple(self.channels)

    def play(self, name):
        import pico2d.pico2d as p
        if self.disabled:
            return
        try:
            if not p.Mix_QuerySpec(None, None, None):
                raise OSError("SDL audio device unavailable")
            if name not in self.sounds:
                self.sounds[name] = p.load_wav(str(AUDIO_ROOT / f"{name}.wav"))
                self.sounds[name].set_volume(78)
            self.active_channels()
            sound = self.sounds[name]
            channel = p.Mix_PlayChannel(-1, sound.wav, 0)
            if channel >= 0:
                self.channels[channel] = sound
        except OSError as error:
            self.disabled = True
            warnings.warn(f"만화 효과음을 사용할 수 없어 무음으로 진행합니다: {error}", RuntimeWarning)

    def pause(self):
        import pico2d.pico2d as p
        for channel in self.active_channels():
            p.Mix_Pause(channel)

    def resume(self):
        import pico2d.pico2d as p
        for channel in self.active_channels():
            p.Mix_Resume(channel)

    def stop(self):
        import pico2d.pico2d as p
        for channel in self.active_channels():
            p.Mix_HaltChannel(channel)
        self.channels.clear()

    def close(self):
        self.stop()
        self.sounds.clear()


class StoryAudio:
    def __init__(self, backend=None):
        self.backend = backend if backend is not None else SDLStorySounds()
        self.index = None
        self.cursor = 0.0
        self.paused = False

    def set_paused(self, paused):
        if paused != self.paused:
            (self.backend.pause if paused else self.backend.resume)()
            self.paused = paused

    def seek(self, index, elapsed=0.0, paused=False):
        self.backend.stop()
        self.index, self.cursor, self.paused = index, elapsed, paused

    def update(self, index, elapsed, paused=False):
        if index != self.index:
            self.seek(index)
        elif elapsed < self.cursor:
            self.seek(index, elapsed, paused)
        self.set_paused(paused)
        if not paused:
            for time, name in CUES[index]:
                # 프레임 경계에서 딱 한 번. 긴 멈춤 뒤 지나간 소리를 몰아서 재생하지 않는다.
                if self.cursor < time <= elapsed and elapsed - time <= MAX_LATENESS:
                    self.backend.play(name)
            self.cursor = elapsed

    def stop(self):
        if self.index is not None:
            self.backend.stop()
        self.index, self.cursor, self.paused = None, 0.0, False

    def close(self):
        self.stop()
        self.backend.close()
