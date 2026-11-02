#!/usr/bin/env python3
"""Build Instagram material for one image page into the git-ignored social/ folder.

Usage:
  python scripts/social-export.py content/australia/ngc253 [--x 0.5] [--y 0.5] [--zoom 1.0]

--x and --y set the crop centre as a fraction of the image width and height.
--zoom above 1.0 crops tighter around that centre.

Output in social/<slug>/:
  1-crop.jpg     3:4 crop (1080x1440), first carousel slide
  2-full.jpg     whole frame on black (1080x1440), second carousel slide
  caption.txt    EN and IT caption drafts
"""
import argparse
import re
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

WIDTH, HEIGHT = 1080, 1440
HASHTAGS = "#astrophotography #astronomy #deepsky #space #nightsky"
SOLAR_HASHTAGS = "#astrophotography #astronomy #space #solarsystem #telescope"
LABELS = {
    "en": ("Total exposure", "Link in bio.", "collaboration with"),
    "it": ("Esposizione totale", "Link nella bio.", "collaborazione con"),
}


def scalar(front, key):
    # Reads a double-quoted top-level front matter value
    match = re.search(rf'^{key}:\s*"((?:[^"\\]|\\.)*)"', front, re.M)
    return match.group(1).replace('\\"', '"') if match else ""


def read_page(path):
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    return front, body


def fit_to_box(size, x, y, zoom):
    # Returns the largest 3:4 box inside the image, scaled by zoom and clamped to its edges
    img_w, img_h = size
    box_h = min(img_h, img_w * HEIGHT / WIDTH) / zoom
    box_w = box_h * WIDTH / HEIGHT
    left = min(max(img_w * x - box_w / 2, 0), img_w - box_w)
    top = min(max(img_h * y - box_h / 2, 0), img_h - box_h)
    return (round(left), round(top), round(left + box_w), round(top + box_h))


def caption(bundle, lang):
    name = "index.md" if lang == "en" else f"index.{lang}.md"
    front, body = read_page(bundle / name)
    exposure_label, link, credit_key = LABELS[lang]
    lines = [scalar(front, "title"), "", scalar(front, "description"), ""]
    exposure = scalar(front, "total_exposure")
    if exposure:
        lines.append(f"{exposure_label}: {exposure}")
    # Keep the name list only: it ends at the "and"/"e" item, or at the first comma if there is one name
    credit = re.search(rf"{credit_key} ((?:[^,.]+, )*?[^,.]+ (?:and|e) [^,.]+|[^,.]+)", body)
    if credit:
        lines.append(f"{credit_key.capitalize()} {credit.group(1).strip()}")
    lines.append(link)
    return "\n".join(lines)


SITE_URL = "https://shakhdinarov.com"
MONTHS = {
    "en": "January February March April May June July August September October November December".split(),
    "it": "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(),
}
POST_LABELS = {
    "en": {
        "optics": "{scope} at {focal}, {mount} mount", "and": "and", "total": "total exposure",
        "processing": "Stacked and processed in PixInsight",
        "details": "Full-resolution image and details:", "bio": "link in bio.",
        "mosaic": "Mosaic of {n} panels",
    },
    "it": {
        "optics": "{scope} a {focal}, montatura {mount}", "and": "e", "total": "di esposizione totale",
        "processing": "Integrata ed elaborata con PixInsight",
        "details": "Immagine a piena risoluzione e dettagli:", "bio": "link nella bio.",
        "mosaic": "Mosaico di {n} pannelli",
    },
}
MOUNT_WORDS = ("NEQ6", "Paramount", "EQ6", "HEQ5", "AZ-EQ")
FILTER_WORDS = ("filter", "UV-IR", "Astrodon", "Antlia", "Astronomik", "Optolong")


def quoted_list(front, key):
    # Reads a one-line front matter list of double-quoted strings
    match = re.search(rf"^{key}:\s*\[(.*)\]\s*$", front, re.M)
    return [s.replace('\\"', '"') for s in re.findall(r'"((?:[^"\\]|\\.)*)"', match.group(1))] if match else []


def nights(dates, lang):
    # "2026-10-16", "2026-10-17" -> "16 and 17 October 2026"; one group per month
    groups = {}
    for date in sorted(dates):
        year, month, day = date.split("-")
        groups.setdefault((year, int(month)), []).append(str(int(day)))
    parts = []
    for (year, month), days in groups.items():
        joined = days[0] if len(days) == 1 else ", ".join(days[:-1]) + f" {POST_LABELS[lang]['and']} " + days[-1]
        parts.append(f"{joined} {MONTHS[lang][month - 1]} {year}")
    return ", ".join(parts)


def post_text(bundle, lang, instagram):
    # One post block built only from the page front matter, so every figure matches the site
    name = "index.md" if lang == "en" else f"index.{lang}.md"
    front, _ = read_page(bundle / name)
    labels = POST_LABELS[lang]
    gear = quoted_list(front, "equipment")
    mount = next((g for g in gear if any(w in g for w in MOUNT_WORDS)), "")
    filt = next((g for g in gear if any(w in g for w in FILTER_WORDS)), "")
    camera = next((g for g in gear if g.startswith("ASI") and g not in (mount, filt)), "")
    scope = next((g for g in gear if g not in (mount, filt, camera)), "")
    place = re.search(r'- name: "([^"]*)"', front).group(1).rsplit(", ", 1)[0]
    bortle = re.search(r'bortle: "[^"\d]*(\d+)"', front).group(1)
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", front.split("locations:", 1)[1].split("featured_image:", 1)[0])
    subs = re.findall(r'- name: "([^"]*)"\s+subs: "([^"]*)"', front.split("filters:", 1)[1])
    frames = ", ".join(
        (s if len(subs) == 1 else f"{n} {s}").replace(" x ", " × ").replace("s", " s") for n, s in subs
    )
    total = re.sub(r"(\d+)h", r"\1 h", scalar(front, "total_exposure")).replace("m", " min")
    focal = scalar(front, "focal_length").replace("mm", " mm")
    if instagram:
        link = f"{labels['details']} {labels['bio']}"
    else:
        path = "/".join(bundle.parts[bundle.parts.index("content") + 1:])
        link = f"{labels['details']} {SITE_URL}{'' if lang == 'en' else '/' + lang}/{path}/"
    # Optional front matter key of a mosaic page (the exposure panel shows the frames per panel)
    panels = re.search(r"^mosaic_panels:\s*(\d+)", front, re.M)
    mosaic = [f"🧩 {labels['mosaic'].format(n=panels.group(1))}"] if panels else []
    return "\n".join([
        scalar(front, "title"), "", scalar(front, "description"), "",
        f"📍 {place} (Bortle {bortle}), {nights(dates, lang)}",
        "🔭 " + labels["optics"].format(scope=scope, focal=focal, mount=mount),
        f"📷 {camera}, {filt}",
        *mosaic,
        f"⏱️ {frames} = {total} {labels['total']}",
        f"💻 {labels['processing']}", "", link,
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--x", type=float, default=0.5)
    parser.add_argument("--y", type=float, default=0.5)
    parser.add_argument("--zoom", type=float, default=1.0)
    args = parser.parse_args()

    front, _ = read_page(args.bundle / "index.md")
    source = Image.open(args.bundle / scalar(front, "featured_image"))
    icc = source.info.get("icc_profile")
    image = source.convert("RGB")

    out = Path("social") / args.bundle.name
    out.mkdir(parents=True, exist_ok=True)

    box = fit_to_box(image.size, args.x, args.y, args.zoom)
    crop = image.crop(box).resize((WIDTH, HEIGHT), Image.LANCZOS)
    crop.save(out / "1-crop.jpg", quality=92, subsampling=0, icc_profile=icc)

    full = image.copy()
    full.thumbnail((WIDTH, HEIGHT), Image.LANCZOS)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "black")
    canvas.paste(full, ((WIDTH - full.width) // 2, (HEIGHT - full.height) // 2))
    canvas.save(out / "2-full.jpg", quality=92, subsampling=0, icc_profile=icc)

    tags = SOLAR_HASHTAGS if "sso" in args.bundle.parts else HASHTAGS
    captions = [caption(args.bundle, lang) for lang in LABELS]
    (out / "caption.txt").write_text("\n\n".join(captions + [tags]) + "\n", encoding="utf-8")
    # Post text in the fixed template: English first, then Italian; Instagram has no clickable links
    for suffix, instagram in (("instagram", True), ("web", False)):
        blocks = [post_text(args.bundle, lang, instagram) for lang in POST_LABELS]
        (out / f"post-{suffix}.txt").write_text("\n\n---\n\n".join(blocks) + f"\n\n{tags}\n", encoding="utf-8")
    print(f"{out}: crop box {box} of {image.size}")


if __name__ == "__main__":
    main()
