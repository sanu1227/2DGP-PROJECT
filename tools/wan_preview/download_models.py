"""Download pinned official Wan models, resume partial files and verify SHA-256."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(model, comfy_root):
    target = comfy_root / "models" / model["folder"] / model["name"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != model["size"] or checksum(target) != model["sha256"]:
            raise RuntimeError(f"Existing model does not match manifest: {target}")
        print(f"Verified existing: {model['name']}", flush=True)
        return
    partial = target.with_suffix(target.suffix + ".partial")
    url = (f"https://huggingface.co/{model['repository']}/resolve/"
           f"{model['revision']}/{model['path']}?download=true")
    for attempt in range(4):
        done = partial.stat().st_size if partial.exists() else 0
        if done == model["size"]:
            break
        headers = {"User-Agent": "Dungeon-Wan-Preview/1.0"}
        if done:
            headers["Range"] = f"bytes={done}-"
        try:
            with urlopen(Request(url, headers=headers), timeout=90) as response:
                append = done > 0 and response.status == 206
                if append and not response.headers.get("Content-Range", "").startswith(f"bytes {done}-"):
                    raise RuntimeError("Unexpected range response")
                if not append:
                    done = 0
                began = last = time.monotonic()
                initial = done
                print(f"Downloading {model['name']} from {done / 1e9:.2f} GB", flush=True)
                with partial.open("ab" if append else "wb") as output:
                    while block := response.read(8 * 1024 * 1024):
                        output.write(block)
                        done += len(block)
                        now = time.monotonic()
                        if now - last >= 30:
                            rate = (done - initial) / (now - began) / 1e6
                            print(f"{model['name']}: {done / model['size']:.1%}, {rate:.1f} MB/s", flush=True)
                            last = now
            if done != model["size"]:
                raise RuntimeError(f"Incomplete model: {done} / {model['size']}")
            break
        except (OSError, RuntimeError) as error:
            if attempt == 3:
                raise
            print(f"Retry {attempt + 1}: {model['name']}: {error}", flush=True)
            time.sleep(3 * (attempt + 1))
    if checksum(partial) != model["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch: {partial}")
    partial.rename(target)
    print(f"Verified download: {model['name']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.comfy_root.resolve()
    if not (root / "main.py").is_file():
        parser.error("--comfy-root must point to an existing ComfyUI installation")
    manifest = json.loads(Path(__file__).with_name("models.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda model: download(model, root), manifest))


if __name__ == "__main__":
    main()
