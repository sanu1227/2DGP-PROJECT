"""장치 스프라이트의 알파를 따라 화면 픽셀 단위 윤곽선을 만든다."""

from ctypes import string_at
from math import degrees

import pico2d.pico2d as p


RADIUS = 3
GLOW_RADIUS = 18
OUTLINE_COLOR = (135, 225, 231)
PALETTE = (bytes(4), bytes((25, 32, 41, 255)), bytes((255, 255, 255, 255)))


def sprite_mask(alpha, atlas_width, clip, width, height, padding):
    left, top, source_width, source_height = clip
    stride = width + 2 * padding
    solid = bytearray(stride * (height + 2 * padding))
    columns = [left + (2 * x + 1) * source_width // (2 * width) for x in range(width)]
    for y in range(height):
        start = (y + padding) * stride + padding
        source = (top + (2 * y + 1) * source_height // (2 * height)) * atlas_width
        solid[start:start + width] = bytes(alpha[source + x] >= 128 for x in columns)
    return solid, stride


def outline_pixels(alpha, atlas_width, clip, width, height):
    solid, stride = sprite_mask(alpha, atlas_width, clip, width, height, RADIUS)
    # 가장자리에서 밝은 선을 두르고, 바깥 한 겹은 어둡게 눌러 밝은 바닥과 분리한다.
    offsets = [(dy * stride + dx, 2 if dx * dx + dy * dy <= 4 else 1)
               for dy in range(-RADIUS, RADIUS + 1) for dx in range(-RADIUS, RADIUS + 1)
               if 0 < dx * dx + dy * dy <= RADIUS * RADIUS]
    border = bytearray(len(solid))
    for i, opaque in enumerate(solid):
        if not opaque or (solid[i - 1] and solid[i + 1] and solid[i - stride] and solid[i + stride]):
            continue
        for offset, shade in offsets:
            j = i + offset
            if not solid[j] and border[j] < shade:
                border[j] = shade
    return b"".join(PALETTE[shade] for shade in border)


def glow_pixels(alpha, atlas_width, clip, width, height):
    """불투명 실루엣까지의 거리를 두 번 훑어 바깥쪽 빛을 만든다."""
    solid, stride = sprite_mask(alpha, atlas_width, clip, width, height, GLOW_RADIUS)
    rows = len(solid) // stride
    limit = 3 * GLOW_RADIUS
    distances = [0 if opaque else limit for opaque in solid]
    for step, ys, xs in ((1, range(1, rows - 1), range(1, stride - 1)),
                         (-1, range(rows - 2, 0, -1), range(stride - 2, 0, -1))):
        for y in ys:
            for x in xs:
                i = y * stride + x
                if not solid[i]:
                    vertical = i - step * stride
                    distances[i] = min(distances[i], distances[i - step] + 3, distances[vertical] + 3,
                                       distances[vertical - 1] + 4, distances[vertical + 1] + 4)
    pixels = bytearray(b"\xff\xff\xff\x00" * len(solid))
    pixels[3::4] = bytes(round(178 * (1 - distance / limit) ** 2) if distance else 0
                        for distance in distances)
    return bytes(pixels)


class DeviceOutlines:
    def __init__(self):
        self.alpha = {}
        self.textures = {}

    def atlas_alpha(self, path):
        if path not in self.alpha:
            source = p.IMG_Load(str(path).encode("utf-8"))
            if not source:
                raise RuntimeError(f"장치 아틀라스를 읽지 못했습니다: {path}")
            try:
                rgba = p.SDL_ConvertSurfaceFormat(source, p.SDL_PIXELFORMAT_RGBA32, 0)
                if not rgba:
                    raise RuntimeError("장치 아틀라스의 알파를 변환하지 못했습니다.")
                try:
                    surface = rgba.contents
                    alpha = b"".join(string_at(surface.pixels + y * surface.pitch, surface.w * 4)[3::4]
                                     for y in range(surface.h))
                    self.alpha[path] = surface.w, alpha
                finally:
                    p.SDL_FreeSurface(rgba)
            finally:
                p.SDL_FreeSurface(source)
        return self.alpha[path]

    def draw(self, path, clip, rect, angle, opacity, color=OUTLINE_COLOR, *, glow=0):
        if rect.w < 1 or rect.h < 1:
            return
        if round(255 * glow):
            self.draw_layer(path, clip, rect, angle, glow, color, GLOW_RADIUS, glow_pixels)
        self.draw_layer(path, clip, rect, angle, opacity, color, RADIUS, outline_pixels)

    def draw_layer(self, path, clip, rect, angle, opacity, color, padding, make_pixels):
        key = path, clip, rect.w, rect.h, padding
        width, height = rect.w + 2 * padding, rect.h + 2 * padding
        if key not in self.textures:
            atlas_width, alpha = self.atlas_alpha(path)
            pixels = make_pixels(alpha, atlas_width, clip, rect.w, rect.h)
            surface = p.SDL_CreateRGBSurfaceWithFormatFrom(pixels, width, height, 32, width * 4,
                                                         p.SDL_PIXELFORMAT_RGBA32)
            if not surface:
                raise RuntimeError("장치 윤곽선 이미지를 만들지 못했습니다.")
            try:
                texture = p.SDL_CreateTextureFromSurface(p.renderer, surface)
                if not texture:
                    raise RuntimeError("장치 윤곽선 텍스처를 만들지 못했습니다.")
                self.textures[key] = texture
            finally:
                p.SDL_FreeSurface(surface)
        frame = p.SDL_Rect(rect.x - padding, rect.y - padding, width, height)
        texture = self.textures[key]
        p.SDL_SetTextureColorMod(texture, *color)
        p.SDL_SetTextureAlphaMod(texture, round(255 * opacity))
        p.SDL_RenderCopyEx(p.renderer, texture, None, frame, degrees(-angle), None, p.SDL_FLIP_NONE)

    def close(self):
        for texture in self.textures.values():
            p.SDL_DestroyTexture(texture)
        self.textures.clear()
        self.alpha.clear()
