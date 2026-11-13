"""화면에 맞는 BGM을 SDL의 음악 스트림 하나로 반복 재생한다."""

from pathlib import Path
import warnings


BGM_ROOT = Path(__file__).resolve().parents[1] / "bgm"
TRACKS = {
    "title": BGM_ROOT / "Dungeon Title Theme.mp3",
    "playing": BGM_ROOT / "Interlocking Gears.mp3",
}
SCREEN_TRACKS = {"title": "title", "controls": "title", "playing": "playing"}
# SDL 음악 음량 범위는 0~128. 안내·일시정지에서는 플레이 음량을 절반으로 낮춘다.
VOLUMES = {"title": 48, "playing": 40}
FADE_IN_MS = 500


class BackgroundMusic:
    def __init__(self):
        self.tracks = {}
        self.current = None
        self.volume = None
        self.failed = set()

    def update(self, screen, *, quiet=False):
        import pico2d.pico2d as p

        target = SCREEN_TRACKS.get(screen)
        if target is None:
            self.stop()
            return
        volume = VOLUMES[target]
        if target == "playing" and quiet:
            volume //= 2
        if target == self.current:
            if volume != self.volume:
                self.tracks[target].set_volume(volume)
                self.volume = volume
            return

        self.stop()
        if target in self.failed:
            return
        try:
            if not p.Mix_QuerySpec(None, None, None):
                raise OSError("SDL audio device unavailable")
            if target not in self.tracks:
                self.tracks[target] = p.load_music(str(TRACKS[target]))
            music = self.tracks[target]
            music.set_volume(volume)
            if p.Mix_FadeInMusic(music.music, -1, FADE_IN_MS) < 0:
                raise OSError(p.Mix_GetError())
        except OSError as error:
            self.failed.add(target)
            warnings.warn(f"BGM을 사용할 수 없어 무음으로 진행합니다 ({TRACKS[target].name}): {error}",
                          RuntimeWarning)
            return
        self.current, self.volume = target, volume

    def stop(self):
        if self.current is not None:
            import pico2d.pico2d as p

            p.Mix_HaltMusic()
        self.current, self.volume = None, None

    def close(self):
        self.stop()
        # pico2d.Music의 해제는 SDL 오디오 장치가 닫히기 전에 끝낸다.
        self.tracks.clear()
