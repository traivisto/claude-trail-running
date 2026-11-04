---
name: aerobic-efficiency-updater
description: >
  Fetches split-level data for qualifying road running activities and appends
  them to aerobic-efficiency-splits.csv. Use after updating activity-cache.csv,
  or whenever the aerobic efficiency chart needs refreshing. Never re-fetches
  activities already in the splits cache.
---

# Aerobic Efficiency Updater

Fetch Garmin splits for qualifying road running activities not yet in the
splits cache, and append them to `aerobic-efficiency-splits.csv`.

---

## Step 0: Locate workspace

Find the workspace:
```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```
Use the containing directory as **WORKSPACE**.

---

## Step 1: Find qualifying activities not yet cached

Read `WORKSPACE/activity-cache.csv` and filter for:
- `modality` == `Road running`
- `hill` == `False`
- `technical_terrain` == `False`
- `distance_km` >= 5.0

Read `WORKSPACE/aerobic-efficiency-splits.csv` and collect all unique `activity_id` values already present.

Subtract: qualifying activities whose `activity_id` is NOT in the splits cache are the **targets**.

Report: "Found N qualifying activities. M already cached. Fetching splits for K new ones."

If K is 0, report "Splits cache is up to date." and stop.

---

## Step 2: Fetch splits for each target activity

For each target activity_id (as a **number**, not a string):

Call `mcp__garmin__get_activity_splits` with the numeric `activity_id`.

For each lap in the response, collect:
- `activity_id` (the number)
- `lap_number`
- `distance_meters` → `distance_m`
- `duration_seconds` → `duration_s`
- `avg_hr_bpm` → `avg_hr`
- `avg_speed_mps`
- `elevation_gain_meters` → `elevation_gain_m`
- `elevation_loss_meters` → `elevation_loss_m`

---

## Step 3: Append to splits cache

Append all new lap rows to `WORKSPACE/aerobic-efficiency-splits.csv`.

The CSV columns are:
```
activity_id,lap_number,distance_m,duration_s,avg_hr,avg_speed_mps,elevation_gain_m,elevation_loss_m
```

Use the **Write** tool to append (read current contents first, then write the full file with new rows added at the end). Do not re-write rows for activities already in the cache.

---

## Step 4: Run update-dashboard.py

After the cache is updated, run:
```bash
cd WORKSPACE && python update-dashboard.py
```

This recomputes all efficiency scores from the cached splits and regenerates the dashboard.

---

## Notes

- `activity_id` in Garmin MCP calls must always be a **number** (integer), not a string.
- The splits cache intentionally stores all laps, not just qualifying ones — filtering happens in `update-dashboard.py` at score computation time, so zone definition changes don't require re-fetching.
- Garmin `get_activity_splits` returns auto-lap (1 km) splits. Sub-400m laps are kept in the cache but filtered out during score computation.
- Temperature data is not currently included; add `temperature_c` column in a future iteration if needed.
