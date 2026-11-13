"""프로젝트 경로에서 아틀라스를 한 번 로드하고 바닥 기준점에 맞춰 그린다."""

import ctypes
import json
from math import floor
from pathlib import Path

import pico2d.pico2d as p


ART_ROOT = Path(__file__).resolve().parents[1] / "assets" / "art_v1"
MAP_ROOT = ART_ROOT.parent / "map_pack_v1"
WALL_ROOT = ART_ROOT.parent / "wall_pack_v1"
GATE_ROOT = ART_ROOT.parent / "gate_pack_v1"


class Art:
    def __init__(self):
        self.atlases = {}
        self.atlas_paths = {}
        self.alpha_masks = {}
        try:
            self.placement = json.loads((ART_ROOT.parents[1] / "data" / "sprite_placement.json").read_text(encoding="utf-8"))
            self.manifest = json.loads((ART_ROOT / "manifest.json").read_text(encoding="utf-8"))
            self._ground_anchors(self.manifest)
            for name, entry in self.manifest["atlases"].items():
                self.atlas_paths[name] = ART_ROOT / entry["file"]
                self.atlases[name] = p.load_image(str(self.atlas_paths[name]))
            self.load_gimmicks()
        except Exception:
            self.close()
            raise

    def load_gimmicks(self):
        root = ART_ROOT.parent / "gimmicks_v1"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self.atlas_paths["gimmicks"] = root / "atlas.png"
        self.atlases["gimmicks"] = p.load_image(str(root / "atlas.png"))
        self.manifest["atlases"].update(manifest["atlases"])
        self.manifest["sprites"].update(manifest["sprites"])

    def load_gates(self):
        """발판 문은 열린 통로의 투명 영역까지 동일한 아틀라스로 처리한다."""
        if "gates" in self.atlases:
            return
        manifest = json.loads((GATE_ROOT / "manifest.json").read_text(encoding="utf-8"))
        path = GATE_ROOT / manifest["atlases"]["gates"]["file"]
        self.atlases["gates"] = p.load_image(str(path))
        self.atlas_paths["gates"] = path
        self.manifest["atlases"].update(manifest["atlases"])
        self.manifest["sprites"].update(manifest["sprites"])

    def load_theme(self, name):
        """방에서 사용하는 테마만 한 번 로드한다. 클릭용 알파도 같은 파일을 읽는다."""
        self._load_pack(MAP_ROOT, name, name)

    def load_walls(self, name):
        """바닥 없는 벽면과 부착 장식은 별도 아틀라스로 관리한다."""
        self._load_pack(WALL_ROOT, name, f"walls_{name}")

    def _load_pack(self, pack_root, theme, name):
        if name in self.atlases:
            return
        allowed = {"crypt", "sewer", "forge", "archive"}
        if pack_root == MAP_ROOT:
            allowed |= {"treasury", "boss"}
        if theme not in allowed:
            raise ValueError(f"알 수 없는 맵 테마: {theme}")
        root = pack_root / theme
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        self._ground_anchors(manifest)
        path = root / manifest["atlases"][name]["file"]
        image = p.load_image(str(path))
        self.atlases[name] = image
        self.atlas_paths[name] = path
        self.manifest["atlases"].update(manifest["atlases"])
        self.manifest["sprites"].update(manifest["sprites"])

    def _ground_anchors(self, manifest):
        """바닥에는 밑면 중심을, 손과 HUD에는 기존 표시 기준점을 사용한다."""
        for name, entry in manifest["sprites"].items():
            placement = self.placement.get(name, {})
            if "anchor" in placement:
                x, y = placement["anchor"]
                if not (0 <= x < entry["width"] and 0 <= y < entry["height"]):
                    raise ValueError(f"{name}: 바닥 기준점이 이미지 밖에 있습니다.")
                entry["display_anchor"] = entry["anchor"]
                entry["anchor"] = {"x": x, "y": y}

    def surface_height(self, name):
        """원본 스프라이트 픽셀 단위의 지지면 높이."""
        return self.placement.get(name, {}).get("surface_height", 0)

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

    def hit_test(self, name, sx, sy, scale, point, flip=False, height_scale=1.0):
        """그림의 투명한 모서리를 통과시켜 뒤의 바닥을 선택할 수 있게 한다."""
        entry = self.manifest["sprites"][name]
        offset = (point[0] - sx) / scale
        x = floor(entry["anchor"]["x"] + (-offset if flip else offset))
        y = floor(entry["anchor"]["y"] - (point[1] - sy) / (scale * height_scale))
        if not (0 <= x < entry["width"] and 0 <= y < entry["height"]):
            return False
        atlas = self.manifest["atlases"][entry["atlas"]]
        left, bottom, _, _ = entry["clip_rect_pico2d"]
        top = atlas["height"] - bottom - entry["height"]
        width, alpha = self._alpha(entry["atlas"])
        return alpha[(top + y) * width + left + x] >= 16

    def bounds(self, name, sx, sy, scale, flip=False, height_scale=1.0):
        """투명 여백을 제외한 표시 영역. 물체를 클릭하면 발이 놓인 칸을 고른다."""
        entry = self.manifest["sprites"][name]
        rect, anchor = entry["content_rect"], entry["anchor"]
        left = (rect["left"] - anchor["x"]) * scale
        right = left + rect["width"] * scale
        if flip:
            left, right = -right, -left
        top = sy + (anchor["y"] - rect["top"]) * scale * height_scale
        return sx + left, top - rect["height"] * scale * height_scale, sx + right, top

    @staticmethod
    def plate_sections(x):
        """상판 앞면과 고정 받침 경계. 256px 원본의 사선 모양을 따른다."""
        return floor(164 - abs(x - 126) * .55), floor(194 - abs(x - 128) * .5)

    def draw_plate(self, sx, sy, scale, pressed):
        """상판은 평행 이동하고 지지대만 짧아진다. 석재 받침은 고정한다."""
        if pressed <= 0:
            self.draw("plate_up", sx, sy, scale)
            return
        entry = self.manifest["sprites"]["plate_up"]
        atlas = self.atlases[entry["atlas"]]
        ax, ay = entry["anchor"]["x"], entry["anchor"]["y"]
        left, bottom, _, _ = entry["clip_rect_pico2d"]
        drop = (self.surface_height("plate_up") - self.surface_height("plate_down")) * pressed
        rect = entry["content_rect"]
        start = floor(sx + (rect["left"] - ax) * scale)
        end = floor(sx + (rect["left"] + rect["width"] - ax) * scale)
        for pixel in range(start, end + 1):
            x = floor(ax + (pixel + .5 - sx) / scale)
            if not 0 <= x < entry["width"]:
                continue
            if 44 <= x < 209:
                cap, base = self.plate_sections(x)
                sections = ((base, entry["height"], base, entry["height"] - base),
                            (cap, base, cap + drop, base - cap - drop),
                            (0, cap, drop, cap))
            else:
                sections = ((0, entry["height"], 0, entry["height"]),)
            for source_top, source_bottom, target_top, target_height in sections:
                if target_height <= 0:
                    continue
                atlas.clip_draw(left + x, bottom + entry["height"] - source_bottom,
                                1, source_bottom - source_top, pixel + .5,
                                sy + (ay - target_top - target_height / 2) * scale,
                                1, target_height * scale)

    def plate_hit_test(self, sx, sy, scale, point, pressed):
        x = floor(128 + (point[0] - sx) / scale)
        y = 176 - (point[1] - sy) / scale
        if 44 <= x < 209:
            cap, base = self.plate_sections(x)
            drop = (self.surface_height("plate_up") - self.surface_height("plate_down")) * pressed
            if y < cap + drop:
                y -= drop
            elif y < base:
                y = cap + (y - cap - drop) * (base - cap) / (base - cap - drop)
        return self.hit_test("plate_up", sx, sy, scale,
                             (point[0], sy + (176 - y) * scale))

    @staticmethod
    def gate_aperture(x):
        """정규화된 문틀 안쪽의 사선 통로 범위(원본 픽셀)."""
        top = floor(278 - 0.59 * (x - 197))
        return top, top + 132

    def draw_gate(self, sx, sy, scale, opening, flip=False):
        """문틀은 고정하고 격자 텍스처만 사선 개구부 안에서 위로 이동한다."""
        if opening <= 0:
            self.draw("gate_closed", sx, sy, scale, flip=flip)
            return "gate_closed"
        if opening < 1:
            lift = round(opening * 144)
            entry = self.manifest["sprites"]["gate_closed"]
            atlas = self.atlases[entry["atlas"]]
            ax, ay = entry["anchor"]["x"], entry["anchor"]["y"]
            clip_left, clip_bottom, _, _ = entry["clip_rect_pico2d"]
            ends = [sx + (x - ax) * scale * (-1 if flip else 1) for x in (197, 326)]
            # 화면 픽셀 단위로 이어 그려 축소 시 세로줄 사이에 틈이 생기지 않는다.
            for pixel in range(floor(min(ends)), floor(max(ends)) + 1):
                x = floor(ax + (pixel + 0.5 - sx) / scale * (-1 if flip else 1))
                if not 197 <= x < 326:
                    continue
                top, bottom = self.gate_aperture(x)
                height = bottom - top - lift
                if height <= 0:
                    continue
                atlas.clip_draw(clip_left + x, clip_bottom + entry["height"] - bottom,
                                1, height, pixel + 0.5,
                                sy + (ay - top - height / 2) * scale, 1, height * scale)
        # 움직인 격자는 기둥과 상인방 뒤로 들어간다.
        self.draw("gate_open", sx, sy, scale, flip=flip)
        return "gate_open"

    def gate_hit_test(self, sx, sy, scale, point, opening, flip=False):
        if opening <= 0:
            return self.hit_test("gate_closed", sx, sy, scale, point, flip)
        if self.hit_test("gate_open", sx, sy, scale, point, flip):
            return True
        x = floor(256 + (point[0] - sx) / scale * (-1 if flip else 1))
        y = 384 - (point[1] - sy) / scale
        top, bottom = self.gate_aperture(x)
        lift = round(opening * 144)
        return (197 <= x < 326 and top <= y < bottom - lift
                and self.hit_test("gate_closed", sx, sy + lift * scale, scale, point, flip))

    def draw(self, name, sx, sy, scale, flip=False, anchor=None, height_scale=1.0):
        """PNG 좌상단 기준점을 pico2d의 위쪽 +y 화면 좌표로 변환한다."""
        entry = self.manifest["sprites"][name]
        width, height = entry["width"], entry["height"]
        anchor = entry["anchor"] if anchor is None else anchor
        if flip:
            self.atlases[entry["atlas"]].clip_composite_draw(
                *entry["clip_rect_pico2d"], 0, "h",
                sx - (width / 2 - anchor["x"]) * scale,
                sy + (anchor["y"] - height / 2) * scale * height_scale,
                width * scale, height * scale * height_scale,
            )
            return
        self.atlases[entry["atlas"]].clip_draw(
            *entry["clip_rect_pico2d"],
            sx + (width / 2 - anchor["x"]) * scale,
            sy + (anchor["y"] - height / 2) * scale * height_scale,
            width * scale, height * scale * height_scale,
        )
