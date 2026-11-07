"""프로젝트 경로에서 아틀라스를 한 번 로드하고 바닥 기준점에 맞춰 그린다."""

import ctypes
import json
from pathlib import Path

import pico2d.pico2d as p


ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "art_v1"


class Art:
    def __init__(self):
        self.atlases = {}
        try:
            self.manifest = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
            for name, entry in self.manifest["atlases"].items():
                self.atlases[name] = p.load_image(str(ART_ROOT / entry["file"]))
        except Exception:
            self.close()
            raise

    def close(self):
        # Image 소멸자가 SDL 텍스처를 해제한다. close_canvas()보다 먼저 호출한다.
        self.atlases.clear()

    def ground(self, name, sx, sy, width, height, tint=(255, 255, 255)):
        """바닥 상면만 새 직사각형 격자에 투영한다. 원본 PNG는 변경하지 않는다."""
        entry = self.manifest["sprites"][name]
        atlas = self.manifest["atlases"][entry["atlas"]]
        left, bottom, _, _ = entry["clip_rect_pico2d"]
        top = atlas["height"] - bottom - entry["height"]
        # 마름모의 북·동·남·서 꼭짓점을 새 칸의 좌상·우상·우하·좌하에 대응한다.
        source = ((128, 104), (240, 160), (128, 216), (16, 160))
        target = ((sx - width / 2, sy + height / 2), (sx + width / 2, sy + height / 2),
                  (sx + width / 2, sy - height / 2), (sx - width / 2, sy - height / 2))
        vertices = (p.SDL_Vertex * 4)()
        output_height = ctypes.c_int()
        p.SDL_GetRendererOutputSize(p.renderer, None, ctypes.byref(output_height))
        for vertex, (u, v), (x, y) in zip(vertices, source, target):
            vertex.position = p.SDL_FPoint(x, output_height.value - y)
            # RenderGeometry는 TextureColorMod 대신 정점 색을 사용한다.
            vertex.color = p.SDL_Color(*tint, 255)
            vertex.tex_coord = p.SDL_FPoint((left + u) / atlas["width"], (top + v) / atlas["height"])
        indices = (ctypes.c_int * 6)(0, 1, 2, 0, 2, 3)
        if p.SDL_RenderGeometry(p.renderer, self.atlases[entry["atlas"]].texture, vertices, 4, indices, 6) != 0:
            raise RuntimeError("정면 시점의 바닥을 그리지 못했습니다.")

    def draw(self, name, sx, sy, scale, flip=False):
        """PNG 좌상단 기준점을 pico2d의 위쪽 +y 화면 좌표로 변환한다."""
        entry = self.manifest["sprites"][name]
        width, height = entry["width"], entry["height"]
        anchor = entry["anchor"]
        if flip:
            self.atlases[entry["atlas"]].clip_composite_draw(
                *entry["clip_rect_pico2d"], 0, "h",
                sx - (width / 2 - anchor["x"]) * scale,
                sy + (anchor["y"] - height / 2) * scale,
                width * scale, height * scale,
            )
            return
        self.atlases[entry["atlas"]].clip_draw(
            *entry["clip_rect_pico2d"],
            sx + (width / 2 - anchor["x"]) * scale,
            sy + (anchor["y"] - height / 2) * scale,
            width * scale, height * scale,
        )
