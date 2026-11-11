"""게임의 효과음 타이밍을 오프라인 WAV로 합성한다. 스피커 재생은 하지 않는다."""

import argparse
from array import array
from pathlib import Path
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from game.story import PANEL_DURATIONS
from game.story_audio import AUDIO_ROOT, CUES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--montage", action="store_true", help="효과음 종류별 짧은 미리듣기")
    args = parser.parse_args()
    if args.montage:
        events = ((.10, "hero_arrival"), (1.65, "dungeon_collapse"), (4.0, "boss_bark"),
                  (5.15, "step_left"), (5.65, "step_right"), (6.15, "step_left"), (6.80, "worker_sigh"))
        duration = 8.4
    else:
        events = [(sum(PANEL_DURATIONS[:index]) + time, name)
                  for index, cues in enumerate(CUES) for time, name in cues]
        duration = sum(PANEL_DURATIONS)
    rate = 44100
    mixed = [0] * round(duration * rate * 2)
    for time, name in events:
        with wave.open(str(AUDIO_ROOT / f"{name}.wav")) as source:
            assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (2, 2, rate)
            samples = array('h', source.readframes(source.getnframes()))
        offset = round(time * rate) * 2
        for index, value in enumerate(samples):
            if offset + index < len(mixed):
                mixed[offset + index] += round(value * 78 / 128)
    assert max(map(abs, mixed)) < 32767
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(array('h', mixed).tobytes())
    print(f"Saved {args.output}: {duration:g}s, {len(events)} cues, peak {max(map(abs, mixed)) / 32767:.3f}")


if __name__ == "__main__":
    main()
