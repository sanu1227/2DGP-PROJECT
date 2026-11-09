"""프로젝트 경로에서 아틀라스를 한 번 로드하고 바닥 기준점에 맞춰 그린다."""

import ctypes
import json
from math import floor
from pathlib import Path

import pico2d.pico2d as p


ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "art_v1"
MAP_ROOT = ART_ROOT.parent / "map_pack_v1"
WALL_ROOT = ART_ROOT.parent / "wall_pack_v1"


class Art:
    def __init__(self):
        self.atlases = {}
        self.atlas_paths = {}
        self.alpha_masks = {}
        try:
            self.manifest = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
            for name, entry in self.manifest["atlases"].items():
                self.atlas_paths[name] = ART_ROOT / entry["file"]
                self.atlases[name] = p.load_image(str(self.atlas_paths[name]))
        except Exception:
            self.close()
            raise

    def load_theme(self, name):
        """방에서 사용하는 테마만 한 번 로드한다. 클릭용 알파도 같은 파일을 읽는다."""
        self._load_pack(MAP_ROOT, name, name)

    def load_walls(self, name):
        """바닥 없는 벽면과 부착 장식은 별도 아틀라스로 관리한다."""
        self._load_pack(WALL_ROOT, name, f"walls_{name}")

    def _load_pack(self, pack_root, theme, name):
        if name in self.atlases:
            return
        if theme not in {"crypt", "sewer", "forge", "archive"}:
            raise ValueError(f"알 수 없는 맵 테마: {theme}")
        root = pack_root / theme
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        path = root / manifest["atlases"][name]["file"]
        image = p.load_image(str(path))
        self.atlases[name] = image
        self.atlas_paths[name] = path
        self.manifest["atlases"].update(manifest["atlases"])
        self.manifest["sprites"].update(manifest["sprites"])

    def close(self):
        # Image 소멸자가 SDL 텍스처를 해제한다. close_canvas()보다 먼저 호출한다.
        self.atlases.clear()
        self.atlas_paths.clear()
        self.alpha_masks.clear()

    def _alpha(self, atlas_name):
        """필요한 아틀라스의 알파만 읽어 캐시한다. 이미지 파일은 바꾸지 않는다."""
        if atlas_name not in self.alpha_masks:
            path = self.atlas_paths[atlas_name]
            source = p.IMG_Load(str(path).encode("utf-8"))
            if not source:
                raise RuntimeError("클릭 판정용 아틀라스를 읽지 못했습니다.")
            rgba = None
            try:
                rgba = p.SDL_ConvertSurfaceFormat(source, p.SDL_PIXELFORMAT_RGBA32, 0)
                if not rgba:
                    raise RuntimeError("클릭 판정용 알파를 변환하지 못했습니다.")
                surface = rgba.contents
                pixels = ctypes.string_at(surface.pixels, surface.pitch * surface.h)
                alpha = b"".join(pixels[y * surface.pitch:y * surface.pitch + surface.w * 4][3::4]
                                 for y in range(surface.h))
                self.alpha_masks[atlas_name] = (surface.w, alpha)
            finally:
                if rgba:
                    p.SDL_FreeSurface(rgba)
                p.SDL_FreeSurface(source)
        return self.alpha_masks[atlas_name]

    def hit_test(self, name, sx, sy, scale, point, flip=False):
        """그림의 투명한 모서리를 통과시켜 뒤의 바닥을 선택할 수 있게 한다."""
        entry = self.manifest["sprites"][name]
        offset = (point[0] - sx) / scale
        x = floor(entry["anchor"]["x"] + (-offset if flip else offset))
        y = floor(entry["anchor"]["y"] - (point[1] - sy) / scale)
        if not (0 <= x < entry["width"] and 0 <= y < entry["height"]):
            return False
        atlas = self.manifest["atlases"][entry["atlas"]]
        left, bottom, _, _ = entry["clip_rect_pico2d"]
        top = atlas["height"] - bottom - entry["height"]
        width, alpha = self._alpha(entry["atlas"])
        return alpha[(top + y) * width + left + x] >= 16

    def bounds(self, name, sx, sy, scale, flip=False):
        """투명 여백을 제외한 표시 영역. 물체를 클릭하면 발이 놓인 칸을 고른다."""
        entry = self.manifest["sprites"][name]
        rect, anchor = entry["content_rect"], entry["anchor"]
        left = (rect["left"] - anchor["x"]) * scale
        right = left + rect["width"] * scale
        if flip:
            left, right = -right, -left
        top = sy + (anchor["y"] - rect["top"]) * scale
        return sx + left, top - rect["height"] * scale, sx + right, top

    def draw_floor(self, name, sx, sy, half_width, half_height, tint=(255, 255, 255)):
        """등각 바닥 윗면을 정면에 가까운 직사각형 평면에 매핑한다."""
        entry = self.manifest["sprites"][name]
        atlas = self.manifest["atlases"][entry["atlas"]]
        left, bottom, _, _ = entry["clip_rect_pico2d"]
        top = atlas["height"] - bottom - entry["height"]
        ax, ay = entry["anchor"]["x"], entry["anchor"]["y"]
        # 측면과 투명 테두리는 제외하고 224×112 마름모 윗면만 사용한다.
        source = ((ax, ay - 54), (ax + 110, ay), (ax, ay + 54), (ax - 110, ay))
        target = ((sx - half_width, sy + half_height), (sx + half_width, sy + half_height),
                  (sx + half_width, sy - half_height), (sx - half_width, sy - half_height))
        vertices = (p.SDL_Vertex * 4)(*[
            p.SDL_Vertex(p.SDL_FPoint(px, p.get_canvas_height() - 1 - py),
                         p.SDL_Color(*tint, 255),
                         p.SDL_FPoint((left + u) / atlas["width"], (top + v) / atlas["height"]))
            for (px, py), (u, v) in zip(target, source)
        ])
        indices = (ctypes.c_int * 6)(0, 1, 2, 0, 2, 3)
        if p.SDL_RenderGeometry(p.renderer, self.atlases[entry["atlas"]].texture,
                                vertices, 4, indices, 6) != 0:
            raise RuntimeError("3/4 탑다운 바닥을 그리지 못했습니다.")

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
