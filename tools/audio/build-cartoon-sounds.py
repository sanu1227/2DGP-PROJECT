"""공개 음원을 편집·겹쳐 슬랩스틱 효과음을 만든다. 개발용 NumPy/SciPy 필요."""

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import wave

import numpy as np
from scipy.signal import resample_poly


RATE = 44100
ROOT = Path(__file__).resolve().parents[2] / "assets/audio_story_v2"
SOURCES = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["sources"]


def source(name, speed=1):
    with wave.open(str(ROOT / SOURCES[name]["pcm"]), "rb") as sound:
        assert (sound.getnchannels(), sound.getsampwidth(), sound.getframerate()) == (2, 2, RATE)
        data = np.frombuffer(sound.readframes(sound.getnframes()), dtype="<i2").reshape(-1, 2).astype(float) / 32768
    data -= data.mean(axis=0)
    # 파일의 여백만 제거한다. 실제 날숨이나 잔향은 낮은 문턱값으로 보존한다.
    active = np.flatnonzero(np.max(np.abs(data), axis=1) > .003)
    if not len(active):
        raise ValueError(f"무음 원본: {name}")
    data = data[max(0, active[0] - 88):min(len(data), active[-1] + 882)]
    if speed != 1:
        ratio = Fraction(1 / speed).limit_denominator(1000)
        data = resample_poly(data, ratio.numerator, ratio.denominator, axis=0)
    data /= np.max(np.abs(data))
    return data


def build(name, length, layers, peak):
    mixed = np.zeros((round(length * RATE), 2))
    for layer in layers:
        clip = source(layer["source"], layer.get("speed", 1))
        if "length" in layer:
            clip = clip[:round(layer["length"] * RATE)]
        clip = clip.copy()
        n = len(clip)
        clip *= (np.minimum(1, np.arange(n) / (RATE * .003))
                 * np.minimum(1, (n - 1 - np.arange(n)) / (RATE * .035)))[:, None]
        pan = layer.get("pan", 0)
        clip *= np.array([1 - max(0, pan), 1 + min(0, pan)]) * layer["gain"]
        start = round(layer["start"] * RATE)
        count = min(len(clip), len(mixed) - start)
        mixed[start:start + count] += clip[:count]
    # 가볍게 압축해 순간적인 충돌음만 지나치게 튀지 않게 한다.
    mixed = np.tanh(mixed * 1.15)
    mixed *= peak / np.max(np.abs(mixed))
    n = len(mixed)
    mixed *= (np.minimum(1, np.arange(n) / (RATE * .004))
              * np.minimum(1, (n - 1 - np.arange(n)) / (RATE * .07)))[:, None]
    pcm = np.round(mixed * 32767).astype("<i2")
    output = ROOT / f"{name}.wav"
    with wave.open(str(output), "wb") as sound:
        sound.setnchannels(2)
        sound.setsampwidth(2)
        sound.setframerate(RATE)
        sound.writeframes(pcm.tobytes())
    return {"file": output.name, "seconds": length, "peak": float(np.max(np.abs(mixed))),
            "rms": float(np.sqrt(np.mean(mixed ** 2))),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "layers": layers}


def layer(source, start, gain, speed=1, **extra):
    return dict(source=source, start=start, gain=gain, speed=speed, **extra)


def main():
    clips = {}
    clips["hero_arrival"] = build("hero_arrival", 1.15, [
        layer("jingles_HIT00", 0, .20),
        layer("jingles_SAX00", 0, .70, .92),
        layer("jingles_SAX00", .18, .68, 1.10),
        layer("jingles_SAX00", .37, .82, 1.38),
    ], .62)
    clips["dungeon_collapse"] = build("dungeon_collapse", 2.05, [
        layer("impactWood_heavy_000", 0, .74, .88),
        layer("impactMetal_heavy_000", .015, .54, .85),
        layer("impactGlass_heavy_000", .075, .52, .92),
        layer("metalPot1", .03, .46, 1.20),
        layer("impactTin_medium_000", .24, .46, 1.05, pan=-.20),
        layer("impactWood_heavy_000", .39, .36, 1.20, pan=.18),
        layer("impactMetal_heavy_000", .57, .29, 1.28, pan=-.15),
        layer("impactGlass_heavy_000", .73, .25, 1.34, pan=.13),
        layer("impactTin_medium_000", .94, .22, 1.45),
        layer("BounceYoFrankie", 1.16, .25, .78),
        layer("impactTin_medium_000", 1.59, .13, 1.65, pan=.08),
    ], .64)
    clips["boss_bark"] = build("boss_bark", .71, [
        layer("qubodup-shout", 0, .95, .75),
        layer("impactWood_heavy_000", .015, .15, 1.35),
    ], .58)
    for name, foot, cloth, speed, pan in (
            ("step_left", "footstep_concrete_000", "cloth1", 1.02, -.07),
            ("step_right", "footstep_concrete_001", "cloth2", 1.15, .07)):
        clips[name] = build(name, .36, [
            layer(foot, 0, .70, .85, pan=pan),
            layer(cloth, .018, .18, length=.27),
            layer("BounceYoFrankie", .045, .25, speed, pan=pan),
        ], .38)
    clips["worker_sigh"] = build("worker_sigh", 1.50, [
        layer("wjtaylor-sigh", 0, .92),
        layer("jingles_SAX10", .52, .21, .92),
    ], .50)
    manifest = {"authoring": "Edited licensed recordings and musical/game samples; original sources retained",
                "format": "44100 Hz, stereo, signed 16-bit PCM", "clips": clips}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {key: entry[key] for key in ("seconds", "peak", "rms")} for name, entry in clips.items()}))


if __name__ == "__main__":
    main()
