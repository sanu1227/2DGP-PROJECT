"""표준 라이브러리로 만드는 오리지널 만화 효과음. 재생하지 않고 WAV만 쓴다."""

import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave


RATE = 44100
ROOT = Path(__file__).resolve().parents[2] / "assets/audio_story_v1"
TAU = math.tau


def fade(t, length, attack=.015, release=.08):
    return min(1, t / attack) * min(1, max(0, (length - t) / release))


def echo(values, taps):
    result = list(values)
    for seconds, gain in taps:
        delay = round(seconds * RATE)
        for i in range(delay, len(result)):
            result[i] += values[i - delay] * gain
    return result


def hero():
    length = 1.25
    notes = ((0, .22, 293.66), (.19, .23, 440), (.39, .63, 587.33),
             (.39, .63, 369.99), (.39, .63, 440))
    data = []
    for i in range(round(length * RATE)):
        t, value = i / RATE, 0
        for start, duration, pitch in notes:
            u = t - start
            if 0 <= u < duration:
                brass = sum(math.sin(TAU * pitch * h * u) / h ** 1.35 for h in range(1, 10))
                value += brass * fade(u, duration, .025, .12) * .20
        if t < .23:
            value += math.sin(TAU * (94 * t - 90 * t * t)) * math.exp(-t * 22) * .32
        data.append(value)
    return echo(data, ((.085, .18), (.16, .08)))


def boss():
    rng = random.Random(934)
    length, phase, noise = .82, 0, 0
    data = []
    for i in range(round(length * RATE)):
        t = i / RATE
        q = t / length
        phase += TAU * (112 - 32 * q + 6 * math.sin(TAU * 7 * t)) / RATE
        # 낮은 성대 진동과 움직이는 모음 공명으로 만든 말 없는 코믹한 호통.
        voiced = sum(math.sin(phase * h) * (math.exp(-((h * 95 - (650 - 240 * q)) / 210) ** 2)
                     + .4 * math.exp(-((h * 95 - 1250) / 300) ** 2)) / h ** .55
                     for h in range(1, 23))
        noise += .2 * (rng.uniform(-1, 1) - noise)
        shape = fade(t, length, .025, .20) * (.85 + .15 * math.sin(TAU * 23 * t))
        data.append((voiced * .28 + noise * .17) * shape)
    return echo(data, ((.075, .18),))


def foot(seed):
    rng = random.Random(seed)
    length, low, slow = .29, 0, 0
    data = []
    for i in range(round(length * RATE)):
        t = i / RATE
        noise = rng.uniform(-1, 1)
        low += .21 * (noise - low)
        slow += .035 * (noise - slow)
        scrape = (low - slow) * math.exp(-t * 12) * .42
        thump = math.sin(TAU * (98 * t - 66 * t * t)) * math.exp(-t * 30) * .50
        grit = noise * math.exp(-((t - .07) / .035) ** 2) * .035
        data.append((scrape + thump + grit) * fade(t, length, .003, .055))
    return data


def sigh():
    rng = random.Random(382)
    length, fast, slow, phase = 1.2, 0, 0, 0
    data = []
    for i in range(round(length * RATE)):
        t, q = i / RATE, i / (length * RATE)
        noise = rng.uniform(-1, 1)
        fast += .22 * (noise - fast)
        slow += .045 * (noise - slow)
        phase += TAU * (142 - 56 * q) / RATE
        breath = (fast - slow) * .85
        throat = (math.sin(phase) + .27 * math.sin(phase * 3)) * .045 * (1 - q)
        envelope = math.sin(pi_safe(q)) ** .85 * (1 - .55 * q)
        data.append((breath + throat) * envelope * fade(t, length, .06, .2))
    return data


def pi_safe(q):
    return math.pi * min(1, max(0, q))


def write(name, data, peak, pan=0):
    scale = peak / max(abs(x) for x in data)
    data = [x * scale * fade(i / RATE, len(data) / RATE, .004, .025) for i, x in enumerate(data)]
    frames = bytearray()
    for value in data:
        frames += struct.pack('<hh', round(value * (1 - max(0, pan)) * 32767),
                              round(value * (1 + min(0, pan)) * 32767))
    path = ROOT / f"{name}.wav"
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(frames)
    assert max(abs(x) for x in data) < .7
    return {"file": path.name, "seconds": len(data) / RATE, "peak": max(abs(x) for x in data),
            "rms": math.sqrt(sum(x * x for x in data) / len(data)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    clips = {"hero_arrival": write("hero_arrival", hero(), .56),
             "boss_bark": write("boss_bark", boss(), .58),
             "step_left": write("step_left", foot(14), .32, -.08),
             "step_right": write("step_right", foot(37), .30, .08),
             "worker_sigh": write("worker_sigh", sigh(), .36)}
    manifest = {"authoring": "Original procedural synthesis; no recordings or third-party samples",
                "format": "44100 Hz, stereo, signed 16-bit PCM", "seeded": True, "clips": clips}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({name: {key: clip[key] for key in ('seconds', 'peak', 'rms')} for name, clip in clips.items()}))


if __name__ == '__main__':
    main()
