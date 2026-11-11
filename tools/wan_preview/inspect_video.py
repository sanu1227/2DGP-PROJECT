"""Decode the delivered MP4, verify timing, and create a review contact sheet."""

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    samples = {0, 12, 24, 36, 48, 60, 72, 84, 95}
    sheet = Image.new("RGB", (960, 792), "#20252b")
    draw = ImageDraw.Draw(sheet)
    frame_hashes, timestamps, differences = [], [], []
    previous = None
    with av.open(str(args.video)) as container:
        stream = container.streams.video[0]
        fps = stream.average_rate
        codec = stream.codec_context.name
        size = [stream.width, stream.height]
        duration = float(stream.duration * stream.time_base)
        for index, frame in enumerate(container.decode(video=0)):
            pixels = frame.to_ndarray(format="rgb24")
            frame_hashes.append(hashlib.sha256(pixels.tobytes()).hexdigest())
            timestamps.append(Fraction(frame.pts) * frame.time_base)
            if previous is not None:
                differences.append(float(np.abs(pixels.astype(np.int16) - previous).mean()))
            previous = pixels.astype(np.int16)
            if index in samples:
                cell = sorted(samples).index(index)
                x, y = (cell % 3) * 320, (cell // 3) * 264
                image = Image.fromarray(pixels)
                image.thumbnail((320, 240), Image.Resampling.LANCZOS)
                sheet.paste(image, (x, y + 24))
                draw.text((x + 8, y + 6), f"Frame {index:02d} | {float(timestamps[-1]):.3f}s", fill="white")
    assert len(frame_hashes) == 96, f"Expected 96 frames, got {len(frame_hashes)}"
    assert fps == Fraction(24), f"Expected 24fps, got {fps}"
    assert duration == 4.0, f"Expected 4 seconds, got {duration}"
    assert timestamps == [Fraction(i, 24) for i in range(96)], "Unexpected frame timestamps"
    assert len(set(frame_hashes)) == 96, "Exact duplicate frames detected"
    report = {
        "file": args.video.name,
        "sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
        "bytes": args.video.stat().st_size,
        "codec": codec,
        "width": size[0], "height": size[1],
        "frames": len(frame_hashes), "fps": str(fps), "duration_seconds": duration,
        "unique_decoded_frames": len(set(frame_hashes)),
        "uniform_frame_timestamps": True,
        "adjacent_frame_mean_absolute_difference": {
            "min": min(differences), "mean": sum(differences) / len(differences), "max": max(differences)
        },
        "motion_review": "Contact sheet and frame sequences require separate visual inspection."
    }
    folder = args.video.parent
    sheet.save(folder / "contact_sheet.jpg", quality=94)
    (folder / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
