"""원본 OGG/MP3/FLAC을 SDL_mixer로 PCM 변환한다. 소리를 재생하거나 창을 열지 않는다."""

import ctypes
import hashlib
import json
import os
from pathlib import Path
import wave

os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pico2d.pico2d as p

ROOT = Path(__file__).resolve().parents[2] / "assets/audio_story_v2"


def main():
    entries = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["sources"]
    p.SDL_Init(p.SDL_INIT_AUDIO)
    if p.Mix_OpenAudio(44100, p.AUDIO_S16SYS, 2, 1024) != 0:
        p.SDL_Quit()
        raise RuntimeError("PCM 변환용 dummy 오디오 초기화 실패")
    try:
        assert p.SDL_GetCurrentAudioDriver() == b"dummy"
        for entry in entries.values():
            source, output = ROOT / entry["original"], ROOT / entry["pcm"]
            assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["original_sha256"]
            chunk = p.Mix_LoadWAV(str(source).encode("utf-8"))
            if not chunk:
                raise RuntimeError(f"효과음 디코딩 실패: {source}")
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                with wave.open(str(output), "wb") as sound:
                    sound.setnchannels(2)
                    sound.setsampwidth(2)
                    sound.setframerate(44100)
                    sound.writeframes(ctypes.string_at(chunk.contents.abuf, chunk.contents.alen))
            finally:
                p.Mix_FreeChunk(chunk)
        print(f"Decoded {len(entries)} sources without playback.")
    finally:
        p.Mix_CloseAudio()
        p.SDL_Quit()


if __name__ == "__main__":
    main()
