"""독립 이미지 레이어로 구성한 움직이는 던전 타이틀."""

from ctypes import byref, c_int, c_ubyte
from dataclasses import dataclass
import json
from math import sin, pi
from pathlib import Path

from game.character_motion import clamp, smooth
from game.layout import WIDTH, HEIGHT


TITLE_ROOT = Path(__file__).resolve().parents[1] / "assets/title_motion_v1"
MANIFEST = json.loads((TITLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
GESTURE_ROOT = TITLE_ROOT.parent / "title_gestures_v2"
GESTURES = json.loads((GESTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
SPRITES = {**MANIFEST["sprites"], **GESTURES["sprites"]}
TITLE_IMAGES = {"title_background": TITLE_ROOT / "sources/background.png",
                **{f"title_{name}": TITLE_ROOT / sprite["file"] for name, sprite in MANIFEST["sprites"].items()},
                **{f"title_{name}": GESTURE_ROOT / sprite["file"] for name, sprite in GESTURES["sprites"].items()}}
WAVE_PERIOD = 3.2
BLINK_PERIOD = 3.0


@dataclass(frozen=True)
class TitleMotion:
    background_x: float
    background_y: float
    logo_scale: float
    logo_y: float
    skeleton: int
    worker: int
    worker_dip: float
    flame: int


def sample_title(age):
    t = max(0, age)
    q = clamp(t / 1.1) - 1
    arrival = 1 + 2.70158 * q ** 3 + 1.70158 * q ** 2
    wave = (t % WAVE_PERIOD) - .25
    skeleton = (0, 1, 2, 3, 4, 3, 4, 5, 6, 7)[min(9, int(wave / .18))] if 0 <= wave < 1.8 else 0
    blink = t % BLINK_PERIOD
    worker, dip = 0, 0.0
    # 첫 인사부터 보이는 느린 깜박임과 짧은 두 번째 깜박임.
    for close, shut, opening, end in ((.65, .78, 1.13, 1.26), (1.40, 1.52, 1.72, 1.84)):
        if close <= blink < end:
            worker = 1 if blink < shut else 2 if blink < opening else 3
            dip = smooth((blink - close) / (shut - close)) * (1 - smooth((blink - opening) / (end - opening)))
            break
    return TitleMotion(sin(t * .24) * 6, sin(t * .19) * 3, .88 + .12 * arrival,
                       600 + 45 * (1 - arrival) + sin(t * 1.05) * 4 * smooth((t - 1.1) / 1),
                       skeleton, worker, dip, int(t * 12) % 8)


def draw_title(load_image, age):
    import pico2d.pico2d as p

    motion = sample_title(age)
    bgx, bgy = motion.background_x, motion.background_y
    load_image("title_background").draw(WIDTH / 2 + bgx, HEIGHT / 2 + bgy, WIDTH + 24, HEIGHT + 24)

    def sprite(name, x, floor, scale, stretch=1):
        entry = SPRITES[name]
        image = load_image(f"title_{name}")
        ax, ay = entry["anchor"]
        image.draw(x + (image.w / 2 - ax) * scale,
                   floor + (ay - image.h / 2) * scale * stretch,
                   image.w * scale, image.h * scale * stretch)

    blend, rgba = c_int(), [c_ubyte() for _ in range(4)]
    p.SDL_GetRenderDrawBlendMode(p.renderer, byref(blend))
    p.SDL_GetRenderDrawColor(p.renderer, *(byref(value) for value in rgba))
    p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
    try:
        for side, nx in enumerate((.065, .946)):
            x = WIDTH / 2 + bgx + (nx - .5) * (WIDTH + 24)
            floor = HEIGHT / 2 + bgy + (.5 - .278) * (HEIGHT + 24)
            flicker = .8 + .2 * sin(age * 11 + side * 2)
            for radius, alpha in ((60, 7), (42, 10), (25, 15)):
                p.draw_circle(x, floor + 40, radius, 255, 158, 48, round(alpha * flicker), filled=True)
            sprite(f"flame_{(motion.flame + side * 3) % 8}", x, floor, .28)
            for mote in range(5):
                phase = (age * .45 + mote * .21 + side * .17) % 1
                px = x + sin(phase * 8 + mote) * (6 + phase * 17)
                py = floor + 48 + phase * 110
                p.draw_circle(px, py, 1 + mote % 2, 255, 206, 91, round(170 * (1 - phase)), filled=True)

        # 손짓·깜박임은 포즈를 바꾸고, 호흡은 발을 고정한 작은 상체 높이 변화로 표현한다.
        sprite(f"wave_{motion.skeleton}", 250, 72, .96)
        sprite(f"worker_{motion.worker}", 1350, 72, 1.10,
               1 + sin(age * 1.8) * .006 - .018 * motion.worker_dip)
        logo = load_image("title_logo")
        logo.draw(800, motion.logo_y, 1050 * motion.logo_scale,
                  1050 * logo.h / logo.w * motion.logo_scale)

        for index in range(12):
            phase = (age * .065 + index * .083) % 1
            x = 320 + index * 85 + sin(age * .4 + index) * 12
            y = 300 + phase * 550
            alpha = round(95 * sin(pi * phase))
            p.draw_circle(x, y, 1 + index % 2, 180, 229, 219, alpha, filled=True)
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, blend.value)
        p.SDL_SetRenderDrawColor(p.renderer, *(value.value for value in rgba))
