#!/usr/bin/env python3
"""
program_health.py
─────────────────
Mechanical aggregates for the program-health-check skill, computed from the athlete's activity cache,
for the Telegram chat run (no free shell, answers in ~250 words) and for exact numbers in any other
session. It implements the Step 3 aggregates of program-health-check/SKILL.md. It does NOT judge
anything: which areas apply and the red/yellow/green verdicts depend on the current phase text in
training-program.md, which the skill's "Chat mode" section has the bot read and apply. No network
access, nothing is written.

Usage:
    python3 scripts/program_health.py            # last 8 ISO weeks (current week in progress marked *)
    python3 scripts/program_health.py 12         # last 12 weeks

Reads ATHLETE_DIR/activity-cache.csv, ATHLETE_DIR/events-log.md and the Athlete Config block of
ATHLETE_DIR/athlete-profile.md (ATHLETE_DIR from scripts/resolve_athlete.py). Pure stdlib.

Definitions (same as the skill):
  * Run = Trail running + Road running. RunMin = running minutes; Trail = minutes of activity type
    Trail running (the athlete picks it whenever the route leaves roads/built paths). Terrain makes
    km a poor load measure on trails, so judge running volume by minutes (and D+) as well as km. Strength = modality "Gym / strength".
  * Hill session = elevation gain >= 200 m (any modality). Night = time_of_day Night.
  * Quality session = running session with purpose Interval / VO2max or Tempo / Threshold, or a
    quality keyword in the name (Nopeusperusta, VO2max, Kynnys, Tempo, Interval), or anaerobic TE > 2.5.
  * Grey-zone session = running session that is not Interval / VO2max / Tempo / Threshold and has
    avg HR from (hr_zone_z2 max - 4) up to hr_zone_z3 max (proxy, avg HR only).
  * B2B = Saturday run >= long_run_threshold_km and Sunday run >= 10 km in the same weekend.
  * Planned deload weeks are read from lines containing "deload" and a date range (d.m.-d.m.) in
    training-program.md and marked "D" in the table. The volume trend compares the average run km per
    non-deload week of the last 4 completed weeks with the 4 before them (current week excluded).
"""

import csv
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_athlete import resolve  # noqa: E402
from hr_histogram import load_zone_seconds  # noqa: E402

RUN = ("Trail running", "Road running")
QUALITY_PURPOSES = ("Interval / VO2max", "Tempo / Threshold")
QUALITY_WORDS = re.compile(r"nopeusperusta|vo2max|kynnys|tempo|interval", re.I)


def f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def hm(minutes: float) -> str:
    m = round(minutes)
    return f"{m // 60}:{m % 60:02d}"


def load_rows(athlete: Path):
    rows = []
    with open(athlete / "activity-cache.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                r["_d"] = datetime.strptime(r["date"], "%m/%d/%Y").date()
            except ValueError:
                continue
            rows.append(r)
    return rows


def athlete_config(athlete: Path) -> dict:
    cfg = {}
    path = athlete / "athlete-profile.md"
    if not path.exists():
        return cfg
    text = path.read_text(encoding="utf-8")
    m = re.search(r"## Athlete Config.*?```(.*?)```", text, re.S)
    for line in (m.group(1) if m else "").splitlines():
        k, sep, v = line.partition(":")
        if sep:
            cfg[k.strip()] = v.strip()
    return cfg


def hi(rng: str, default: float) -> float:
    nums = re.findall(r"\d+(?:\.\d+)?", rng or "")
    return float(nums[-1]) if nums else default


def is_quality(r) -> bool:
    return r["modality"] in RUN and (r["purpose"] in QUALITY_PURPOSES
                                     or QUALITY_WORDS.search(r["name"]) is not None
                                     or f(r["anaerobic_te"]) > 2.5)


def deload_weeks(athlete: Path, today: date) -> set:
    """Mondays of weeks that training-program.md flags as deload (start date of a 'deload' line's range)."""
    path = athlete / "training-program.md"
    if not path.exists():
        return set()
    out = set()
    rng = re.compile(r"(\d{1,2})\.(\d{1,2})\.?\s*[–-]\s*\d{1,2}\.\d{1,2}\.")
    for line in path.read_text(encoding="utf-8").splitlines():
        if "deload" not in line.lower():
            continue
        for m in rng.finditer(line):
            try:
                for year in (today.year, today.year - 1):
                    d = date(year, int(m.group(2)), int(m.group(1)))
                    if d <= today + timedelta(days=60):
                        out.add(d - timedelta(days=d.weekday()))
                        break
            except ValueError:
                continue
    return out


def recent_events(athlete: Path, today: date):
    path = athlete / "events-log.md"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(\d{4}-\d{2}-\d{2})\s*\|?\s*(.*)", line)
        if not m:
            continue
        d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if not today - timedelta(days=60) <= d <= today:
            continue
        rest = m.group(2)
        kind = re.match(r"([A-Za-z_]+)", rest)
        kind = kind.group(1).lower() if kind else ""
        if kind in ("training", "readiness"):  # routine log lines; keep illness, travel, tests, milestones
            continue
        out.append((d, f"{d.day}.{d.month}. {rest[:110]}"))
    return [e for _, e in sorted(out, key=lambda t: t[0])]


def main(argv) -> int:
    athlete = resolve()
    rows = load_rows(athlete)
    cfg = athlete_config(athlete)
    today = datetime.now(ZoneInfo("Europe/Helsinki")).date()
    n = int(argv[0]) if argv and argv[0].isdigit() else 8
    n = max(5, min(n, 26))

    long_km = f(cfg.get("long_run_threshold_km")) or 15.0
    z2_max, z3_max = hi(cfg.get("hr_zone_z2_range"), 141), hi(cfg.get("hr_zone_z3_range"), 148)
    grey_lo = z2_max - 4
    deloads = deload_weeks(athlete, today)

    this_mon = today - timedelta(days=today.weekday())
    mondays = [this_mon - timedelta(weeks=i) for i in range(n - 1, -1, -1)]
    by_week = defaultdict(list)
    for r in rows:
        by_week[r["_d"] - timedelta(days=r["_d"].weekday())].append(r)

    out = [f"PROGRAM HEALTH DATA {today.day}.{today.month}.{today.year} (last {n} ISO weeks, Mon-Sun; "
           f"* = week in progress, D = planned deload)",
           f"Config: long run >= {long_km:g} km; grey zone = avg HR {grey_lo:g}-{z3_max:g}; hill session >= 200 m",
           "Week     RunKm  RunMin Trail  Hrs   D+    Long(km/min)  Str  Hill  Tech  Night  Qual  Grey  B2B  Sessions"]
    run_km = {}
    for mon in mondays:
        W = by_week.get(mon, [])
        run = [r for r in W if r["modality"] in RUN]
        km = sum(f(r["distance_km"]) for r in run)
        run_km[mon] = km
        longest = max(run, key=lambda r: f(r["duration_min"]), default=None)
        sat = sum(f(r["distance_km"]) for r in run if r["_d"] == mon + timedelta(days=5))
        sun = sum(f(r["distance_km"]) for r in run if r["_d"] == mon + timedelta(days=6))
        grey = sum(1 for r in run if r["purpose"] not in QUALITY_PURPOSES and grey_lo <= f(r["avg_hr"]) <= z3_max)
        star = ("*" if mon == this_mon else "") + ("D" if mon in deloads else "")
        out.append(
            f"{f'{mon.day}.{mon.month}.{star}':<8} {km:5.1f}  {sum(f(r['duration_min']) for r in run):5.0f}  "
            f"{sum(f(r['duration_min']) for r in run if r['modality'] == 'Trail running'):5.0f}  {hm(sum(f(r['duration_min']) for r in W)):>5} "
            f"{sum(f(r['elevation_m']) for r in W):5.0f}  "
            + (f"{f(longest['distance_km']):4.1f}/{f(longest['duration_min']):3.0f}      " if longest else "-            ")
            + f"{sum(r['modality'] == 'Gym / strength' for r in W):3d}  "
              f"{sum(f(r['elevation_m']) >= 200 for r in W):4d}  "
              f"{sum(r['technical_terrain'] == 'True' for r in W):4d}  "
              f"{sum(r['time_of_day'] == 'Night' for r in W):5d}  "
              f"{sum(is_quality(r) for r in W):4d}  {grey:4d}  "
              f"{'yes' if sat >= long_km and sun >= 10 else 'no':>3}  {len(W):3d}")

    wk_km = lambda mon: sum(f(r["distance_km"]) for r in by_week.get(mon, []) if r["modality"] in RUN)
    done = [this_mon - timedelta(weeks=i) for i in range(8, 0, -1)]  # 8 completed weeks, oldest first
    avg = lambda ws: sum(wk_km(m) for m in ws) / len(ws) if ws else 0.0
    l4, p4 = [m for m in done[4:] if m not in deloads], [m for m in done[:4] if m not in deloads]
    a_l4, a_p4 = avg(l4), avg(p4)
    pct = (a_l4 / a_p4 - 1) * 100 if a_p4 else 0.0
    out.append(f"Run km per non-deload week: last 4 completed weeks {a_l4:.1f} ({len(l4)} weeks) vs previous 4 "
               f"{a_p4:.1f} ({len(p4)} weeks), {pct:+.0f} %")

    try:
        zs = load_zone_seconds(athlete)
    except (OSError, SystemExit):
        zs = {}
    if zs:
        out.append("Zone minutes of running sessions with an HR histogram (LTHR zones from Athlete Config; "
                   "Z1 incl. the gap above its max; cov = runs with data / runs; trail = Trail running only)")
        out.append("Week      Z1    Z2    Z3    Z4    Z5   | trail Z1  Z2  Z3+ | cov")
        for mon in mondays:
            run = [r for r in by_week.get(mon, []) if r["modality"] in RUN]
            got = [r for r in run if sum(zs.get(int(r["activity_id"]), [])) > 0]
            tot, trl = [0] * 5, [0] * 5
            for r in got:
                for i, s in enumerate(zs[int(r["activity_id"])]):
                    tot[i] += s
                    if r["modality"] == "Trail running":
                        trl[i] += s
            star = ("*" if mon == this_mon else "") + ("D" if mon in deloads else "")
            out.append(f"{f'{mon.day}.{mon.month}.{star}':<8} "
                       + " ".join(f"{s / 60:5.0f}" for s in tot)
                       + f"  | {trl[0] / 60:9.0f} {trl[1] / 60:3.0f} {sum(trl[2:]) / 60:4.0f} | {len(got)}/{len(run)}")
        out.append("(Weeks with cov below runs have missing histograms - run `python3 scripts/hr_histogram.py "
                   "missing`; zone minutes only count runs with data.)")

    q_rows = sorted((r for r in rows if r["_d"] >= mondays[0] and is_quality(r)), key=lambda r: r["_d"])
    if q_rows:
        out.append("Quality sessions: " + " | ".join(
            f"{r['_d'].day}.{r['_d'].month}. {r['name'][:28]} ({r['purpose']}, {f(r['distance_km']):.1f} km)"
            for r in q_rows[-8:]))
    strength = sorted(r["_d"] for r in rows if r["modality"] == "Gym / strength" and r["_d"] >= mondays[0])
    out.append("Strength dates: " + (", ".join(f"{d.day}.{d.month}." for d in strength) or "none"))

    months = []
    for y, mo in ((today.year - (today.month == 1), (today.month - 2) % 12 + 1), (today.year, today.month)):
        elev = sum(f(r["elevation_m"]) for r in rows if r["_d"].year == y and r["_d"].month == mo)
        months.append(f"{mo}/{y}: {elev:.0f} m" + (f" (day {today.day})" if (y, mo) == (today.year, today.month) else ""))
    out.append("D+ per calendar month: " + " | ".join(months))

    nights = [r for r in rows if r["time_of_day"] == "Night" and r["_d"] >= today - timedelta(weeks=8)]
    out.append(f"Night sessions in last 8 weeks: {len(nights)}"
               + (f" (last {max(r['_d'] for r in nights).day}.{max(r['_d'] for r in nights).month}.)" if nights else ""))

    frontier = max((r["_d"] for r in rows), default=None)
    if frontier:
        out.append(f"Last cached session: {frontier.day}.{frontier.month}.{frontier.year} "
                   f"({(today - frontier).days} days ago)")
    ev = recent_events(athlete, today)  # chronological
    if ev:
        out.append("Events log, last 60 days (routine training lines omitted):")
        out += [f"  - {e}" for e in ev[-12:]]
        if len(ev) > 12:
            out.append(f"  - (+{len(ev) - 12} older not shown)")
    note = "Cache covers through " + (frontier.strftime("%d.%m.%Y") if frontier else "n/a")
    if frontier is None or frontier < today - timedelta(days=1):
        note += " - recent days may be missing (this script does not sync)"
    out.append(note)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
