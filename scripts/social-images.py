#!/usr/bin/env python3
"""Build the per-channel social images for one image page into the git-ignored social/ folder.

Usage:
  python scripts/social-images.py content/dso/nebulas/vdb142 [--rotate auto|cw|ccw|none] [--x 0.5] [--y 0.5]

A landscape frame is rotated 90 degrees (lossless; the sky has no fixed up or down) and cropped to fill
the canvas. --x and --y set the crop centre as a fraction of the rotated image width and height.
--rotate auto (default) rotates clockwise when the image is landscape and leaves a portrait image as is.

Output in social/<slug>/ (does not touch the post texts):
  instagram.jpg   4:5, 1080x1350 (Facebook uses the same file)
  pinterest.jpg   2:3, 1000x1500
"""
import argparse
import re
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

CHANNELS = {"instagram": (1080, 1350), "pinterest": (1000, 1500)}


def featured_image(bundle):
    front = (bundle / "index.md").read_text(encoding="utf-8").split("---", 2)[1]
    match = re.search(r'^featured_image:\s*"([^"]*)"', front, re.M)
    if not match:
        raise SystemExit("No featured_image in the front matter")
    return bundle / match.group(1)


def fill_crop(image, size, x, y):
    # Scales the image to cover the canvas, then crops around the (x, y) centre, clamped to the edges
    width, height = size
    scale = max(width / image.width, height / image.height)
    scaled = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = min(max(round(scaled.width * x - width / 2), 0), scaled.width - width)
    top = min(max(round(scaled.height * y - height / 2), 0), scaled.height - height)
    return scaled.crop((left, top, left + width, top + height))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--rotate", choices=("auto", "cw", "ccw", "none"), default="auto")
    parser.add_argument("--x", type=float, default=0.5)
    parser.add_argument("--y", type=float, default=0.5)
    args = parser.parse_args()

    source = Image.open(featured_image(args.bundle))
    icc = source.info.get("icc_profile")
    image = source.convert("RGB")

    mode = args.rotate
    if mode == "auto":
        mode = "cw" if image.width > image.height else "none"
    if mode == "cw":
        image = image.transpose(Image.ROTATE_270)
    elif mode == "ccw":
        image = image.transpose(Image.ROTATE_90)

    out = Path("social") / args.bundle.name
    out.mkdir(parents=True, exist_ok=True)
    for name, size in CHANNELS.items():
        fill_crop(image, size, args.x, args.y).save(out / f"{name}.jpg", quality=92, subsampling=0, icc_profile=icc)
        print(f"{out / (name + '.jpg')}: {size[0]}x{size[1]}, rotation {mode}")


if __name__ == "__main__":
    main()
