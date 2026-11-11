"""고정 배경 위에 투명 캐릭터 포즈와 숨 효과를 독립적으로 그린다."""

import json
from math import pi, sin
from pathlib import Path

from game.character_motion import MOTION_END, smooth, worker_motion


MOTION_ROOT = Path(__file__).resolve().parents[1] / "assets/comic_motion_v1"
MANIFEST = json.loads((MOTION_ROOT / "manifest.json").read_text(encoding="utf-8"))
MOTION_IMAGES = {"motion_backgrounds": MOTION_ROOT / "sources/backgrounds.png",
                 **{f"motion_{name}": MOTION_ROOT / sprite["file"]
                    for name, sprite in MANIFEST["sprites"].items()}}


def draw_sprite(load_image, name, x, y, *, height=None, scale=None,
                rotation=0, stretch=1, opacity=1, center=False):
    image = load_image(f"motion_{name}")
    bounds = MANIFEST["sprites"][name]["bounds"]
    if scale is None:
        scale = height / bounds["height"]
    anchor = MANIFEST["worker_anchor"] if name.removeprefix("worker_").isdigit() else MANIFEST["cast_anchor"]
    if center:
        anchor = (bounds["left"] + bounds["width"] / 2, bounds["top"] + bounds["height"] / 2)
    sy = scale * stretch
    image.opacify(opacity)
    try:
        image.clip_composite_draw(0, 0, image.w, image.h, rotation, "",
                                  x + (image.w / 2 - anchor[0]) * scale,
                                  y + (anchor[1] - image.h / 2) * sy,
                                  image.w * scale, image.h * sy)
    finally:
        image.opacify(1)


def draw_actors(load_image, bounds, age, index, opacity):
    left, bottom, right, _ = bounds
    width = right - left
    t = min(max(0, age), MOTION_END)

    def actor(name, x, y, **kwargs):
        draw_sprite(load_image, name, left + width * x, bottom + y, opacity=opacity, **kwargs)

    if index == 0:
        entrance = smooth(t / 1.6)
        actor("hero_enter", .23 + .09 * entrance, 38, height=280,
              rotation=.025 * sin(t * 7) * (1 - entrance))
        shiver = sin(t * 25) * max(0, 1 - t / 3)
        actor("skeleton_guard", .80 + shiver * .004, 40, height=245,
              rotation=shiver * .015)
    elif index == 1:
        leave = smooth(t / 2.8)
        actor("hero_leave", .35 - .13 * leave, 82 + 24 * leave + sin(t * 12) * (1 - leave) * 2,
              height=220 - 22 * leave)
        surprise = sin(t * 15) * max(0, 1 - t / 2.6)
        actor("skeleton_broken", .77, 38, height=180, rotation=surprise * .025)
    elif index == 2:
        reaction = sin(t * 12) * max(0, 1 - t / 2.6)
        actor("skeleton_broken", .79, 36, height=157, rotation=reaction * .02)
        motion = worker_motion(t)
        actor(f"worker_{motion.frame:02d}", motion.x, 46 + motion.bob,
              scale=.75, stretch=motion.stretch)
        if motion.breath is not None:
            progress = motion.breath
            alpha = min(1, progress * 7) * (1 - progress) ** .6
            draw_sprite(load_image, "breath", left + width * motion.x + 44 + progress * 64,
                        bottom + 188 + progress * 22, height=19 + progress * 28,
                        center=True, opacity=opacity * alpha)
    else:
        bark = sin(max(0, t - .45) * 12) * max(0, 1 - t / 2.8)
        actor("skeleton_skull", .91, 136, height=62,
              rotation=sin(t * 9) * max(0, 1 - t / 3) * .05)
        actor("boss", .26, 22, height=280, stretch=1 + bark * .025, rotation=bark * .018)
        cower = smooth((t - .5) / 1.5)
        actor("worker_cower", .77, 30, height=232, stretch=1 - .035 * cower,
              rotation=.035 * cower)
