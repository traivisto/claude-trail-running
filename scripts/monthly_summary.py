#!/usr/bin/env python3
"""
monthly_summary.py
──────────────────
Compact monthly training summary computed from the athlete's activity cache, for the Telegram chat run
(which has no free shell and answers in ~250 words) and for exact numbers in any other session. It
implements the Step 3 aggregates of coach-monthly-summary/SKILL.md; the skill's "Chat mode" section
tells the bot how to turn this output into a short reply. No network access, nothing is written.

Usage:
    python3 scripts/monthly_summary.py                 # current month (Europe/Helsinki)
    python3 scripts/monthly_summary.py 2026-10         # one month
    python3 scripts/monthly_summary.py 2026-09 2026-10 2026-11   # several months, oldest first

Reads ATHLETE_DIR/activity-cache.csv and ATHLETE_DIR/events-log.md (ATHLETE_DIR from
scripts/resolve_athlete.py). Pure stdlib.

Notes on the numbers:
  * "Run" = Trail running + Road running. km in the headline is running km; all-modality km is shown too.
  * Average paces are total time / total distance of the sessions concerned (not a mean of paces).
  * "Fastest" ignores running sessions shorter than 2 km.
  * Weekly rows are ISO weeks (Mon-Sun); the first/last row is marked * when the week reaches outside
    the month.
  * If the cache ends before yesterday the output says so: this script never syncs.
"""

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_athlete import resolve  # noqa: E402

RUN = ("Trail running", "Road running")
EASY_PURPOSES = ("Recovery", "Aerobic base")
MONTHS_FI = ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu",
             "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu"]


def f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def pace(minutes: float, km: float) -> str:
    if km <= 0:
        return "-"
    p = minutes / km
    m, s = int(p), round((p - int(p)) * 60)
    if s == 60:
        m, s = m + 1, 0
    return f"{m}:{s:02d}/km"


def dm(r) -> str:
    return f"{r['_d'].day}.{r['_d'].month}."


def hm(minutes: float) -> str:
    m = round(minutes)
    return f"{m // 60}h {m % 60:02d}m"


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


def events_for(athlete: Path, year: int, month: int):
    path = athlete / "events-log.md"
    if not path.exists():
        return []
    out = []
    prefix = f"{year:04d}-{month:02d}-"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            continue
        d, rest = line[:10], line[10:].lstrip(" |")
        # "TYPE  note" or "category | note": keep the type token, drop routine training log lines
        m = re.match(r"([A-Za-z_]+)\s*\|?\s*(.*)", rest)
        kind, note = (m.group(1), m.group(2)) if m else ("", rest)
        if kind.lower() in ("training", "event", "readiness") and not re.search(
                r"sick|flu|illness|travel|alcohol|test", note, re.I):
            continue
        out.append(f"{int(d[8:])}.{int(d[5:7])}. {kind.upper()} {note[:70]}".rstrip())
    return out


def summarize(rows, year: int, month: int, athlete: Path) -> str:
    R = [r for r in rows if r["_d"].year == year and r["_d"].month == month]
    head = f"## {MONTHS_FI[month - 1].capitalize()} {year}"
    if not R:
        return head + "\nEi aktiviteetteja välimuistissa tälle kuukaudelle."
    run = [r for r in R if r["modality"] in RUN]
    run_km, all_km = sum(f(r["distance_km"]) for r in run), sum(f(r["distance_km"]) for r in R)
    minutes, elev = sum(f(r["duration_min"]) for r in R), sum(f(r["elevation_m"]) for r in R)
    lines = [head,
             f"Volume: {run_km:.1f} km juoksua ({len(run)} juoksua) | {all_km:.1f} km kaikki lajit | "
             f"{hm(minutes)} | {elev:.0f} m nousu | {len(R)} sessiota"]
    longest = max(R, key=lambda r: f(r["distance_km"]))
    lines.append(f"Longest: {longest['name'][:40]} {f(longest['distance_km']):.1f} km / "
                 f"{hm(f(longest['duration_min']))} / {f(longest['elevation_m']):.0f} m "
                 f"({longest['purpose']}, {dm(longest)})")

    mod = defaultdict(lambda: [0, 0.0])
    for r in R:
        mod[r["modality"]][0] += 1
        mod[r["modality"]][1] += f(r["distance_km"])
    lines.append("Modality: " + " | ".join(
        f"{k}: {n} ({km:.1f} km)" if km else f"{k}: {n}"
        for k, (n, km) in sorted(mod.items(), key=lambda kv: -kv[1][0])))

    pur = defaultdict(lambda: [0, 0.0])
    for r in R:
        pur[r["purpose"]][0] += 1
        pur[r["purpose"]][1] += f(r["distance_km"])
    lines.append("Purpose: " + " | ".join(
        f"{k}: {n} ({km:.1f} km)" if km else f"{k}: {n}"
        for k, (n, km) in sorted(pur.items(), key=lambda kv: -kv[1][0])))

    hill = sum(r["hill"] == "True" for r in R)
    tech = sum(r["technical_terrain"] == "True" for r in R)
    if hill or tech:
        lines.append(f"Modifiers: {hill} Hill | {tech} Technical terrain")

    paces = []
    for label, purposes in (("Aerobic base", ("Aerobic base",)),
                            ("Long", ("Long effort", "Very long / Race sim")),
                            ("Tempo", ("Tempo / Threshold",))):
        sel = [r for r in run if r["purpose"] in purposes and f(r["distance_km"]) > 0]
        if sel:
            paces.append(f"{label} {pace(sum(f(r['duration_min']) for r in sel), sum(f(r['distance_km']) for r in sel))}")
    fast = [r for r in run if f(r["distance_km"]) >= 2 and f(r["pace_min_km"]) > 0]
    if fast:
        fr = min(fast, key=lambda r: f(r["pace_min_km"]))
        paces.append(f"Fastest {pace(f(fr['pace_min_km']), 1)} ({dm(fr)}, {f(fr['distance_km']):.1f} km)")
    if paces:
        lines.append("Pace (running): " + " | ".join(paces))

    te_a = sum(f(r["aerobic_te"]) for r in R) / len(R)
    te_n = sum(f(r["anaerobic_te"]) for r in R) / len(R)
    labels = Counter(r["training_effect_label"] for r in R if r["training_effect_label"])
    lines.append(f"Intensity: avg aerobic TE {te_a:.1f} | avg anaerobic TE {te_n:.1f} | labels: " +
                 ", ".join(f"{n} {k.lower()}" for k, n in labels.most_common()))

    rated = [r for r in R if r["rpe"] not in ("", None)]
    feels = Counter(r["feel"] for r in R if r["feel"])
    if rated or feels:
        parts = []
        if rated:
            parts.append(f"avg RPE {sum(f(r['rpe']) for r in rated) / len(rated):.1f} ({len(rated)}/{len(R)} rated)")
        if feels:
            parts.append("feel " + ", ".join(f"{n} {k}" for k, n in feels.most_common()))
        grey = [r for r in rated if r["purpose"] in EASY_PURPOSES and f(r["rpe"]) >= 8]
        if grey:
            parts.append(f"{len(grey)} easy-day session(s) with RPE >= 8")
        lines.append("Subjective: " + " | ".join(parts))

    weeks = defaultdict(list)
    for r in R:
        weeks[r["_d"] - timedelta(days=r["_d"].weekday())].append(r)
    first, last = date(year, month, 1), (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
    wk = []
    for mon in sorted(weeks):
        W = weeks[mon]
        wrun = sum(f(r["distance_km"]) for r in W if r["modality"] in RUN)
        star = "*" if mon < first or mon + timedelta(days=6) > last else ""
        wk.append(f"{mon.day}.{mon.month}.{star}: {wrun:.1f} km ({len(W)} sess, {hm(sum(f(r['duration_min']) for r in W))})")
    lines.append("Weeks (Mon-Sun, run km): " + " | ".join(wk))

    tod = Counter(r["time_of_day"] for r in R)
    lines.append("Time of day: " + " | ".join(f"{n} {k}" for k, n in tod.most_common()))

    ev = events_for(athlete, year, month)
    if ev:
        lines.append("Events log:")
        lines += [f"  - {e}" for e in ev[:8]]
        if len(ev) > 8:
            lines.append(f"  - (+{len(ev) - 8} more)")
    return "\n".join(lines)


def main(argv) -> int:
    athlete = resolve()
    rows = load_rows(athlete)
    today = datetime.now(ZoneInfo("Europe/Helsinki")).date()
    months = []
    for a in argv or [f"{today.year}-{today.month:02d}"]:
        m = re.fullmatch(r"(\d{4})-(\d{2})", a)
        if not m or not 1 <= int(m.group(2)) <= 12:
            print(f"bad month '{a}', expected YYYY-MM", file=sys.stderr)
            return 2
        months.append((int(m.group(1)), int(m.group(2))))
    for i, (y, mo) in enumerate(months):
        if i:
            print()
        print(summarize(rows, y, mo, athlete))
    frontier = max((r["_d"] for r in rows), default=None)
    note = f"\nCache covers through {frontier.strftime('%d.%m.%Y') if frontier else 'n/a'}"
    if frontier is None or frontier < today - timedelta(days=1):
        note += " - recent days may be missing (this script does not sync)"
    if months and (months[-1][0], months[-1][1]) == (today.year, today.month):
        note += f"; the month is in progress (today is day {today.day})"
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
