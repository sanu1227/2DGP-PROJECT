"""학교 시그니처와 2DGP 일러스트를 차례로 재생하는 시작 로고 모드."""

from ctypes import byref, c_int, c_ubyte
from dataclasses import dataclass
import json
from pathlib import Path

from game.layout import WIDTH, HEIGHT


ROOT = Path(__file__).resolve().parents[1] / "assets/splash_v1"
MOTION_ROOT = ROOT.parent / "splash_motion_v1"
SPRITES = json.loads((MOTION_ROOT / "manifest.json").read_text(encoding="utf-8"))["sprites"]
LOGO_IMAGES = {"logo_university": ROOT / "tukorea.png",
               "logo_workshop": MOTION_ROOT / "sources/background.png",
               **{f"logo_{name}": MOTION_ROOT / entry["file"] for name, entry in SPRITES.items()}}
LOGO_DURATIONS = (2.2, 2.6)
FADE_SECONDS = .35
LETTER_STARTS = (.12, .70)
LETTER_HEIGHT = 280


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


@dataclass(frozen=True)
class LetterMotion:
    opacity: float
    scale: float
    x: float
    y: float


def sample_letter(age, index):
    local = age - LETTER_STARTS[index]
    progress = max(0.0, min(1.0, local / .55))
    q = progress - 1
    arrival = 1 + 2.70158 * q ** 3 + 1.70158 * q ** 2
    return LetterMotion(smooth(local / .14), .86 + .14 * arrival,
                        (-55 if index == 0 else 55) * (1 - arrival), 24 * (1 - arrival))


@dataclass
class LogoPlayback:
    elapsed: float = 0.0

    @property
    def finished(self):
        return self.elapsed >= sum(LOGO_DURATIONS)

    @property
    def index(self):
        return 0 if self.elapsed < LOGO_DURATIONS[0] else 1

    @property
    def age(self):
        return self.elapsed - (LOGO_DURATIONS[0] if self.index else 0)

    @property
    def opacity(self):
        remaining = LOGO_DURATIONS[self.index] - self.age
        return smooth(self.age / FADE_SECONDS) * smooth(remaining / FADE_SECONDS)

    def update(self, delta):
        self.elapsed = min(sum(LOGO_DURATIONS), self.elapsed + max(0.0, delta))

    def advance(self):
        self.elapsed = LOGO_DURATIONS[0] if self.index == 0 else sum(LOGO_DURATIONS)


def fade_to_black(opacity):
    """다른 화면에 SDL 합성 모드나 색이 남지 않는 전체 화면 페이드."""
    import pico2d.pico2d as p

    alpha = round(max(0, min(1, opacity)) * 255)
    if not alpha:
        return
    blend, rgba = c_int(), [c_ubyte() for _ in range(4)]
    p.SDL_GetRenderDrawBlendMode(p.renderer, byref(blend))
    p.SDL_GetRenderDrawColor(p.renderer, *(byref(value) for value in rgba))
    try:
        p.SDL_SetRenderDrawBlendMode(p.renderer, p.SDL_BLENDMODE_BLEND)
        p.SDL_SetRenderDrawColor(p.renderer, 0, 0, 0, alpha)
        p.SDL_RenderFillRect(p.renderer, None)
    finally:
        p.SDL_SetRenderDrawBlendMode(p.renderer, blend.value)
        p.SDL_SetRenderDrawColor(p.renderer, *(value.value for value in rgba))


def draw_logos(load_image, playback):
    import pico2d.pico2d as p

    if playback.index == 0:
        p.draw_rectangle(0, 0, WIDTH, HEIGHT, 255, 255, 255, filled=True)
        logo = load_image("logo_university")
        logo.draw(WIDTH / 2, HEIGHT / 2, 620, 620 * logo.h / logo.w)
    else:
        illustration = load_image("logo_workshop")
        # 일러스트 전체가 조금씩 가까워지고 공식 학교 시그니처는 고정한다.
        zoom = 1 + .025 * smooth(playback.age / LOGO_DURATIONS[1])
        scale = max(WIDTH / illustration.w, HEIGHT / illustration.h) * zoom
        illustration.draw(WIDTH / 2, HEIGHT / 2, illustration.w * scale, illustration.h * scale)
        widths = [SPRITES[name]["bounds"]["width"] / SPRITES[name]["bounds"]["height"] * LETTER_HEIGHT
                  for name in ("2d", "gp")]
        left = (WIDTH - sum(widths) - 18) / 2
        for index, name in enumerate(("2d", "gp")):
            motion = sample_letter(playback.age, index)
            center = left + widths[index] / 2
            left += widths[index] + 18
            if not motion.opacity:
                continue
            image = load_image(f"logo_{name}")
            bounds = SPRITES[name]["bounds"]
            scale = LETTER_HEIGHT / bounds["height"] * motion.scale * zoom
            cx = bounds["left"] + bounds["width"] / 2
            cy = bounds["top"] + bounds["height"] / 2
            x = WIDTH / 2 + (center - WIDTH / 2 + motion.x) * zoom
            y = HEIGHT / 2 + (515 - HEIGHT / 2 + motion.y) * zoom
            alpha = c_ubyte()
            p.SDL_GetTextureAlphaMod(image.texture, byref(alpha))
            try:
                p.SDL_SetTextureAlphaMod(image.texture, round(alpha.value * motion.opacity))
                image.draw(x + (image.w / 2 - cx) * scale, y + (cy - image.h / 2) * scale,
                           image.w * scale, image.h * scale)
            finally:
                p.SDL_SetTextureAlphaMod(image.texture, alpha.value)
    fade_to_black(1 - playback.opacity)
