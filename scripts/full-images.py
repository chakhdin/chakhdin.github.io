#!/usr/bin/env python3
"""Build the full-size JPEGs that the fullscreen viewer loads when it zooms in.

Usage:
  python scripts/full-images.py [--min-width 2400] [--only <text>] [--force]

For every page image in content/dso, content/australia and content/sso/comets (featured_image and each
versions[].image) it takes the source file, which is the bundle image itself unless scripts/full-sources.json
names another one (for example the full-size XISF of an image published smaller). Sources wider than
--min-width (the hero width cap in layouts/partials/hero-resize.html), and every source named in
full-sources.json, get a full-size JPEG:
  - a bundle JPEG that is already quality 95 with 4:4:4 chroma is copied unchanged;
  - an XISF goes through scripts/web-copies.py --file (quality 95, 4:4:4);
  - any other image is converted with the same JPEG settings.
The JPEGs are written to full/<page path>/<name>.jpg (git-ignored) and the map from page image to media key to
data/full_images.json, which layouts/_default/single.html reads. Upload with scripts/r2-upload-full.mjs
before pushing, or the pages will link to files that do not exist yet.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, JpegImagePlugin

Image.MAX_IMAGE_PIXELS = None

SECTIONS = ["dso", "australia", "sso/comets"]
QUALITY = 95
SOURCES = Path("scripts/full-sources.json")
DATA = Path("data/full_images.json")
OUT = Path("full")
# Standard IJG luminance table, to recognise a JPEG saved at QUALITY.
STD_LUMA = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]


def log(message):
    print(message, flush=True)


def page_images(md):
    front = md.read_text(encoding="utf-8").split("---")[1]
    return list(dict.fromkeys(re.findall(r'^\s*(?:featured_image|image):\s*"([^"]+)"', front, re.M)))


def xisf_width(path):
    with open(path, "rb") as f:
        head = f.read(16)
        if head[:8] != b"XISF0100":
            raise SystemExit(f"{path}: not an XISF file")
        xml = f.read(int.from_bytes(head[8:12], "little")).decode("utf-8", "replace")
    match = re.search(r'<Image[^>]*geometry="(\d+):(\d+):\d+"', xml)
    if not match:
        raise SystemExit(f"{path}: no image geometry in the XISF header")
    return int(match.group(1))


def is_target_jpeg(image):
    scale = 200 - 2 * QUALITY
    table = [min(255, max(1, (v * scale + 50) // 100)) for v in STD_LUMA]
    return (image.format == "JPEG" and sorted(image.quantization[0]) == sorted(table)
            and JpegImagePlugin.get_sampling(image) == 0)


def media_name(name):
    # "LDN 1228_1.resample.jpg" -> "ldn-1228_1.resample.jpg"
    return re.sub(r"\s+", "-", Path(name).stem.lower()) + ".jpg"


def build(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".xisf":
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, "scripts/web-copies.py", "--file", str(source), "--out", tmp,
                            "--name", "full", "--quality", str(QUALITY), "--no-lookup"], check=True)
            shutil.copyfile(Path(tmp) / "full.jpg", target)
        return "converted from XISF"
    with Image.open(source) as image:
        if is_target_jpeg(image):
            shutil.copyfile(source, target)
            return "copied"
        image.convert("RGB").save(target, "JPEG", quality=QUALITY, subsampling=0, optimize=True)
    return "converted"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-width", type=int, default=2400)
    parser.add_argument("--only", help="only page images whose key contains this text")
    parser.add_argument("--force", action="store_true", help="rebuild JPEGs that already exist")
    args = parser.parse_args()

    overrides = json.loads(SOURCES.read_text(encoding="utf-8")) if SOURCES.exists() else {}
    mapping = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {}
    content = Path("content")
    seen = set()
    for section in SECTIONS:
        for md in sorted((content / section).rglob("index.md")):
            page = md.parent.relative_to(content).as_posix()
            for name in page_images(md):
                key = f"{page}/{name}"
                seen.add(key)
                if args.only and args.only not in key:
                    continue
                source = Path(overrides.get(key, md.parent / name))
                if not source.exists():
                    raise SystemExit(f"{key}: source {source} not found")
                if source.suffix.lower() == ".xisf":
                    width = xisf_width(source)
                else:
                    with Image.open(source) as image:
                        width = image.width
                # A source named in full-sources.json is always included.
                if key not in overrides and width <= args.min_width:
                    mapping.pop(key, None)
                    continue
                media_key = f"full/{page}/{media_name(name)}"
                target = OUT / Path(media_key).relative_to("full")
                if target.exists() and not args.force:
                    log(f"{key}: {target} exists, kept")
                else:
                    log(f"{key}: {build(source, target)} -> {target} ({target.stat().st_size / 2**20:.1f} MiB)")
                mapping[key] = media_key
    # Page images that no longer exist lose their entry.
    for key in [k for k in mapping if k not in seen]:
        del mapping[key]
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(dict(sorted(mapping.items())), indent=2) + "\n", encoding="utf-8")
    log(f"Wrote {DATA}: {len(mapping)} full-size images")


if __name__ == "__main__":
    main()
