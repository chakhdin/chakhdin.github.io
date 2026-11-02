#!/usr/bin/env python3
"""Make the web copies of a finished image from its XISF file, outside PixInsight.

Usage:
  python scripts/web-copies.py "C:/Astro/pixinsight/NGC 253" [--quality 95] [--limit-mib 15] [--name NGC253] [--no-lookup] [--force]
  python scripts/web-copies.py --file "C:/path/M13_1.xisf" --out "C:/scratch/m13" [same options]

Finds the final full-size XISF in the folder (the highest _N number, ignoring *.annotated.xisf), looks up the object on SIMBAD
from the plate solution stored in the file, and writes next to it, named after the object:
  <name>.png            full size, 8 bit
  <name>.jpg            full size, JPEG at the given quality, no chroma subsampling (4:4:4)
  <name>.resample.png   8 bit, reduced to stay under the size limit (only if the full-size PNG is larger)
  <name>.facts.json     object, field and the SIMBAD objects in it, for the page and the social posts
The image must already be stretched. Existing output files are kept unless --force is given.
"""
import argparse
import base64
import io
import json
import re
import struct
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

VERSION = "0.1.0"
SIMBAD_URLS = [
    "https://simbad.cfa.harvard.edu/simbad/sim-tap/sync?request=doQuery&lang=adql&format=tsv&query=",
    "https://simbad.cds.unistra.fr/simbad/sim-tap/sync?request=doQuery&lang=adql&format=tsv&query=",
]
SIMBAD_TIMEOUT_S = 20
# well-known catalogues (main_id prefixes): in a wide field the biggest SIMBAD objects are otherwise obscure survey entries
SIMBAD_CATALOGUES = ["NGC", "IC", "M", "LDN", "LBN", "Sh", "vdB", "B", "Cr", "Mel", "Abell"]
SHARE_MIN_FACTOR = 0.25
NS = {"x": "http://www.pixinsight.com/xisf"}
SAMPLE_TYPES = {"UInt8": "u1", "UInt16": "<u2", "UInt32": "<u4", "Float32": "<f4", "Float64": "<f8"}


def log(message):
    print(message, flush=True)


# ---- XISF reading --------------------------------------------------------------------------------------------------------------

def find_final_xisf(folder):
    # the highest _N number wins; annotated copies are never used
    best = None
    for path in folder.glob("*.xisf"):
        if ".annotated" in path.name.lower():
            continue
        match = re.search(r"_(\d+)$", path.stem)
        number = int(match.group(1)) if match else 0
        if best is None or number > best[0]:
            best = (number, path)
    if best is None:
        raise SystemExit(f"No XISF file found in {folder}")
    return best[1]


def read_header(path):
    with open(path, "rb") as f:
        head = f.read(16)
        if head[:8] != b"XISF0100":
            raise SystemExit(f"{path} is not an XISF 1.0 file")
        length = struct.unpack("<I", head[8:12])[0]
        return ET.fromstring(f.read(length).decode("utf-8"))


def property_value(prop):
    # value of an inline Property element; vectors and matrices are little-endian float64
    kind = prop.get("type")
    if kind in ("Float64", "Float32", "Int32", "UInt32", "Int16", "UInt16", "Int8", "UInt8", "Boolean"):
        value = prop.get("value")
        return float(value) if kind.startswith("Float") else value
    if kind in ("F64Vector", "F64Matrix"):
        location = prop.get("location", "")
        if prop.get("compression") or not location.startswith("inline:"):
            return None
        raw = prop.text.strip()
        data = base64.b64decode(raw) if location == "inline:base64" else bytes.fromhex(raw)
        values = np.frombuffer(data, dtype="<f8")
        if kind == "F64Matrix":
            return values.reshape(int(prop.get("rows")), int(prop.get("columns")))
        return values
    return None


def read_properties(root):
    props = {}
    for prop in root.iter("{%s}Property" % NS["x"]):
        value = property_value(prop)
        if value is not None:
            # older PixInsight versions store the solution as "PCL:AstrometricSolution:..."
            props[prop.get("id").removeprefix("PCL:")] = value
    return props


def read_image(path, root):
    image = root.find("x:Image", NS)
    width, height, channels = (int(v) for v in image.get("geometry").split(":"))
    sample = image.get("sampleFormat")
    if sample not in SAMPLE_TYPES:
        raise SystemExit(f"Unsupported sample format {sample}")
    if image.get("compression"):
        raise SystemExit("Compressed XISF data blocks are not supported; save the image without compression")
    kind, offset, size = image.get("location").split(":")[0], None, None
    if kind != "attachment":
        raise SystemExit("Only attached image data is supported")
    _, offset, size = image.get("location").split(":")
    offset, size = int(offset), int(size)
    dtype = np.dtype(SAMPLE_TYPES[sample])
    count = width * height * channels
    if size != count * dtype.itemsize:
        raise SystemExit(f"Image block is {size} bytes, expected {count * dtype.itemsize}")
    data = np.fromfile(path, dtype=dtype, count=count, offset=offset)
    if image.get("pixelStorage", "Planar") == "Planar":
        data = data.reshape(channels, height, width).transpose(1, 2, 0)
    else:
        data = data.reshape(height, width, channels)
    if sample.startswith("Float"):
        lo, hi = (float(v) for v in image.get("bounds", "0:1").split(":"))
        scaled = (data.astype(np.float32) - lo) / (hi - lo)
    else:
        scaled = data.astype(np.float32) / float(np.iinfo(dtype).max)
    pixels = np.rint(np.clip(scaled, 0.0, 1.0) * 255.0).astype(np.uint8)
    return pixels, width, height, channels


def solved_field(props, width, height):
    # centre, radius and scale (degrees) of the plate-solved image, or None
    matrix = props.get("AstrometricSolution:LinearTransformationMatrix")
    if matrix is None:
        return None
    scale_x = float(np.hypot(matrix[0][0], matrix[1][0]))
    scale_y = float(np.hypot(matrix[0][1], matrix[1][1]))
    if not scale_x > 0:
        return None
    ra = props.get("Observation:Center:RA")
    dec = props.get("Observation:Center:Dec")
    if ra is None or dec is None:
        return None
    radius = 0.5 * float(np.hypot(width * scale_x, height * scale_y))
    return {"ra": float(ra), "dec": float(dec), "radius": radius, "scale_arcsec_px": scale_x * 3600.0}


# ---- SIMBAD --------------------------------------------------------------------------------------------------------------------

def simbad_where(field, catalogues):
    return ("CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', %.5f, %.5f, %.4f))=1" % (field["ra"], field["dec"], field["radius"]) +
            " AND (" + " OR ".join(f"main_id LIKE '{c} %'" for c in catalogues) + ")")


def sized_adql(field):
    # objects from 1 arcmin up to 120% of the field diameter (no sky-sized clouds), biggest first
    max_size = "%.2f" % (field["radius"] * 2 * 60 * 1.2)
    return ("SELECT TOP 25 main_id, galdim_majaxis FROM basic WHERE " + simbad_where(field, SIMBAD_CATALOGUES + ["NAME"]) +
            f" AND galdim_majaxis BETWEEN 1 AND {max_size} ORDER BY galdim_majaxis DESC")


def unsized_adql(field):
    # catalogue objects SIMBAD has no size for, most referenced first
    return ("SELECT TOP 10 main_id, nbref FROM basic WHERE " + simbad_where(field, SIMBAD_CATALOGUES + ["NAME"]) +
            " AND galdim_majaxis IS NULL ORDER BY nbref DESC")


NAMED_OBJECTS = set()  # clean names of the SIMBAD objects whose main_id is a common name ("NAME ...")


def clean_name(raw):
    return re.sub(r"\s+", " ", re.sub(r'^(NAME|\*|V\*)\s+', "", raw.replace('"', ""))).strip()


def simbad_query(adql):
    # object names of one query, or None on any failure
    for url in SIMBAD_URLS:
        try:
            with urllib.request.urlopen(url + urllib.parse.quote(adql), timeout=SIMBAD_TIMEOUT_S) as response:
                body = response.read().decode("utf-8", "replace")
        except Exception as error:
            log(f"[simbad] {url.split('/')[2]} failed: {error}")
            continue
        rows = body.splitlines()
        if not rows or not re.match(r'^"?main_id"?(\t|$)', rows[0], re.I):
            log(f"[simbad] unexpected answer from {url.split('/')[2]}, ignored")
            continue
        names = []
        for row in rows[1:]:
            name = clean_name(row.split("\t")[0])
            if name and name not in names:
                names.append(name)
                # a common name, not a catalogue designation with a suffix such as "NGC 253 IRS 1"
                if re.match(r'^"?NAME\s', row) and not re.match(r"(%s)\s" % "|".join(SIMBAD_CATALOGUES), name):
                    NAMED_OBJECTS.add(name)
        return names
    return None


def lookup_objects(field):
    names = simbad_query(sized_adql(field))
    if names is None:
        return None
    for name in simbad_query(unsized_adql(field)) or []:
        if name not in names:
            names.append(name)
    return names


# ---- Output --------------------------------------------------------------------------------------------------------------------

def file_stem(name):
    # "NGC 253" -> "NGC253"
    return re.sub(r"[^A-Za-z0-9-]", "", name)


def to_image(pixels):
    return Image.fromarray(pixels[:, :, 0] if pixels.shape[2] == 1 else pixels)


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def write_resampled(image, path, limit_bytes, full_bytes):
    # smaller copy under the limit: the first factor comes from the full-size PNG size, then retries from the original pixels
    factor, size = 1.0, full_bytes
    for attempt in range(1, 8):
        factor = factor * (limit_bytes / size) ** 0.5 * 0.95
        if factor < SHARE_MIN_FACTOR:
            log(f"Resampled PNG abandoned: below {SHARE_MIN_FACTOR:.0%} of the side")
            return None
        w, h = round(image.width * factor), round(image.height * factor)
        data = png_bytes(image.resize((w, h), Image.LANCZOS))
        log(f"  attempt {attempt}: {w}x{h}, {len(data) / 1048576:.2f} MiB")
        if len(data) <= limit_bytes:
            path.write_bytes(data)
            return {"width": w, "height": h, "bytes": len(data)}
        size = len(data)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?")
    parser.add_argument("--file", help="use this XISF file instead of searching the folder")
    parser.add_argument("--out", help="folder for the output files (default: the folder, or the folder of --file)")
    parser.add_argument("--quality", type=int, default=95)
    parser.add_argument("--limit-mib", type=float, default=15.0)
    parser.add_argument("--name", help="object name for the file names, instead of the SIMBAD lookup")
    parser.add_argument("--no-lookup", action="store_true", help="skip SIMBAD (the file name of the XISF is used)")
    parser.add_argument("--force", action="store_true", help="overwrite existing output files")
    args = parser.parse_args()

    if args.file:
        source = Path(args.file)
        folder = Path(args.out) if args.out else (Path(args.folder) if args.folder else source.parent)
    elif args.folder:
        source = find_final_xisf(Path(args.folder))
        folder = Path(args.out) if args.out else Path(args.folder)
    else:
        parser.error("give a folder or --file")
    folder.mkdir(parents=True, exist_ok=True)
    log(f"Source: {source}")
    root = read_header(source)
    props = read_properties(root)
    pixels, width, height, channels = read_image(source, root)
    log(f"Image: {width}x{height}, {channels} channel(s)")

    field = solved_field(props, width, height)
    objects, lookup_status = [], "skipped"
    if field is None:
        lookup_status = "no plate solution"
        log("No usable plate solution in the file: no SIMBAD lookup")
    elif not args.no_lookup:
        log(f"Field: RA {field['ra']:.4f} Dec {field['dec']:.4f}, radius {field['radius']:.3f} deg, {field['scale_arcsec_px']:.3f} arcsec/px")
        found = lookup_objects(field)
        if found is None:
            lookup_status = "failed"
            log("SIMBAD lookup failed")
        else:
            objects, lookup_status = found, "ok"
            log(f"SIMBAD: {len(objects)} object(s): " + " | ".join(objects))

    # a named object (common name) first, else the first one found
    named = next((o for o in objects if o in NAMED_OBJECTS), None)
    object_name = args.name or named or (objects[0] if objects else re.sub(r"_\d+$", "", source.stem))
    stem = file_stem(object_name)
    log(f"Object: {object_name} -> files {stem}.*")

    paths = {"png": folder / f"{stem}.png", "jpg": folder / f"{stem}.jpg",
             "resample": folder / f"{stem}.resample.png", "facts": folder / f"{stem}.facts.json"}
    existing = [p for p in paths.values() if p.exists()]
    if existing and not args.force:
        raise SystemExit("Output exists, use --force to overwrite: " + ", ".join(p.name for p in existing))

    image = to_image(pixels)
    limit_bytes = round(args.limit_mib * 1048576)
    full = png_bytes(image)
    paths["png"].write_bytes(full)
    log(f"Wrote {paths['png'].name}: {len(full) / 1048576:.2f} MiB")
    image.save(paths["jpg"], "JPEG", quality=args.quality, subsampling=0, optimize=True)
    log(f"Wrote {paths['jpg'].name}: {paths['jpg'].stat().st_size / 1048576:.2f} MiB (quality {args.quality}, 4:4:4)")
    resampled = None
    if len(full) > limit_bytes:
        log(f"Resampling to under {args.limit_mib} MiB")
        resampled = write_resampled(image, paths["resample"], limit_bytes, len(full))
        if resampled:
            log(f"Wrote {paths['resample'].name}")
    else:
        log("Resampled PNG not needed: the full-size PNG is under the limit")

    facts = {
        "object": object_name,
        "simbad_objects_in_field": objects,
        "simbad_lookup": lookup_status,
        "field": None if field is None else {
            "ra_deg": round(field["ra"], 5), "dec_deg": round(field["dec"], 5),
            "radius_deg": round(field["radius"], 4), "scale_arcsec_per_px": round(field["scale_arcsec_px"], 4)},
        "image": {"width": width, "height": height, "channels": channels},
        "source_xisf": source.name,
        "files": {"png": paths["png"].name, "jpg": paths["jpg"].name,
                  "resample": paths["resample"].name if resampled else None,
                  "resample_size": resampled},
        "jpeg": {"quality": args.quality, "chroma_subsampling": "4:4:4"},
        "tool": f"web-copies.py {VERSION}",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    paths["facts"].write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"Wrote {paths['facts'].name}")


if __name__ == "__main__":
    sys.exit(main())
