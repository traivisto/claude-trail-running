---
name: activity-cache-updater
description: >
  Syncs the local activity cache CSV with the latest Garmin data. Use whenever the
  user says "update my activity cache", "sync new activities", "cache my recent runs",
  "refresh the cache", or when another skill (like coach-monthly-summary) detects that
  the cache is stale. Also use proactively before any analysis that needs up-to-date
  data. This skill never re-tags old activities — it only appends new ones.
---

# Activity Cache Updater

Fetch new Garmin activities since the last cached date, classify each one using the
garmin-activity-tagger logic, and append them to the local CSV cache.

## Step 0: Discover workspace

Run this to find the workspace directory:

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. All file references below are relative to it.

**Cache file:** `WORKSPACE/activity-cache.csv`

---

## Step 1: Read the cache and find the frontier

1. Read `WORKSPACE/activity-cache.csv` **using the Read tool** (not bash — bash sees a stale Cowork mount; see CLAUDE.md File reading rule). For efficiency, read only the tail (`offset` near end-of-file with `limit: 50`) to find the most recent date; that is enough for the frontier check. Read additional chunks only if needed for `activity_id` deduplication of unusually long backfills.
2. Find the **most recent `date`** value in the file (last row if sorted, but scan to be safe).
3. Note the set of all `activity_id` values already in the cache (for deduplication).
4. Report to the user: "Cache currently covers up to [date]. Checking for new activities…"

If the cache file doesn't exist or is empty, tell the user to run the backfill process first (the cache was originally built from Jan 2025 onward).

---

## Step 2: Fetch new activities from Garmin

> 📖 **Garmin-työkalujen parametrit, vastausrakenteet ja quirkit:** lue `garmin-mcp/SKILL.md`. Erityisesti: `activity_id` on aina number-tyyppi, nousudata haetaan `get_activity_splits`:llä.

Call `mcp__garmin__get_activities_by_date` with:
- `start_date`: the day **after** the most recent cached date (YYYY-MM-DD)
- `end_date`: today's date

This returns all activities in the date range in a single call — no pagination needed.

**Important:** `get_activity` requires `activity_id` as a **number** (not a string).

For each new activity, also call `mcp__garmin__get_activity_splits` with the numeric `activity_id` to get elevation data. Sum `elevation_gain_meters` across all laps to get `elevation_m`. The `get_activities_by_date` response does **not** include elevation — splits are the only reliable source.

---

## Step 3: Classify each new activity

For each activity **not already in the cache** (check by `activity_id`), apply the
garmin-activity-tagger classification logic manually:

### Classification rules (ordered — first match wins)

| # | Purpose | Condition |
|---|---------|-----------|
| 1 | Strength | type is gym/strength/indoor_cardio with distance < 1 km or avg HR < 100 |
| 2 | Interval / VO2max | trainingEffectLabel = VO2MAX, or anaerobicTrainingEffect > 2.5 |
| 3 | Tempo / Threshold | label = TEMPO or LACTATE_THRESHOLD, **and** duration < 120 min |
| 4 | Recovery | duration < 60 min AND label = RECOVERY |
| 5 | Very long / Race sim | distance > 30 km OR duration > 180 min |
| 6 | Long effort | distance > 15 km OR duration > 90 min |
| 7 | Cross-training | modality is Swimming, Skiing, Cycling, or Hiking/walking |
| 8 | Aerobic base | everything else |

### Modifiers (apply independently)

- **Hill**: elevation_per_km > `hill_modifier_threshold_m_per_km` from athlete-profile.md (skip if distance < 2 km)
- **Technical terrain** (running only, distance > 2 km):
  ```
  baseline = aerobic_baseline_pace_min_km     (Aerobic base / Tempo / Interval)
           = long_effort_baseline_pace_min_km (Long effort / Very long)
           = skip                              (Recovery / Strength / Cross-training)
  expected = baseline + (elev_per_km × 0.06)
  flag if actual_pace > expected × technical_terrain_multiplier
  ```
  (All `baseline` and multiplier values come from the Athlete Config block in `athlete-profile.md`.)

### Modality mapping

| Garmin typeKey | Modality |
|---------------|----------|
| trail_running | Trail running |
| running, indoor_running | Road running |
| lap_swimming, open_water_swimming | Swimming |
| skate_skiing_ws | Skate skiing |
| cross_country_skiing_ws | XC skiing |
| cycling, e_bike_mountain, e_bike_fitness | Cycling |
| hiking, walking | Hiking / walking |
| indoor_cardio, strength_training, yoga, pilates, breathwork | Gym / strength |
| multi_sport | Multi-sport |

### Time of day

| Start hour | Tag |
|-----------|-----|
| 05–08 | Morning |
| 09–16 | Daytime |
| 17–21 | Evening |
| 22–04 | Night |

---

## Step 4: Append to CSV

For each classified activity, write a row with these columns (in order):

```
activity_id, date, time_local, name, location, type_key, modality,
distance_km, duration_min, elevation_m, elev_per_km, pace_min_km,
purpose, hill, technical_terrain, time_of_day,
training_effect_label, aerobic_te, anaerobic_te,
avg_hr, max_hr, calories,
rpe, feel
```

**Column notes:**
- `rpe`: Garmin's post-activity perceived exertion value (integer 0–10). Read from the `directWorkoutRpe` field of `get_activity`. If the athlete did not rate the session, leave the field empty.
- `feel`: Garmin's post-activity subjective feel label. Read from `directWorkoutFeel` (Garmin uses numeric scale; convert to text where possible: very_weak / weak / normal / strong / very_strong) or `feelLabel` if present. Leave empty if absent.

**Important:**
- Round distance_km to 2 decimal places
- Round duration_min to 1 decimal place
- Round elevation_m to 0 decimal places
- Round elev_per_km to 1 decimal place
- Round pace_min_km to 2 decimal places
- `hill` and `technical_terrain` are Python-style booleans: `True` or `False`
- `rpe` and `feel` may be empty — never guess or fabricate values; only write what Garmin returns
- Keep existing rows unchanged — only append new rows
- Sort new rows by date ascending before appending

**Backfill note:** If the cache header does not yet include `rpe` and `feel` columns, the first sync after the schema change must add them. Extend the header line to include the two new columns, and left-pad existing rows with two empty trailing fields so column alignment is preserved. Do not re-tag or re-fetch old activities — just add the empty columns.

Write the new rows using the Edit tool (append to end of file).

---

## Step 5: Report

Tell the user:
- How many new activities were added
- The date range of new activities
- The new total row count
- A brief list of the new activities (date, name, purpose tag)

Example:
```
Added 3 new activities (Feb 25–28, 2026). Cache now covers Jan 1, 2025 → Feb 28, 2026 (253 activities).

New entries:
  Feb 25 — Morning Trail Run → Aerobic base + Hill
  Feb 27 — Evening Running → Tempo / Threshold
  Feb 28 — Pool Swim → Cross-training
```
