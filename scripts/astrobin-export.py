#!/usr/bin/env python3
"""Build the AstroBin acquisition CSV and a description text for one object.

Usage:
  python scripts/astrobin-export.py "E:\\Astro\\pixinsight\\vdB 142" content/dso/nebulas/vdb142
  python scripts/astrobin-export.py "C:\\Astro\\pixinsight\\NGC 253" content/australia/ngc253 --dry-run

Output in social/<slug>/ (git-ignored):
  acquisition.csv            paste into AstroBin's "Import from CSV" box of the image acquisition form
  astrobin-description.txt   description text built from the page and the WBPP log

CSV columns follow https://welcome.astrobin.com/importing-acquisitions-from-csv (checked 02/11/2026):
date,filter,number,duration,binning,gain,sensorCooling,fNumber,bortle. "number" and "duration" are
mandatory, "filter" is the numeric ID of the filter in AstroBin's equipment database, values are not
validated by AstroBin (invalid ones are ignored).

Filter IDs: nothing is guessed. Put the verified IDs in social/astrobin-filters.json, e.g.
  {"L": 12345, "Clear": 12345}   (key = filter name as written by NINA / WBPP log)
A filter without an ID gets the marker TODO-<name> in the CSV; replace it before pasting.
The value may be a list of {"from", "until", "site", "id"} entries (all keys but "id" optional). "site" is the
start of the English site name in scripts/sites.local.json (e.g. "Swan Reach"); an entry with a "site" is used
only for lights taken there and wins over entries without one.

Rows: one per session, filter and exposure when the lights under <run folder>/process/SESSION_*/lights
(the run folder of the latest log) add up to the "active" count of the final WBPP group. Otherwise one
row per filter and exposure with the active count; its date is left empty when the group spans several
nights (a warning says so).
Bortle: taken per session from the site keywords of its lights, matched in scripts/sites.local.json.
A site that is not in the table leaves the cell empty.
Mosaics (process/PANEL_* folders, PANEL: keyword in the log): each panel is counted on its own (its
post-calibration group in the log, its lights in process/PANEL_<n>/SESSION_*/lights); the CSV rows of the
panels with the same date, filter and settings are added together, and the description lists the panels.
Known limitations: a group with active < total frames gets one row with an empty date (no per-night split).
Nothing is overwritten without --force. --dry-run prints and writes nothing.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pi_logs  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
FILTER_MAP = REPO / "social" / "astrobin-filters.json"
COLUMNS = ["date", "filter", "number", "duration", "binning", "gain", "sensorCooling", "fNumber", "bortle"]
LIGHT_KEYS = ("FILTER", "EXPTIME", "GAIN", "XBINNING", "SET-TEMP", "FOCRATIO", "SITELAT", "SITELONG", "DATE-OBS")
LIGHT_SUFFIXES = (".xisf", ".fits", ".fit")


def warn(message):
    print(f"WARNING: {message}", file=sys.stderr)


def fmt_number(value):
    # 300.0 -> "300", 2.5 -> "2.5"; AstroBin accepts up to 4 decimals for the duration
    return f"{value:.4f}".rstrip("0").rstrip(".")


def fits_cards(text):
    # FITS header: fixed 80-character cards, no newlines, closed by END
    found = {}
    for pos in range(0, len(text) - 79, 80):
        card = text[pos:pos + 80]
        if card.startswith("END") and not card[3:].strip():
            break
        if card[8:10] != "= ":
            continue
        value = card[10:].strip()
        if value.startswith("'"):
            end = value.find("'", 1)
            value = value[1:end] if end > 0 else value[1:]
        else:
            value = value.split("/")[0]
        found[card[:8].strip()] = value.strip()
    return found


def read_keys(light):
    # XISF keeps FITS keywords as XML elements, FITS as 80-character cards
    text = Path(light).open("rb").read(400000).decode("latin-1")
    if text.startswith("SIMPLE"):
        cards = fits_cards(text)
        return {key: cards[key] for key in LIGHT_KEYS if key in cards}
    found = {}
    for key in LIGHT_KEYS:
        match = re.search(rf'<FITSKeyword name="{re.escape(key)}" value="([^"]*)"', text)
        if match:
            found[key] = match.group(1).strip().strip("'")
    return found


def frame_files(folder):
    # One file per frame: the calibrated _a.xisf lights when there are any (raw files can sit next to them,
    # also for frames that were not used), otherwise one file per name stem
    files = [p for p in sorted(Path(folder).iterdir()) if p.suffix.lower() in LIGHT_SUFFIXES]
    calibrated = [p for p in files if p.suffix.lower() == ".xisf" and p.stem.endswith("_a")]
    if calibrated:
        return calibrated
    unique = {}
    for p in files:
        unique.setdefault(p.stem, p)
    return list(unique.values())


def session_lights(run_dir, panel=None):
    # {session: [header dict, ...]} from <run folder>/process/SESSION_YYYYMMDD/lights; each session counted once.
    # For a mosaic panel: <run folder>/process/PANEL_<n>/SESSION_YYYYMMDD/lights
    result = {}
    pattern = f"**/PANEL_{panel}/SESSION_*/lights" if panel else "**/SESSION_*/lights"
    for folder in sorted(Path(run_dir).glob(pattern)):
        match = re.fullmatch(r"SESSION_(\d{8})", folder.parent.name)
        if not match or match.group(1) in result:
            continue
        result[match.group(1)] = [read_keys(light) for light in frame_files(folder)]
    return result


def session_site(headers):
    # Site entry of the table that the session's lights were taken at; None when it is not in the table
    for header in headers:
        if "SITELAT" in header and "SITELONG" in header:
            return pi_logs.match_site(header)
    return None


def session_bortle(headers):
    site = session_site(headers)
    return site.get("bortle") if site else None


def session_site_name(headers):
    site = session_site(headers)
    return site["name"]["en"] if site else ""


def load_filter_map():
    if not FILTER_MAP.exists():
        return {}
    return json.loads(FILTER_MAP.read_text(encoding="utf-8"))


def filter_cell(name, ids, dates=(), sites=()):
    # value = one ID, or a list of {"from": "YYYY-MM-DD", "until": "YYYY-MM-DD", "site": "Swan Reach", "id": N}
    # (from/until/site optional); with a list every date and site of the row must resolve to the same ID.
    # An entry with a "site" counts only for that site and wins over the entries without one.
    value = ids.get(name)
    if isinstance(value, list):
        found = set()
        for date in dates or [""]:
            for site in sites or [""]:
                hit = [e for e in value if date and e.get("from", "0000-00-00") <= date <= e.get("until", "9999-99-99")]
                specific = [e for e in hit if e.get("site") and site.startswith(e["site"])]
                hit = specific or [e for e in hit if not e.get("site")]
                found.add(hit[0]["id"] if len(hit) == 1 else None)
        value = found.pop() if len(found) == 1 else None
    return str(value) if value else f"TODO-{name}"


def iso_date(session):
    return f"{session[:4]}-{session[4:6]}-{session[6:]}"


def build_rows(groups, lights, ids, prefix=""):
    rows = []
    for group in groups:
        name, exposure = group["filter"], group["exposure_s"]
        label = f"{prefix}{name} {fmt_number(exposure)} s"
        nights = group["sessions"] or sorted(lights)  # a log without SESSION keywords: use the nights on disk
        per_session = {}
        sample = None
        for session in nights:
            matching = [h for h in lights.get(session, []) if h.get("FILTER") == name and float(h.get("EXPTIME", -1)) == exposure]
            if matching:
                per_session[session] = len(matching)
                sample = sample or matching[0]
        if per_session and sum(per_session.values()) == group["active"]:
            split = per_session
        else:
            if per_session:
                warn(f"{label}: lights on disk ({sum(per_session.values())}) do not add up to the "
                     f"active count ({group['active']}); single row")
            elif group["active"] != group["total"]:
                warn(f"{label}: active count ({group['active']}) differs from the group total ({group['total']}) "
                     f"and no lights were found on disk; single row")
            else:
                warn(f"{label}: no lights found on disk; single row")
            if len(nights) > 1:
                warn(f"{label}: {group['active']} frames span {len(nights)} nights; date left empty")
            split = {nights[0] if len(nights) == 1 else None: group["active"]}
            sample = sample or next((h for ss in lights.values() for h in ss if h.get("FILTER") == name), {})
        for session, count in sorted(split.items(), key=lambda kv: kv[0] or ""):
            temp = sample.get("SET-TEMP")
            if session:
                bortle = session_bortle(lights.get(session, []))
            else:
                # whole group on one row: only when every night's site gives the same class
                classes = {session_bortle(lights.get(s, [])) for s in nights}
                bortle = classes.pop() if len(classes) == 1 else None
            rows.append({
                "date": iso_date(session) if session else "",
                "filter": filter_cell(name, ids, [iso_date(session)] if session else [iso_date(s) for s in nights],
                                      [session_site_name(lights.get(s, [])) for s in ([session] if session else nights)]),
                "number": str(count),
                "duration": fmt_number(exposure),
                "binning": sample.get("XBINNING", ""),
                "gain": fmt_number(float(sample["GAIN"])) if "GAIN" in sample else "",
                "sensorCooling": str(round(float(temp))) if temp else "",
                "fNumber": fmt_number(float(sample["FOCRATIO"])) if "FOCRATIO" in sample else "",
                "bortle": str(bortle) if bortle else "",
            })
    return rows


def merge_rows(rows):
    # Rows that differ only in the number of frames (the panels of a mosaic) become one row
    merged = {}
    for row in rows:
        key = tuple(row[c] for c in COLUMNS if c != "number")
        if key in merged:
            merged[key]["number"] = str(int(merged[key]["number"]) + int(row["number"]))
        else:
            merged[key] = dict(row)
    return list(merged.values())


def merge_panels(panel_groups):
    # One group per (filter, exposure) for the page check and the description; "panels" keeps the count of each
    merged = {}
    for g in panel_groups:
        entry = merged.setdefault((g["filter"], g["exposure_s"]), {
            "filter": g["filter"], "exposure_s": g["exposure_s"], "active": 0, "total": 0, "sessions": set(), "panels": {}})
        entry["active"] += g["active"]
        entry["total"] += g["total"]
        entry["sessions"].update(g["sessions"])
        entry["panels"][g["panel"]] = g["active"]
    return [{**v, "sessions": sorted(v["sessions"])} for _, v in sorted(merged.items())]


def csv_text(rows):
    # AstroBin wants a header line and no spaces around the commas
    return "\n".join([",".join(COLUMNS)] + [",".join(r[c] for c in COLUMNS) for r in rows]) + "\n"


def scalar(front, key):
    match = re.search(rf'^{key}:\s*"((?:[^"\\]|\\.)*)"', front, re.M)
    return match.group(1).replace('\\"', '"') if match else ""


def hours(seconds):
    total = round(seconds / 60)
    return f"{total // 60} h {total % 60:02d} min" if total >= 60 else f"{total} min"


def page_locations(front):
    # The "locations:" list of the page front matter: name, optional "Class N" Bortle, dates
    block = re.search(r"^locations:[ \t]*\n((?:[ \t]+.*\n|[ \t]*\n)*)", front + "\n", re.M)
    result = []
    for item in re.split(r"^[ \t]*-[ \t]+(?=name:)", block.group(1), flags=re.M)[1:] if block else []:
        name = re.search(r'name:\s*"([^"]*)"', item)
        bortle = re.search(r'bortle:\s*"Class (\d)"', item)
        dates = re.search(r"dates:\s*\[(.*?)\]", item)
        result.append({
            "name": name.group(1) if name else "",
            "bortle": bortle.group(1) if bortle else "",
            "dates": re.findall(r"\d{4}-\d{2}-\d{2}", dates.group(1)) if dates else [],
        })
    return result


def description_text(page, groups, sessions):
    front, body = page.read_text(encoding="utf-8").split("---", 2)[1:]
    equipment = re.search(r"^equipment:\s*\[(.*)\]\s*$", front, re.M)
    gear = ", ".join(re.findall(r'"((?:[^"\\]|\\.)*)"', equipment.group(1))).replace('\\"', '"') if equipment else ""
    locations = page_locations(front)
    lines = [scalar(front, "title"), "", scalar(front, "description"), ""]
    for paragraph in re.split(r"\n\s*\n", body.strip()):
        if paragraph.strip():
            lines += [paragraph.strip(), ""]
    lines.append("Acquisition")

    def dmy(date):
        return f"{date[8:]}/{date[5:7]}/{date[:4]}"

    def place(loc):
        return f"{loc['name']}" + (f" (Bortle {loc['bortle']})" if loc["bortle"] else "")

    if len(locations) > 1:
        # every location with its own nights, as written on the page
        for loc in locations:
            nights = ", ".join(dmy(d) for d in loc["dates"])
            lines.append(f"Location: {place(loc)}" + (f", nights: {nights}" if nights else ""))
    else:
        if locations:
            lines.append(f"Location: {place(locations[0])}")
        nights = [dmy(iso_date(s)) for s in sessions] or [dmy(d) for loc in locations for d in loc["dates"]]
        if nights:
            lines.append("Nights: " + ", ".join(nights))
    panel_ids = sorted({p for g in groups for p in g.get("panels", {})})
    if len(panel_ids) > 1:
        lines.append(f"Mosaic: {len(panel_ids)} panels")
    if gear:
        lines.append(f"Equipment: {gear}")
    lines.append("Software: N.I.N.A. (acquisition), PHD2 (guiding)")
    total = 0
    for g in groups:
        seconds = g["active"] * g["exposure_s"]
        total += seconds
        panels = g.get("panels", {})
        detail = " (" + ", ".join(f"panel {p}: {n}" for p, n in sorted(panels.items())) + ")" if len(panels) > 1 else ""
        lines.append(f"{g['filter']}: {g['active']} x {fmt_number(g['exposure_s'])} s = {hours(seconds)}{detail}")
    lines.append(f"Total integration: {hours(total)}")
    if "processed in PixInsight" not in body:
        lines.append("Stacked and processed in PixInsight.")
    return "\n".join(lines) + "\n", front


def check_against_page(front, groups):
    # The page lists "N x Ds" per filter; the filter names can differ (log "Clear" vs page "L"), so compare counts only
    front = re.sub(r"^\s*panels:.*$", "", front, flags=re.M)  # mosaic pages: the per-panel counts are not extra filters
    page = sorted((int(n), float(s)) for n, s in re.findall(r'subs:\s*"(\d+) x (\d+(?:\.\d+)?)s"', front))
    log = sorted((g["active"], g["exposure_s"]) for g in groups)
    if page != log:
        warn(f"page frame counts {page} differ from the log's active counts {log}")


def is_mosaic(log):
    # Mosaic runs have process/PANEL_* folders and PANEL: keywords in the log
    run_dir = Path(log).parents[2]
    if any(run_dir.glob("**/process/PANEL_*")):
        return True
    return "PANEL:" in Path(log).read_text(encoding="utf-8", errors="replace")


def check_writable(path, force):
    if path.exists() and not force:
        sys.exit(f"{path} exists; use --force to overwrite")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="PixInsight object folder")
    parser.add_argument("page", help="Hugo page bundle, e.g. content/dso/nebulas/vdb142")
    parser.add_argument("--out", help="output folder (default social/<page folder name>)")
    parser.add_argument("--force", action="store_true", help="overwrite existing output")
    parser.add_argument("--dry-run", action="store_true", help="print the output, write nothing")
    args = parser.parse_args()

    page_dir = Path(args.page)
    if not (page_dir / "index.md").exists():
        sys.exit(f"{page_dir / 'index.md'} not found")
    log = pi_logs.latest_log(args.folder)
    if not log:
        sys.exit(f"No WBPP logs under {args.folder}")
    ids = load_filter_map()
    # <run folder>/output/logs/<log>: only the lights of the run that produced the log
    if is_mosaic(log):
        panel_groups = pi_logs.panel_counts(log)
        if not panel_groups:
            sys.exit(f"No light groups with a PANEL keyword in {log}")
        rows = []
        for panel in sorted({g["panel"] for g in panel_groups}):
            rows += build_rows([g for g in panel_groups if g["panel"] == panel],
                               session_lights(log.parents[2], panel), ids, prefix=f"Panel {panel}: ")
        rows = merge_rows(rows)
        groups = merge_panels(panel_groups)
    else:
        groups = pi_logs.final_counts(log)
        if not groups:
            sys.exit(f"No light groups in {log}")
        rows = build_rows(groups, session_lights(log.parents[2]), ids)
    missing = sorted({r["filter"][5:] for r in rows if r["filter"].startswith("TODO-")})
    if missing:
        warn(f"no AstroBin filter ID (for the date) for {missing}; add them to {FILTER_MAP} (cells are marked TODO-<name>)")
    if rows and not any(r["bortle"] for r in rows):
        warn("Bortle column left empty: site not in scripts/sites.local.json (or no site keywords in the lights)")
    sessions = sorted({s for g in groups for s in g["sessions"]})
    description, front = description_text(page_dir / "index.md", groups, sessions)
    check_against_page(front, groups)

    csv = csv_text(rows)
    if args.dry_run:
        print(f"# log: {log}\n# acquisition.csv\n{csv}\n# astrobin-description.txt\n{description}")
        return
    out = Path(args.out) if args.out else REPO / "social" / page_dir.name
    targets = [(out / "acquisition.csv", csv), (out / "astrobin-description.txt", description)]
    for path, _ in targets:
        check_writable(path, args.force)
    out.mkdir(parents=True, exist_ok=True)
    for path, text in targets:
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
