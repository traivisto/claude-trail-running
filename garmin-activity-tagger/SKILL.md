---
name: garmin-activity-tagger
description: >
  Classifies a Garmin activity into a purpose tag + modality tag + time-of-day tag,
  using the athlete's personal training thresholds from athlete-profile.md. Use this
  skill whenever the user asks to tag, classify, or analyse what type of training a
  specific activity was — e.g. "what kind of session was my Sunday run?", "tag
  activity 12345678", "classify my last workout", "was that a long run or a base
  run?". Also use when the user wants to understand whether a recent session counted
  as hill work, a very long effort, interval training, technical terrain, etc.
  Always prefer this skill over ad-hoc reasoning about activity type.
---

# Garmin Activity Tagger

Classify a single Garmin activity into: **Purpose**, **Modality**, **Modifiers**, and **Time of day**.

## Step 0: Discover workspace

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. The Athlete Config block in `WORKSPACE/athlete-profile.md` is the source for all thresholds referenced below.

---

## Taxonomy

### Purpose tags

| Tag | Meaning |
|-----|---------|
| **Recovery** | Deliberately easy, short, low-stress — facilitates adaptation from harder sessions |
| **Aerobic base** | Comfortable Z1–Z2 effort, standard duration — the bread-and-butter volume session |
| **Long effort** | Extended aerobic session, 15–30 km or 90 min–3 h — trains time-on-feet endurance |
| **Very long / Race sim** | 30 km+ or 3 h+ — specific 100 km prep, requires nutrition practice |
| **Tempo / Threshold** | Sustained hard effort at Z3–Z4 *by intent* — lactate threshold work (must be < 2 h; longer sessions override this) |
| **Interval / VO2max** | Structured high-intensity repeats, Z4–Z5 — speed and economy work |
| **Strength** | Gym, weights, bodyweight — no meaningful GPS or HR data |
| **Cross-training** | Skiing, swimming, cycling, hiking when used as running complement |

### Modifiers (stackable onto purpose tag)

| Modifier | Trigger condition |
|----------|-------------------|
| **+ Hill** | Elevation gain per km > `hill_modifier_threshold_m_per_km` from Athlete Config |
| **+ Technical terrain** | Actual pace > expected pace × `technical_terrain_multiplier` from Athlete Config (pace unexplained by elevation alone — see formula below) |

Multiple modifiers can stack: *Long effort + Hill + Technical terrain* is valid.

### Modality tags

| Garmin type | Modality label |
|-------------|---------------|
| `trail_running` | Trail running |
| `running`, `indoor_running` | Road running |
| `lap_swimming`, `open_water_swimming` | Swimming |
| `skate_skiing_ws` | Skate skiing |
| `cross_country_skiing_ws` | XC skiing |
| `cycling`, `e_bike_mountain`, `e_bike_fitness` | Cycling |
| `hiking`, `walking` | Hiking / walking |
| `resort_skiing` | Resort skiing |
| `indoor_cardio` + no GPS | Gym / strength |
| `multi_sport` | Multi-sport (note separately) |

### Time-of-day tag

| Start time (local) | Tag |
|-------------------|-----|
| 05:00–08:59 | Morning |
| 09:00–16:59 | Daytime |
| 17:00–21:59 | Evening |
| 22:00–04:59 | **Night** ⭐ |

Night sessions can be specifically valuable race preparation when the athlete's race card specifies a night/late-evening start time.

---

## Thresholds — read from `athlete-profile.md` Athlete Config

Do not hardcode these values. Read the Athlete Config block in `athlete-profile.md` and use the named fields below. The mapping:

| Parameter | Athlete Config field |
|-----------|----------------------|
| Long effort (distance) | `long_run_threshold_km` |
| Long effort (duration) | `long_run_threshold_min` |
| Very long (distance) | `very_long_threshold_km` |
| Very long (duration) | `very_long_threshold_min` |
| Hill modifier threshold | `hill_modifier_threshold_m_per_km` |
| Aerobic baseline pace (flat) | `aerobic_baseline_pace_min_km` |
| Long effort baseline pace | `long_effort_baseline_pace_min_km` |
| Technical terrain multiplier | `technical_terrain_multiplier` |

Fixed constants (not athlete-specific):

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Recovery (duration cap) | < 60 min | |
| Night window | 22:00–05:00 | |
| Elevation pace penalty | **0.06 min/km per m/km elev** | Standard trail running rule of thumb |

If the Athlete Config block is missing a required field, fall back to a reasonable default and note it in the output ("baseline pace defaulted to 6.75 min/km — set `aerobic_baseline_pace_min_km` in athlete-profile.md to override").

---

## Classification logic

Work through these checks **in order** — use the first that matches:

1. **Strength** — activity type is gym/strength/indoor_cardio with no meaningful distance (< 1 km), or distance < 1 km with avg HR < 100
2. **Interval / VO2max** — Garmin `trainingEffectLabel` = `VO2MAX`, or `anaerobicTrainingEffect` > 2.5
3. **Tempo / Threshold** — Garmin label = `TEMPO` or `LACTATE_THRESHOLD`, **and duration < 2 h** (if ≥ 2 h, fall through to long/very long — no real tempo session lasts 2+ hours)
4. **Recovery** — duration < 60 min AND (label = `RECOVERY` OR Z1 > 65% of zone time)
5. **Cross-training** — modality is swimming, skiing, cycling, or hiking/walking. **This check comes before the long-duration rules deliberately:** a 2 h ski tour is Cross-training, not "Long effort" — the long/very-long tags are reserved for running. Quality work on skis still gets caught by rules 2–3 above.
6. **Very long / Race sim** — distance > 30 km OR duration > 3 h
7. **Long effort** — distance > 15 km OR duration > 90 min
8. **Aerobic base** — default for everything else

Then check modifiers **independently** (apply as many as fit):

- **Hill modifier** — elevation_per_km > `hill_modifier_threshold_m_per_km` (skip if distance < 2 km or elevation data missing)
- **Technical terrain modifier** — see formula below (running activities only, distance > 2 km)

---

## Technical terrain formula

This detects when pace is significantly slower than the elevation gain alone explains — a signal that terrain was rocky, rooty, snowy, or otherwise slow going beyond just being steep.

```
actual_pace     = duration_min / distance_km
baseline_pace   = aerobic_baseline_pace_min_km     for Aerobic base / Tempo / Interval
                  long_effort_baseline_pace_min_km for Long effort / Very long
                  skip check                        for Recovery / Strength / Cross-training
expected_pace   = baseline_pace + (elev_per_km × 0.06)
flag_technical  = actual_pace > expected_pace × technical_terrain_multiplier
```

**Examples:**
- Flat 7km run in 55 min, 5 m/km elev → actual 7.9, expected 7.05 → ratio 1.12 → not technical
- Hilly 8km in 90 min, 60 m/km elev → actual 11.25, expected 10.35 → ratio 1.09 → not technical (steep but well-explained)
- Rocky 8km in 90 min, 20 m/km elev → actual 11.25, expected 7.95 → ratio 1.42 → **technical ✓**

Note: The flag can also fire for winter/icy conditions, frequent GPS stops, navigation pauses, or fatigue. Mention this in the Why if relevant.

---

## Steps

### 1. Resolve the activity

If the user gives an activity ID, use it directly.

If the user asks for **the most recent** activity of a type, call `mcp__garmin__get_activities_by_date` with `start_date` (last 7 days) and `end_date` (today) and pick the most recent matching activity.

If the user asks for **the longest / biggest / hardest** activity in a period (e.g. "longest run in February"), call `mcp__garmin__get_activities_by_date` for the full date range, filter to the relevant activity type, **sort by distance descending**, and select the top result. Verify the distance looks correct before proceeding.

Confirm the activity name, date, and distance before classifying.

### 2. Fetch activity details

Call `mcp__garmin__get_activity` with `activity_id` as a **number** (not string).

Extract from result:
- `type` → modality
- `distance_meters`, `duration_seconds`, `elevation_gain_meters` (if present)
- `start_time_local` → time of day
- `training_effect_label`, `training_effect` (aerobic), `anaerobic_training_effect`
- `avg_hr_bpm`, `max_hr_bpm`
- Derive pace from distance_meters / duration_seconds

For HR zone breakdown, additionally call `mcp__garmin__get_activity_hr_in_timezones` with `activity_id` (number).

### 3. Compute derived values

```
distance_km  = distance / 1000
duration_min = duration / 60
elev_per_km  = elevationGain / distance_km   (skip if distance_km < 2)
z_total      = sum(hrTimeInZone_1..5)
z1_pct       = hrTimeInZone_1 / z_total × 100
start_hour   = hour from startTimeLocal
actual_pace  = duration_min / distance_km
```

### 4. Apply classification logic

Follow the ordered purpose checks, then evaluate both modifiers.

### 5. Output the classification card

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ACTIVITY CLASSIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Activity:  [Name]
 Date:      [Day, DD Mon YYYY] at [HH:MM]
 Distance:  [X.X km]
 Duration:  [Xh Xm]
 Elevation: [X m] ([X m/km])
 Pace:      [X:XX min/km]

 PURPOSE:   [Tag] [+ Hill] [+ Technical terrain]
 MODALITY:  [Modality]
 TIME:      [Morning / Daytime / Evening / Night]

 Why: [1–2 sentences covering the key signals:
       which threshold triggered the purpose tag,
       whether modifiers fired and why, and any
       notable caveats (e.g. winter conditions,
       race vs training context)]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If classification is genuinely ambiguous, note both candidates and explain which took priority.

---

## Edge cases

- **Garmin TEMPO label on a long session:** Override with Very long / Race sim if duration > 2 h. A 4-hour "tempo" is not a tempo session — Garmin mislabels sustained hard mountain efforts.
- **Skiing and swimming:** Default to Cross-training; apply purpose label upgrade if label = TEMPO etc.
- **Resort (downhill) skiing:** Always Cross-training, and **never apply the Hill modifier** — elevation gain is lift-assisted and does not represent climbing stimulus.
- **Multi-sport:** Apply purpose logic to dominant segment (longest by duration); note modality as Multi-sport. For the **Hill modifier**, use the dominant segment's elevation and distance (from `get_activity_splits`), not the overall totals — cycling legs dilute elev_per_km and can cause the flag to be missed. Example: a hiking drill with 529 m / 10 km = 52.9 m/km qualifies as Hill even if the full multisport activity shows only 32.9 m/km overall.
- **Missing elevation data:** Skip Hill modifier entirely — never infer.
- **Very short activities (< 20 min):** Lean toward Recovery or Strength unless HR/label says otherwise.
- **Technical terrain on road runs:** Valid — wet cobblestones, muddy paths, icy roads all slow pace. Note the likely cause if inferrable.
