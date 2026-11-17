"""장치 스프라이트의 알파를 따라 화면 픽셀 단위 윤곽선을 만든다."""

from ctypes import string_at
from math import degrees

import pico2d.pico2d as p


RADIUS = 3
OUTLINE_COLOR = (135, 225, 231)
PALETTE = (bytes(4), bytes((25, 32, 41, 255)), bytes((255, 255, 255, 255)))


def outline_pixels(alpha, atlas_width, clip, width, height):
    left, top, source_width, source_height = clip
    stride = width + 2 * RADIUS
    solid = bytearray(stride * (height + 2 * RADIUS))
    columns = [left + (2 * x + 1) * source_width // (2 * width) for x in range(width)]
    for y in range(height):
        start = (y + RADIUS) * stride + RADIUS
        source = (top + (2 * y + 1) * source_height // (2 * height)) * atlas_width
        solid[start:start + width] = bytes(alpha[source + x] >= 128 for x in columns)

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

    def draw(self, path, clip, rect, angle, opacity, color=OUTLINE_COLOR):
        if rect.w < 1 or rect.h < 1:
            return
        key = path, clip, rect.w, rect.h
        if key not in self.textures:
            atlas_width, alpha = self.atlas_alpha(path)
            pixels = outline_pixels(alpha, atlas_width, clip, rect.w, rect.h)
            width, height = rect.w + 2 * RADIUS, rect.h + 2 * RADIUS
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
        frame = p.SDL_Rect(rect.x - RADIUS, rect.y - RADIUS, rect.w + 2 * RADIUS, rect.h + 2 * RADIUS)
        texture = self.textures[key]
        p.SDL_SetTextureColorMod(texture, *color)
        p.SDL_SetTextureAlphaMod(texture, round(255 * opacity))
        p.SDL_RenderCopyEx(p.renderer, texture, None, frame, degrees(-angle), None, p.SDL_FLIP_NONE)

    def close(self):
        for texture in self.textures.values():
            p.SDL_DestroyTexture(texture)
        self.textures.clear()
        self.alpha.clear()
