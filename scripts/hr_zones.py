#!/usr/bin/env python3
"""
hr_zones.py
───────────
Heart-rate zone distribution of one activity, using the athlete's LTHR-based zones (never Garmin's
%HRmax zones). Input is the file that `get_activity_fit_data(activity_id, include_records=true)` saves
(JSON with `records[].heart_rate_bpm` and `laps[].start_time`).

    python3 scripts/hr_zones.py <fit-data-file> [--athlete-dir <dir>]

Zone boundaries are read from the `Athlete Config` block of <athlete>/athlete-profile.md
(hr_zone_z1_max, hr_zone_z2_range ... hr_zone_z5_range). A value between two zones is assigned to the
lower zone (e.g. with Z3 140-150 and Z4 152-160: 151 counts as Z3; 161 counts as Z4). Records are 1 s apart, so counts
are seconds. Prints the whole-activity split and, when laps exist, the split per lap. Pure stdlib.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_athlete import resolve  # noqa: E402


def read_zone_minimums(profile: Path) -> list:
    text = profile.read_text(encoding="utf-8")
    z1 = re.search(r"^hr_zone_z1_max:\s*(\d+)", text, re.M)
    mins = [0]  # Z1 starts at 0
    if not z1:
        raise SystemExit("hr_zone_z1_max not found in the Athlete Config block of " + str(profile))
    for n in (2, 3, 4, 5):
        m = re.search(rf"^hr_zone_z{n}_range:\s*(\d+)\s*[–\-]\s*(\d+)", text, re.M)
        if not m:
            raise SystemExit(f"hr_zone_z{n}_range not found in " + str(profile))
        mins.append(int(m.group(1)))
    return mins  # lower bound of Z1..Z5


def zone_of(hr: int, mins: list) -> int:
    z = 1
    for i, lo in enumerate(mins, start=1):
        if hr >= lo:
            z = i
    return z


def split(hrs: list, mins: list) -> str:
    n = len(hrs)
    if not n:
        return "no HR data"
    counts = [0] * 5
    for h in hrs:
        counts[zone_of(h, mins) - 1] += 1
    parts = [f"Z{i+1} {c // 60}:{c % 60:02d} ({100 * c / n:.0f}%)" for i, c in enumerate(counts)]
    return f"{n // 60}:{n % 60:02d} total | " + " | ".join(parts)


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        return 2
    path = Path(args[0])
    athlete = Path(args[args.index("--athlete-dir") + 1]) if "--athlete-dir" in args else resolve()
    mins = read_zone_minimums(athlete / "athlete-profile.md")
    data = json.loads(path.read_text(encoding="utf-8"))
    recs = [r for r in data.get("records", []) if r.get("heart_rate_bpm")]
    if not recs:
        print("no per-second HR records in this file (was include_records=true used?)")
        return 1
    print("Zone lower bounds (bpm): " + ", ".join(f"Z{i+1}>={m}" for i, m in enumerate(mins)))
    print("Whole activity: " + split([int(r["heart_rate_bpm"]) for r in recs], mins))
    laps = data.get("laps") or []
    if len(laps) > 1:
        starts = [l.get("start_time") for l in laps]
        if all(starts):
            for i, lap in enumerate(laps):
                lo = starts[i]
                hi = starts[i + 1] if i + 1 < len(laps) else "9999"
                hrs = [int(r["heart_rate_bpm"]) for r in recs if lo <= r["timestamp"] < hi]
                print(f"Lap {lap.get('lap_number', i + 1)} (start {lo[-8:]}, "
                      f"{(lap.get('total_distance_m') or 0) / 1000:.2f} km): " + split(hrs, mins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
