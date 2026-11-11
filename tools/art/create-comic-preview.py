"""Encode native SDL PNG captures as a review GIF (development-only Pillow)."""

import argparse
import json
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path, help="Directory containing frames.json and PNG captures")
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int)
    parser.add_argument("--palette-samples", type=int, default=1,
                        help="Palette reference frames; use several for different scenes")
    args = parser.parse_args()
    if args.palette_samples < 1:
        parser.error("--palette-samples must be at least 1")
    items = json.loads((args.frames / "frames.json").read_text(encoding="utf-8"))

    def read(item):
        with Image.open(args.frames / item["file"]) as source:
            result = source.convert("RGB")
            if args.width:
                result = result.resize((args.width, round(source.height * args.width / source.width)),
                                       Image.Resampling.LANCZOS)
            return result

    if args.palette_samples == 1:
        palette = read(items[-1]).quantize(colors=192)
    else:
        count = min(args.palette_samples, len(items))
        samples = [read(items[round(i * (len(items) - 1) / max(1, count - 1))]) for i in range(count)]
        sw, sh = samples[0].size
        contact = Image.new("RGB", (sw, sh * count))
        for index, sample in enumerate(samples):
            contact.paste(sample, (0, index * sh))
        palette = contact.quantize(colors=192)
    frames = [read(item).quantize(palette=palette, dither=Image.Dither.NONE) for item in items]
    elapsed, previous, durations = 0, 0, []
    # GIF stores centiseconds. Round the timeline rather than every frame,
    # so 125ms frames alternate 120/130ms without shortening the whole clip.
    for item in items:
        elapsed += item["duration_ms"]
        rounded = round(elapsed / 10) * 10
        durations.append(rounded - previous)
        previous = rounded
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(args.output, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=1, optimize=False)
    with Image.open(args.output) as output:
        duration = 0
        for index in range(output.n_frames):
            output.seek(index)
            duration += output.info["duration"]
        assert duration == previous, (duration, previous)
        print(json.dumps({"file": str(args.output), "frames": output.n_frames,
                          "duration_ms": duration, "size": output.size,
                          "bytes": args.output.stat().st_size}))


if __name__ == "__main__":
    main()
