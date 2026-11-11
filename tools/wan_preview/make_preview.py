"""Submit the dungeon worker's four-second animation to a local ComfyUI server."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets/story_overtime_v1/act_01.png"
POSITIVE = (
    "A continuous four-second hand-drawn cartoon shot. The small exhausted dungeon repair worker "
    "on the left wears a teal hood, round brass goggles and a brown leather work apron. "
    "In the first two seconds he trudges slowly toward screen right with two short heavy shuffling steps. "
    "His boots alternately lift and plant on the stone floor; his body moves forward and bobs slightly. "
    "He drags the small rectangular wheeled toolbox behind him with one hand and holds a wrench in the other. "
    "Then he stops walking. His shoulders rise as he inhales, his eyes close, his chin drops, "
    "and his shoulders sink as he opens his mouth and lets out a long tired sigh. "
    "A small white breath puff drifts from his mouth and dissipates. "
    "Comically weary body language. The smiling skeleton skull on the crate at the right stays in place. "
    "Locked camera, full body stays in frame, continuous natural movement. "
    "Consistent thick ink outlines, warm comic shading, same face, outfit, toolbox and dungeon background."
)
NEGATIVE = (
    "still image, frozen character, slideshow, cuts, camera zoom, camera pan, "
    "photorealistic, live action, realistic 3D render, different character, changing clothes, "
    "extra arms, extra legs, fused fingers, deformed hands, floating feet, foot sliding, "
    "running, dancing, jumping, violent motion, melting objects, flickering outlines, "
    "text, subtitles, speech bubbles, watermark, blurry, low quality"
)


def request(server, endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    try:
        with urlopen(Request(server + endpoint, data=data,
                             headers={"Content-Type": "application/json"}), timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(error.read().decode("utf-8", errors="replace")) from error


def workflow(seed, width=640, height=480, steps=20):
    def node(kind, **inputs):
        return {"class_type": kind, "inputs": inputs}
    return {
        "1": node("LoadImage", image="dungeon_worker_story_atlas.png"),
        "2": node("ImageCrop", image=["1", 0], width=720, height=539, x=726, y=545),
        "3": node("SaveImage", images=["2", 0], filename_prefix="dungeon_preview/worker_input"),
        "4": node("CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default"),
        "5": node("CLIPTextEncode", clip=["4", 0], text=POSITIVE),
        "6": node("CLIPTextEncode", clip=["4", 0], text=NEGATIVE),
        "7": node("UNETLoader", unet_name="wan2.2_ti2v_5B_fp16.safetensors", weight_dtype="fp8_e4m3fn"),
        "8": node("ModelSamplingSD3", model=["7", 0], shift=8.0),
        "9": node("VAELoader", vae_name="wan2.2_vae.safetensors"),
        "10": node("Wan22ImageToVideoLatent", vae=["9", 0], width=width, height=height,
                   length=97, batch_size=1, start_image=["2", 0]),
        "11": node("KSampler", model=["8", 0], positive=["5", 0], negative=["6", 0],
                   latent_image=["10", 0], seed=seed, steps=steps, cfg=5.0,
                   sampler_name="uni_pc", scheduler="simple", denoise=1.0),
        "12": node("VAEDecodeTiled", samples=["11", 0], vae=["9", 0], tile_size=256,
                   overlap=64, temporal_size=32, temporal_overlap=8),
        "13": node("ImageFromBatch", image=["12", 0], batch_index=0, length=96),
        "14": node("CreateVideo", images=["13", 0], fps=24.0),
        "15": node("SaveVideo", video=["14", 0], filename_prefix=f"dungeon_preview/worker_{seed}",
                   format="mp4", **{"format.codec": "h264", "format.codec.encoding": "auto"}),
    }


def export_outputs(comfy_root, output_folder, outputs):
    source_folder = (comfy_root / "output").resolve()
    exported = {}
    for node_id, destination in (("3", "input.png"), ("15", "worker_trudge_sigh.mp4")):
        item = outputs[node_id]["images"][0]
        source = (source_folder / item.get("subfolder", "") / item["filename"]).resolve()
        if item.get("type") != "output" or not source.is_relative_to(source_folder):
            raise RuntimeError(f"Unexpected ComfyUI output path: {source}")
        shutil.copy2(source, output_folder / destination)
        exported[node_id] = destination
    return exported


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", required=True, type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8189")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/worker_video_v1")
    parser.add_argument("--seed", type=int, default=2026111101)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--submit-only", action="store_true")
    args = parser.parse_args()
    if args.width % 32 or args.height % 32:
        parser.error("Width and height must be multiples of 32")
    args.output.mkdir(parents=True, exist_ok=True)
    input_folder = args.comfy_root / "input"
    input_folder.mkdir(exist_ok=True)
    shutil.copy2(SOURCE, input_folder / "dungeon_worker_story_atlas.png")
    graph = workflow(args.seed, args.width, args.height, args.steps)
    (args.output / "workflow_api.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = request(args.server, "/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})
    record = {"prompt_id": result["prompt_id"], "server": args.server,
              "source": str(SOURCE.relative_to(ROOT)), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "crop": {"x": 726, "y": 545, "width": 720, "height": 539},
              "seed": args.seed, "width": args.width, "height": args.height, "steps": args.steps,
              "generated_frames": 97, "delivered_frames": 96, "fps": 24, "seconds": 4,
              "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "status": "queued"}
    record_path = args.output / "generation.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)
    if args.submit_only:
        return
    began = last = time.monotonic()
    while True:
        history = request(args.server, "/history/" + result["prompt_id"])
        if result["prompt_id"] in history:
            item = history[result["prompt_id"]]
            (args.output / "history.json").write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            record["status"] = item["status"]["status_str"]
            record["elapsed_seconds"] = round(time.monotonic() - began, 2)
            if record["status"] == "success":
                record["exported_files"] = export_outputs(args.comfy_root, args.output, item["outputs"])
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if record["status"] != "success":
                raise RuntimeError(json.dumps(item["status"], ensure_ascii=False))
            print(json.dumps(item["outputs"], ensure_ascii=False), flush=True)
            return
        now = time.monotonic()
        if now - last >= 30:
            queue = request(args.server, "/queue")
            print(f"Elapsed {now - began:.0f}s; running={len(queue['queue_running'])}, queued={len(queue['queue_pending'])}", flush=True)
            last = now
        time.sleep(5)


if __name__ == "__main__":
    main()
