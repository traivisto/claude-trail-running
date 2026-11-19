#!/usr/bin/env python3
"""
hr_histogram.py
───────────────
Time-in-HR-zone cache. For each run the heart-rate histogram (seconds spent at each bpm) is stored in
ATHLETE_DIR/hr-histograms.csv (columns: activity_id,bpm,seconds). Zones are NOT stored: they are
computed from the histogram with the boundaries in the Athlete Config block of athlete-profile.md
whenever they are needed, so a change of zones never requires re-fetching from Garmin (same idea as
aerobic-efficiency-splits.csv). Never uses Garmin's own %HRmax zones.

Add one activity (input is the file that `get_activity_fit_data(activity_id, include_records=true)`
saves; the file is large, never read it into context):

    python3 scripts/hr_histogram.py add <fit-data-file> <activity_id> [--athlete-dir <dir>]

Add one activity from a binary FIT file (or a ZIP holding one), e.g. from `download_activity_file`; use
this for very long activities whose `get_activity_fit_data` result is too large for the connector:

    python3 scripts/hr_histogram.py add-fit <file.fit|file.zip> <activity_id> [--athlete-dir <dir>]

List activities that still need a histogram (runs = Trail running + Road running in activity-cache.csv):

    python3 scripts/hr_histogram.py missing [--since YYYY-MM-DD] [--athlete-dir <dir>]

Show the zone split of the cached runs (per run, newest last):

    python3 scripts/hr_histogram.py show [--since YYYY-MM-DD] [--athlete-dir <dir>]

Rules: records are weighted by the time to the next record (capped at 10 s; with the usual 1 s
recording that is 1 s per record). An activity without per-second HR gets one marker row
(bpm 0, seconds 0) so it is not fetched again. `add` is idempotent. Other scripts import
`load_zone_seconds(athlete)` -> {activity_id: [Z1..Z5 seconds]}. Pure stdlib.
"""

import csv
import json
import struct
import sys
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hr_zones import read_zone_minimums, zone_of  # noqa: E402
from resolve_athlete import resolve  # noqa: E402

FILE = "hr-histograms.csv"
RUN = ("Trail running", "Road running")
MAX_STEP_S = 10


def _read(athlete: Path):
    path = athlete / FILE
    if not path.exists():
        return {}
    hist = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            h = hist.setdefault(int(r["activity_id"]), Counter())
            if int(r["seconds"]) > 0:
                h[int(r["bpm"])] += int(r["seconds"])
    return hist


def load_zone_seconds(athlete: Path) -> dict:
    """{activity_id: [Z1..Z5 seconds]} for activities that have an HR histogram (marker-only ones are empty)."""
    mins = read_zone_minimums(athlete / "athlete-profile.md")
    out = {}
    for aid, h in _read(athlete).items():
        z = [0] * 5
        for bpm, sec in h.items():
            z[zone_of(bpm, mins) - 1] += sec
        out[aid] = z
    return out


def histogram_from_fit(path: Path) -> Counter:
    data = json.loads(path.read_text(encoding="utf-8"))
    recs = [r for r in data.get("records", []) if r.get("timestamp")]
    h = Counter()
    for i, r in enumerate(recs):
        bpm = r.get("heart_rate_bpm")
        if not bpm:
            continue
        step = 1.0
        if i + 1 < len(recs):
            try:
                t0 = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(recs[i + 1]["timestamp"].replace("Z", "+00:00"))
                step = min(max((t1 - t0).total_seconds(), 0.0), MAX_STEP_S)
            except ValueError:
                pass
        h[int(bpm)] += step
    return Counter({k: int(round(v)) for k, v in h.items() if round(v) > 0})


FIT_EPOCH = datetime(1989, 12, 31)


def _fit_messages(data: bytes):
    """Yield (global_message_number, {field_number: raw_bytes}, endian) for every data message of a FIT
    file (chained files supported). Minimal stdlib decoder: definition and data messages, compressed
    timestamp headers and developer fields are handled; CRCs are not checked."""
    pos = 0
    while pos + 14 <= len(data):
        hsize = data[pos]
        if hsize not in (12, 14) or data[pos + 8:pos + 12] != b".FIT":
            break
        dsize = struct.unpack_from("<I", data, pos + 4)[0]
        p, end = pos + hsize, pos + hsize + dsize
        defs, last_ts = {}, None
        while p < end:
            hdr = data[p]
            p += 1
            if hdr & 0x80:  # compressed timestamp header: local type in bits 5-6, time offset in bits 0-4
                local, offset = (hdr >> 5) & 3, hdr & 0x1F
                if last_ts is not None:
                    ts = (last_ts & ~0x1F) | offset
                    if ts < last_ts:
                        ts += 0x20
                    last_ts = ts
                d = defs.get(local)
                if d is None:
                    raise ValueError("data message without definition")
                fields = {}
                for num, size, _ in d["fields"]:
                    fields[num] = data[p:p + size]
                    p += size
                p += sum(sz for _, sz, _ in d["dev"])
                if last_ts is not None:
                    fields[253] = struct.pack(d["end"] + "I", last_ts)
                yield d["gmn"], fields, d["end"]
                continue
            local = hdr & 0x0F
            if hdr & 0x40:  # definition message
                end_c = "<" if data[p + 1] == 0 else ">"
                gmn = struct.unpack_from(end_c + "H", data, p + 2)[0]
                nf = data[p + 4]
                p += 5
                fields = [struct.unpack_from("BBB", data, p + 3 * i) for i in range(nf)]
                p += 3 * nf
                dev = []
                if hdr & 0x20:
                    nd = data[p]
                    p += 1
                    dev = [struct.unpack_from("BBB", data, p + 3 * i) for i in range(nd)]
                    p += 3 * nd
                defs[local] = {"gmn": gmn, "end": end_c, "fields": fields, "dev": dev}
                continue
            d = defs.get(local)
            if d is None:
                raise ValueError("data message without definition")
            fields = {}
            for num, size, _ in d["fields"]:
                fields[num] = data[p:p + size]
                p += size
            p += sum(sz for _, sz, _ in d["dev"])
            if 253 in fields and len(fields[253]) == 4:
                last_ts = struct.unpack(d["end"] + "I", fields[253])[0]
            yield d["gmn"], fields, d["end"]
        pos = end + 2  # skip the trailing CRC; a chained file may follow


def histogram_from_fit_file(path: Path) -> Counter:
    """HR histogram (seconds per bpm) from a binary .fit file or a .zip containing one."""
    raw = path.read_bytes()
    if raw[:2] == b"PK":
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".fit")]
            if not names:
                raise ValueError("no .fit file inside the zip")
            raw = z.read(names[0])
    recs = []  # (timestamp seconds, hr)
    for gmn, f, end in _fit_messages(raw):
        if gmn != 20 or 253 not in f:  # 20 = record
            continue
        ts = struct.unpack(end + "I", f[253])[0] if len(f[253]) == 4 else None
        hr = f.get(3, b"\xff")[0]
        if ts is not None:
            recs.append((ts, hr if hr not in (0, 255) else 0))
    h = Counter()
    for i, (ts, hr) in enumerate(recs):
        if not hr:
            continue
        step = 1.0
        if i + 1 < len(recs):
            step = min(max(recs[i + 1][0] - ts, 0), MAX_STEP_S)
        h[hr] += step
    return Counter({k: int(round(v)) for k, v in h.items() if round(v) > 0})


def _store(aid: int, h: Counter, athlete: Path) -> int:
    existing = _read(athlete)
    if aid in existing:
        print(f"{aid}: already in {FILE}, nothing added")
        return 0
    path = athlete / FILE
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["activity_id", "bpm", "seconds"])
        if h:
            for bpm in sorted(h):
                w.writerow([aid, bpm, h[bpm]])
        else:
            w.writerow([aid, 0, 0])  # marker: checked, no per-second HR
    if not h:
        print(f"{aid}: no per-second HR in the file, marker row written")
        return 0
    mins = read_zone_minimums(athlete / "athlete-profile.md")
    z = [0] * 5
    for bpm, sec in h.items():
        z[zone_of(bpm, mins) - 1] += sec
    print(f"{aid}: added {sum(h.values()) // 60}:{sum(h.values()) % 60:02d} of HR data | " +
          " | ".join(f"Z{i + 1} {s // 60}:{s % 60:02d}" for i, s in enumerate(z)))
    return 0


def cmd_add_fit(args, athlete: Path) -> int:
    if len(args) < 2:
        print(__doc__)
        return 2
    return _store(int(args[1]), histogram_from_fit_file(Path(args[0])), athlete)


def cmd_add(args, athlete: Path) -> int:
    if len(args) < 2:
        print(__doc__)
        return 2
    return _store(int(args[1]), histogram_from_fit(Path(args[0])), athlete)


def _runs(athlete: Path, since):
    out = []
    with open(athlete / "activity-cache.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["modality"] not in RUN:
                continue
            d = datetime.strptime(r["date"], "%m/%d/%Y").date()
            if since and d < since:
                continue
            r["_d"] = d
            out.append(r)
    return sorted(out, key=lambda r: (r["_d"], r["time_local"]))


def _since(args):
    if "--since" in args:
        return datetime.strptime(args[args.index("--since") + 1], "%Y-%m-%d").date()
    return None


def cmd_missing(args, athlete: Path) -> int:
    have = set(_read(athlete))
    todo = [r for r in _runs(athlete, _since(args)) if int(r["activity_id"]) not in have]
    for r in todo:
        print(f"{r['activity_id']} {r['_d'].isoformat()} {r['modality']} {r['name'][:40]}")
    print(f"{len(todo)} run(s) without HR histogram")
    return 0


def cmd_show(args, athlete: Path) -> int:
    zs = load_zone_seconds(athlete)
    for r in _runs(athlete, _since(args)):
        z = zs.get(int(r["activity_id"]))
        if not z or not sum(z):
            continue
        tot = sum(z)
        print(f"{r['_d'].day}.{r['_d'].month}. {r['modality'][:5]} {tot // 60:3d} min | " +
              " | ".join(f"Z{i + 1} {s // 60}" for i, s in enumerate(z)) + f" | {r['name'][:30]}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("add", "add-fit", "missing", "show"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    athlete = Path(rest[rest.index("--athlete-dir") + 1]) if "--athlete-dir" in rest else resolve()
    return {"add": cmd_add, "add-fit": cmd_add_fit, "missing": cmd_missing, "show": cmd_show}[cmd](rest, athlete)


if __name__ == "__main__":
    sys.exit(main())
