"""Check art files; --window also verifies individual/atlas rendering in pico2d.

Run from any directory: python tools/art/check.py [--window]
No Pillow dependency. The --window path requires the project's pico2d installation.
"""

import argparse
import ctypes
from datetime import date
import gc
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2] / "assets" / "art_v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", action="store_true")
    args = parser.parse_args()
    manifest_bytes = (ROOT / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    for group in ("sources", "atlases", "sprites"):
        for name, entry in manifest[group].items():
            data = (ROOT / entry["file"]).read_bytes()
            if data[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"Not PNG: {name}")
            width, height, depth, color = struct.unpack(">IIBB", data[16:26])
            if (width, height) != (entry["width"], entry["height"]):
                raise ValueError(f"Incorrect dimensions: {name}")
            if depth != 8 or color != 6:
                raise ValueError(f"Not RGBA8: {name}")
            if digest(data) != entry["sha256"]:
                raise ValueError(f"Hash mismatch: {name}")
    print(f"PASS: {len(manifest['sprites'])} sprites, {len(manifest['atlases'])} aligned atlases, "
          f"{len(manifest['sources'])} sources; PNG headers and SHA-256.")
    if not args.window:
        return

    import pico2d.pico2d as p

    sprites, atlases = {}, {}
    p.open_canvas(1280, 900, sync=True)
    try:
        for name, entry in manifest["sprites"].items():
            sprites[name] = p.load_image(str(ROOT / entry["file"]))
        for name, entry in manifest["atlases"].items():
            atlases[name] = p.load_image(str(ROOT / entry["file"]))

        def render(use_atlas):
            p.clear_canvas()
            p.draw_rectangle(0, 0, 1280, 900, 23, 35, 41, filled=True)
            for index, (name, entry) in enumerate(manifest["sprites"].items()):
                x, y = 80 + (index % 8) * 160, 820 - (index // 8) * 145
                if use_atlas:
                    atlases[entry["atlas"]].clip_draw(*entry["clip_rect_pico2d"], x, y, 138, 138)
                else:
                    sprites[name].draw(x, y, 138, 138)
            pixels = (ctypes.c_ubyte * (1280 * 900 * 4))()
            result = p.SDL_RenderReadPixels(p.renderer, None, p.SDL_PIXELFORMAT_RGBA8888,
                                          pixels, 1280 * 4)
            if result != 0:
                raise RuntimeError("SDL_RenderReadPixels failed")
            p.update_canvas()
            p.get_events()
            return bytes(pixels)

        individual, atlas = render(False), render(True)
        max_error = max(abs(a - b) for a, b in zip(individual, atlas))
        if max_error > 2:
            raise ValueError(f"Atlas clip rendering differs from individual sprites: {max_error}")
        report = {
            "checked": date.today().isoformat(),
            "manifest_sha256": digest(manifest_bytes),
            "pico2d_loaded_images": len(sprites) + len(atlases),
            "individual_sprites_drawn": len(sprites),
            "atlas_clips_drawn": len(manifest["sprites"]),
            "max_rgba_channel_difference": max_error,
            "individual_render_sha256": digest(individual),
            "atlas_render_sha256": digest(atlas),
            "scope": "Actual SDL texture loading, drawing and atlas clip comparison; not game integration or playtesting.",
        }
        (ROOT / "runtime-validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"PASS: pico2d loaded {len(sprites) + len(atlases)} images; "
              f"drew {len(sprites)} sprites and atlas clips; max channel difference {max_error}.")
    finally:
        # Release SDL textures before destroying their renderer.
        sprites.clear()
        atlases.clear()
        gc.collect()
        p.close_canvas()


if __name__ == "__main__":
    main()
