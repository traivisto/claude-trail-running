#!/usr/bin/env python3
"""
update-dashboard.py
───────────────────
Reads activity-cache.csv and rewrites all static data arrays in
training-dashboard.html.  Run after every cache update:

    python3 update-dashboard.py

No external dependencies — pure stdlib.
"""

import csv, json, re, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE  = Path(__file__).parent
CACHE = BASE / "activity-cache.csv"
DASH  = BASE / "training-dashboard.html"

# ── Modality → dashboard label ─────────────────────────────────────────────
MOD_LABEL = {
    "Trail running":          "Trail",
    "Road running":           "Road",
    "Hiking / walking":       "Walk",
    "XC skiing":              "XC Ski",
    "cross_country_skiing":   "XC Ski",
    "Skate skiing":           "Skate Ski",
    "Cycling":                "Cycling",
    "Swimming":               "Swim",
    "Gym / strength":         "Strength",
    "Multi-sport":            "Multi-sport",
    "resort_skiing":          "Resort ski",
}
# modData tracks only these 8 labels (others skipped)
MODDATA_LABELS  = ["Trail","Road","XC Ski","Skate Ski","Walk","Cycling","Swim","Strength"]
MODDATA_COLORS  = ["#4CAF50","#2196F3","#00BCD4","#80DEEA","#FFCC02","#FF9800","#E91E63","#795548"]

# ── Purpose → allActivities short label + colour ───────────────────────────
PURPOSE_SHORT = {
    "Aerobic base":         ("Base",      "#4CAF50"),
    "Long effort":          ("Long",      "#2196F3"),
    "Very long / Race sim": ("Race sim",  "#673AB7"),
    "Tempo / Threshold":    ("Tempo",     "#FF9800"),
    "Interval / VO2max":    ("Intervals", "#F44336"),
    "Recovery":             ("Recovery",  "#9E9E9E"),
    "Cross-training":       ("Cross",     "#00BCD4"),
    "Strength":             ("Strength",  "#795548"),
}
# purposeDs chart labels and colours
PURPOSE_KM_LABELS  = ["Aerobic base","Long effort","Very long / Race sim",
                       "Tempo / Threshold","Interval / VO2max","Recovery","Cross-training"]
PURPOSE_HRS_LABELS = PURPOSE_KM_LABELS + ["Strength"]
PURPOSE_COLORS     = ["#4CAF50","#2196F3","#673AB7","#FF9800","#F44336","#9E9E9E","#00BCD4","#795548"]

MONTH_NAMES = ["","Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Helpers ────────────────────────────────────────────────────────────────

def next_monday(d: date) -> date:
    """Monday that starts the week AFTER the week containing d (ISO: Mon=0)."""
    return d - timedelta(days=d.weekday()) + timedelta(days=7)

def fmt_dur(mins: float) -> str:
    """Convert decimal minutes → 'H:MM' string."""
    total = round(mins)
    return f"{total // 60}:{total % 60:02d}"

def js_num(v):
    """Format a float for JS: drop .0 if integer, else keep meaningful decimals."""
    if v == int(v):
        return str(int(v))
    return str(v)

def compact_json_list(items):
    """Produce a compact single-line JSON array."""
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))

# ── Load CSV ───────────────────────────────────────────────────────────────
if not CACHE.exists():
    sys.exit(f"ERROR: {CACHE} not found")

# Drop any stale kernel page-cache for this file before reading.
# Needed when the CSV is written by Windows tools via a 9P/virtio-fs mount
# and the Linux page cache has not yet picked up the latest version.
try:
    import os as _os
    with open(CACHE, "rb") as _f:
        _os.posix_fadvise(_f.fileno(), 0, 0, _os.POSIX_FADV_DONTNEED)
except Exception:
    pass  # Non-Linux or unsupported kernel — proceed normally

# Drop any stale kernel page-cache for this file before reading.
# Needed when the CSV is written by Windows tools via a 9P/virtio-fs mount
# and the Linux page cache has not yet picked up the latest version.
try:
    import os as _os
    with open(CACHE, "rb") as _f:
        _os.posix_fadvise(_f.fileno(), 0, 0, _os.POSIX_FADV_DONTNEED)
except Exception:
    pass  # Non-Linux or unsupported kernel — proceed normally

acts = []
with open(CACHE, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        raw_date = row["date"].strip()
        try:
            d = date.fromisoformat(raw_date)
        except ValueError:
            from datetime import datetime
            d = datetime.strptime(raw_date, "%m/%d/%Y").date()
        km_raw  = row["distance_km"].strip()
        dur_raw = row["duration_min"].strip()
        elv_raw = row["elevation_m"].strip()
        mod     = row["modality"].strip()
        is_gym  = (mod == "Gym / strength")

        km   = round(float(km_raw),  2) if km_raw  and not (is_gym and km_raw  == "0") else None
        hrs  = round(float(dur_raw) / 60, 2) if dur_raw else None
        elev = round(float(elv_raw))        if elv_raw and not (is_gym and elv_raw == "0") else None

        acts.append({
            "date":    d,
            "name":    row["name"].strip(),
            "mod":     MOD_LABEL.get(mod, mod),
            "modality": mod,
            "km":      km,
            "hrs":     hrs,
            "elev":    elev,
            "purpose": row["purpose"].strip(),
            "dur_raw": float(dur_raw) if dur_raw else 0.0,
        })

acts.sort(key=lambda a: (a["date"], a["name"]))
if not acts:
    sys.exit("ERROR: no activities found in cache")

first_date = acts[0]["date"]
last_date  = acts[-1]["date"]
today_str  = date.today().isoformat()
n_acts     = len(acts)

print(f"Loaded {n_acts} activities  {first_date} → {last_date}")

# ── rawSessions: per-day aggregation ──────────────────────────────────────
# Two aggregations:
#   day_km  – km > 0 days only (for rawSessions, wkKm, rollKm, calData)
#   day_all – ALL days incl. 0-km (for wkHrs, rollHrs so strength hrs count)
day_km  = defaultdict(lambda: {"km": 0.0, "hrs": 0.0, "elev": 0.0})
day_all = defaultdict(lambda: {"hrs": 0.0, "elev": 0.0})
for a in acts:
    ds = a["date"].isoformat()
    if a["km"] and a["km"] > 0:
        day_km[ds]["km"]   += a["km"]
        day_km[ds]["hrs"]  += (a["hrs"]  or 0.0)
        day_km[ds]["elev"] += (a["elev"] or 0.0)
    # always accumulate hrs/elev for ALL days (includes strength sessions)
    day_all[ds]["hrs"]  += (a["hrs"]  or 0.0)
    day_all[ds]["elev"] += (a["elev"] or 0.0)

# rawSessions uses km>0 aggregation (km, hrs, elev of same days)
raw_sessions = [
    {"date": ds,
     "km":   round(v["km"],   2),
     "hrs":  round(v["hrs"],  2),
     "elev": round(v["elev"])}
    for ds, v in sorted(day_km.items())
]
rs_by_date = {s["date"]: s for s in raw_sessions}

# ── Weekly buckets ─────────────────────────────────────────────────────────
# wkDate = next Monday after the week; week spans [wkDate-7, wkDate-1].
# wkKm/Elev sourced from km>0 days; wkHrs from ALL days (includes strength).
wk_km_d   = defaultdict(float)
wk_hrs_d  = defaultdict(float)
wk_elev_d = defaultdict(float)

for ds, v in day_km.items():
    lbl = next_monday(date.fromisoformat(ds)).isoformat()
    wk_km_d[lbl]   += v["km"]
    wk_elev_d[lbl] += v["elev"]

for ds, v in day_all.items():
    lbl = next_monday(date.fromisoformat(ds)).isoformat()
    wk_hrs_d[lbl]  += v["hrs"]

# wkDates = union of all weeks that have any activity
wk_dates = sorted(set(wk_km_d) | set(wk_hrs_d))
wk_km    = [round(wk_km_d.get(w, 0.0),  1) for w in wk_dates]
wk_hrs   = [round(wk_hrs_d.get(w, 0.0), 1) for w in wk_dates]
wk_elev  = [round(wk_elev_d.get(w, 0.0))   for w in wk_dates]

# wkDisplay: "Mon d'YY" when year changes, otherwise "Mon d"
wk_display = []
prev_year  = None
for w in wk_dates:
    d   = date.fromisoformat(w)
    lbl = f"{MONTH_NAMES[d.month]} {d.day}"
    if prev_year is None or d.year != prev_year:
        lbl += f"'{str(d.year)[2:]}"
        prev_year = d.year
    wk_display.append(lbl)

# ── Rolling 28-day snapshots ───────────────────────────────────────────────
# rollDate[0] = first_date + 28 days, then weekly (+7d each).
# Each snapshot = sum of rawSessions where date in [rollDate-27, rollDate].
roll_dates = []
roll_km    = []
roll_hrs   = []
roll_elev  = []

rd = first_date + timedelta(days=28)
while rd <= last_date:
    window_start = rd - timedelta(days=27)
    tkm = thrs = telev = 0.0
    for ds, s in rs_by_date.items():           # km from km>0 days
        sd = date.fromisoformat(ds)
        if window_start <= sd <= rd:
            tkm   += s["km"]
            telev += s["elev"]
    for ds, v in day_all.items():              # hrs from ALL days (incl. strength)
        sd = date.fromisoformat(ds)
        if window_start <= sd <= rd:
            thrs  += v["hrs"]
    roll_dates.append(rd.isoformat())
    roll_km.append(round(tkm,   1))
    roll_hrs.append(round(thrs, 1))
    roll_elev.append(round(telev))
    rd += timedelta(days=7)

# ── Monthly purpose breakdown ──────────────────────────────────────────────
# Build list of (year, month) from first to last activity month.
months = []
y, m = first_date.year, first_date.month
while (y, m) <= (last_date.year, last_date.month):
    months.append((y, m))
    m += 1
    if m > 12:
        m = 1; y += 1

def purpose_ds(metric):
    """
    metric: 'km' | 'hrs' | 'elev'
    Returns list of {label, data, backgroundColor} dicts.
    """
    labels = PURPOSE_HRS_LABELS if metric == "hrs" else PURPOSE_KM_LABELS
    colors = PURPOSE_COLORS[:len(labels)]
    # month_purpose[month_idx][purpose_full] → sum
    mp = defaultdict(lambda: defaultdict(float))
    for a in acts:
        yi, mi = a["date"].year, a["date"].month
        midx = months.index((yi, mi)) if (yi, mi) in months else -1
        if midx < 0:
            continue
        p = a["purpose"]
        if metric == "km":
            mp[midx][p] += (a["km"]   or 0.0)
        elif metric == "hrs":
            mp[midx][p] += (a["hrs"]  or 0.0)
        else:  # elev
            mp[midx][p] += (a["elev"] or 0.0)

    result = []
    for lbl, color in zip(labels, colors):
        data = [round(mp[i][lbl], (1 if metric in ("km","hrs") else 0))
                for i in range(len(months))]
        result.append({"label": lbl, "data": data, "backgroundColor": color})
    return result

purpose_ds_km   = purpose_ds("km")
purpose_ds_hrs  = purpose_ds("hrs")
purpose_ds_elev = purpose_ds("elev")

# ── modData ────────────────────────────────────────────────────────────────
mod_km   = defaultdict(float)
mod_hrs  = defaultdict(float)
mod_elev = defaultdict(float)
for a in acts:
    lbl = MOD_LABEL.get(a["modality"], a["modality"])
    if lbl not in MODDATA_LABELS:
        continue
    mod_km[lbl]   += (a["km"]   or 0.0)
    mod_hrs[lbl]  += (a["hrs"]  or 0.0)
    mod_elev[lbl] += (a["elev"] or 0.0)

mod_data_km   = [round(mod_km[l],   1) for l in MODDATA_LABELS]
mod_data_hrs  = [round(mod_hrs[l],  1) for l in MODDATA_LABELS]
mod_data_elev = [round(mod_elev[l])    for l in MODDATA_LABELS]

# ── calData: per-day km (all activities with km > 0) ──────────────────────
cal_data = [{"date": ds, "km": round(v["km"], 2)}
            for ds, v in sorted(day_km.items())]

# ── allActivities ──────────────────────────────────────────────────────────
all_activities = []
for a in acts:
    ps, pc = PURPOSE_SHORT.get(a["purpose"], (a["purpose"], "#9E9E9E"))
    entry = {
        "date":    a["date"].isoformat(),
        "name":    a["name"],
        "mod":     a["mod"],
        "km":      a["km"],
        "dur":     fmt_dur(a["dur_raw"]) if a["dur_raw"] else "0:00",
        "elev":    a["elev"],
        "purpose": ps,
        "pc":      pc,
    }
    all_activities.append(entry)

# ── Month label helpers for footer ────────────────────────────────────────
def month_label(d: date) -> str:
    return f"{MONTH_NAMES[d.month]} {d.year}"

# ── Derived display arrays ─────────────────────────────────────────────────
# rollLabels: human-readable labels for each rolling snapshot date
roll_labels = []
prev_year_rl = None
for rd_str in roll_dates:
    rd_d = date.fromisoformat(rd_str)
    lbl  = f"{MONTH_NAMES[rd_d.month]} {rd_d.day}"
    if prev_year_rl is None or rd_d.year != prev_year_rl:
        lbl += f"'{str(rd_d.year)[2:]}"
        prev_year_rl = rd_d.year
    roll_labels.append(lbl)

# monthKeys: "YYYY-MM" strings for the purpose chart x-axis
month_keys    = [f"{y:04d}-{m:02d}" for y, m in months]
# monthDisplay: "Mon YYYY" labels for purpose chart ticks
month_display = [f"{MONTH_NAMES[m]} {y}" for y, m in months]

# ── Build the replacement data block ──────────────────────────────────────

def arr(name, values, indent=""):
    """Format a JS const array on one line."""
    return f"{indent}const {name} = {compact_json_list(values)};"

def num_arr(values):
    """Compact numeric array without quotes."""
    return "[" + ",".join(str(v) for v in values) + "]"

def purpose_ds_js(var_name, datasets):
    parts = []
    for ds in datasets:
        data_str = "[" + ",".join(str(v) for v in ds["data"]) + "]"
        parts.append(
            f'{{"label":{json.dumps(ds["label"])},"data":{data_str},"backgroundColor":{json.dumps(ds["backgroundColor"])}}}'
        )
    return f"const {var_name} = [{','.join(parts)}];"

new_block = f"""// Per-session raw (for stats)
const rawSessions = {compact_json_list(raw_sessions)};

// Pre-aggregated weekly arrays
const wkDates   = {compact_json_list(wk_dates)};
const wkDisplay = {compact_json_list(wk_display)};
const wkKm  = {num_arr(wk_km)};
const wkHrs = {num_arr(wk_hrs)};
const wkElev= {num_arr(wk_elev)};

const rollDates  = {compact_json_list(roll_dates)};
const rollLabels = {compact_json_list(roll_labels)};
const rollKm  = {num_arr(roll_km)};
const rollHrs = {num_arr(roll_hrs)};
const rollElev= {num_arr(roll_elev)};

const monthKeys    = {compact_json_list(month_keys)};
const monthDisplay = {compact_json_list(month_display)};

{purpose_ds_js("purposeDsKm",  purpose_ds_km)}
{purpose_ds_js("purposeDsHrs", purpose_ds_hrs)}

{purpose_ds_js("purposeDsElev", purpose_ds_elev)}

// Merged modality
const modData = {{
  labels: {compact_json_list(MODDATA_LABELS)},
  km:   {num_arr(mod_data_km)},
  hrs:  {num_arr(mod_data_hrs)},
  elev: {num_arr(mod_data_elev)},
  colors: {compact_json_list(MODDATA_COLORS)}
}};

const calData = {compact_json_list(cal_data)};

const allActivities = {compact_json_list(all_activities)};

const TODAY = '{today_str}';"""

# ── Patch the HTML ─────────────────────────────────────────────────────────
html = DASH.read_text(encoding="utf-8")

# Find the data block using simple string markers (avoids regex backslash issues)
START_MARKER = "// Per-session raw (for stats)"
END_RE = re.compile(r"const TODAY = '[^']*';")

start_idx = html.find(START_MARKER)
end_match = END_RE.search(html, start_idx)
if start_idx < 0 or not end_match:
    sys.exit("ERROR: data block markers not found in HTML — has the file structure changed?")

new_html = html[:start_idx] + new_block + html[end_match.end():]

# ── Update footer ──────────────────────────────────────────────────────────
today = date.today()
footer_new = (
    f"{n_acts} sessions cached · "
    f"{month_label(first_date)}–{month_label(last_date)} · "
    f"Updated {today.day} {MONTH_NAMES[today.month]} {today.year}"
)
new_html = re.sub(
    r"\d+ sessions cached · [^<]+",
    footer_new,
    new_html,
    count=1,
)

DASH.write_text(new_html, encoding="utf-8")

# ── Summary ────────────────────────────────────────────────────────────────
print(f"✓ rawSessions : {len(raw_sessions)} day entries")
print(f"✓ wkKm        : {len(wk_km)} weeks  (last={wk_km[-1] if wk_km else '–'})")
print(f"✓ rollKm      : {len(roll_km)} snapshots  (last={roll_km[-1] if roll_km else '–'})")
print(f"✓ months      : {len(months)}  ({month_label(first_date)} – {month_label(last_date)})")
print(f"✓ allActivities: {len(all_activities)} entries")
print(f"✓ Footer      : {footer_new}")
print(f"✓ Saved → {DASH.name}")
