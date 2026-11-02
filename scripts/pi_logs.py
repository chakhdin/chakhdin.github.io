#!/usr/bin/env python3
"""Read acquisition facts from the PixInsight WBPP logs of one object folder.

Folder layout: <object>/<date>/output/logs/<timestamp>.log (some folders have the
typo "ouput"). Frame counts follow the site rule: the "(N active)" figure of the
last Light group per filter and exposure, never the group total.

Usage:
  python scripts/pi_logs.py "E:\\Astro\\pixinsight\\vdB 142"
"""
import json
import re
import sys
from pathlib import Path

GROUP = re.compile(r"Group of (\d+) Light frames \((\d+) active\)")
STAMP = re.compile(r"^\[[^\]]*\] ")
SESSION = re.compile(r"SESSION: (\d{8})")
TOTAL_FIELDS = ("Filter", "Exposure", "Keywords")
SITE_KEYS = ("SITELAT", "SITELONG", "SITEELEV", "DATE-OBS", "TELESCOP", "INSTRUME", "FOCALLEN")
SITE_TABLE = Path(__file__).with_name("sites.local.json")


def latest_log(folder):
    # The log file name is a timestamp, so the highest name is the latest run.
    # Italian objects keep logs per date folder; the Swan Reach ones sit directly under the object.
    patterns = ("*/output/logs/*.log", "*/ouput/logs/*.log", "output/logs/*.log")
    logs = [p for pattern in patterns for p in Path(folder).glob(pattern)]
    return max(logs, key=lambda p: p.name) if logs else None


def read_groups(log):
    # Returns one dict per Light group block, in log order
    lines = [STAMP.sub("", line.rstrip("\n")) for line in Path(log).read_text(encoding="utf-8", errors="replace").splitlines()]
    groups = []
    for i, line in enumerate(lines):
        match = GROUP.search(line)
        if not match:
            continue
        group = {"total": int(match.group(1)), "active": int(match.group(2))}
        for follow in lines[i + 1:i + 12]:
            key, _, value = follow.partition(":")
            if key.strip() in TOTAL_FIELDS:
                group[key.strip()] = value.strip()
        groups.append(group)
    return groups


def final_counts(log):
    # Last block per (filter, exposure) wins; sessions are gathered from every block of that pair
    result = {}
    for group in read_groups(log):
        if "Filter" not in group or "Exposure" not in group:
            continue
        key = (group["Filter"], float(group["Exposure"].rstrip("s")))
        entry = result.setdefault(key, {"sessions": set()})
        entry.update(active=group["active"], total=group["total"])
        entry["sessions"].update(SESSION.findall(group.get("Keywords", "")))
    return [
        {"filter": f, "exposure_s": e, "active": v["active"], "total": v["total"], "sessions": sorted(v["sessions"])}
        for (f, e), v in sorted(result.items())
    ]


def first_light(folder):
    # NINA writes the site keywords in the calibrated lights (_a.xisf), not in the stacked XISF
    lights = sorted(Path(folder).glob("**/lights/*"))
    return next((p for p in lights if p.suffix.lower() in (".xisf", ".fits", ".fit")), None)


def light_header(light):
    # XISF keeps FITS keywords as XML elements, FITS as 80-character cards in the first blocks
    text = Path(light).open("rb").read(400000).decode("latin-1")
    found = {}
    for key in SITE_KEYS:
        match = re.search(rf'<FITSKeyword name="{key}" value="([^"]*)"', text) or re.search(
            rf"^{key:<8}= *'?([^'/\n]*?)'? *(?:/|$)", text, re.M
        )
        if match:
            found[key] = match.group(1).strip().strip("'").replace("&quot;", '"')
    return found


def to_degrees(value):
    # Keywords are decimal ("45.383") or sexagesimal ("+45 23 00.347")
    parts = value.split()
    if len(parts) == 1:
        return float(parts[0])
    sign = -1 if parts[0].startswith("-") else 1
    return sign * (abs(float(parts[0])) + float(parts[1]) / 60 + float(parts[2]) / 3600)


def match_site(header, table_path=SITE_TABLE):
    # The table is local and git-ignored: [{"lat", "lon", "tolerance_deg", "name": {en,it,ru}, "bortle"}]
    if "SITELAT" not in header or "SITELONG" not in header or not Path(table_path).exists():
        return None
    lat, lon = to_degrees(header["SITELAT"]), to_degrees(header["SITELONG"])
    date = header.get("DATE-OBS", "")[:10]
    for site in json.loads(Path(table_path).read_text(encoding="utf-8")):
        # Optional "from"/"until" (YYYY-MM-DD) limit an entry to a date range of the light's DATE-OBS
        if date and (date < site.get("from", "") or date > site.get("until", "9999-12-31")):
            continue
        tolerance = site.get("tolerance_deg", 0.01)
        if abs(site["lat"] - lat) <= tolerance and abs(site["lon"] - lon) <= tolerance:
            return site
    return None


def main():
    folder = sys.argv[1]
    log = latest_log(folder)
    if not log:
        sys.exit(f"No logs under {folder}")
    print(log)
    for row in final_counts(log):
        print(row)
    light = first_light(folder)
    header = light_header(light) if light else {}
    print(header)
    site = match_site(header)
    print(site["name"]["en"] if site else "Site not in sites.local.json")


if __name__ == "__main__":
    main()
