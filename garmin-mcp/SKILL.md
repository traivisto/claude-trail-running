---
name: garmin-mcp
description: >
  Reference document for Garmin MCP usage in this coaching system. Read this before
  making Garmin MCP tool calls — it maps use cases to the right tools, documents
  response field names, and captures known quirks. Not a workflow skill — use it
  as a lookup when writing or debugging other skills.
---

# Garmin MCP Reference

Comprehensive reference for Garmin MCP usage in this coaching system. Other skills
read this document before making Garmin API calls.

**Starting the MCP server** (manually in PowerShell if needed):
```
cmd /c uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp
```
Token management: `~/.garminconnect` (garth library). Re-authenticate:
```
uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth
```

---

## Domain 1: Recovery & Health — daily recovery data

### `get_sleep_summary` ⭐ lightest sleep data
```
params: { date: "YYYY-MM-DD" }
```
Returns ~350 B. **Always use this** instead of `get_sleep_data` (which returns ~200 KB of time-series data).

Key fields:
```json
{
  "sleep_hours": 8.32,
  "sleep_score": 87,
  "sleep_score_qualifier": "GOOD",
  "avg_overnight_hrv": 42.0,
  "deep_sleep_seconds": 3780,
  "light_sleep_seconds": 19740,
  "rem_sleep_seconds": 6420,
  "awake_seconds": 420,
  "awake_count": 0,
  "avg_sleep_stress": 16.0,
  "deep_sleep_percent": 12.6,
  "light_sleep_percent": 65.9,
  "rem_sleep_percent": 21.4
}
```

### `get_body_battery`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Returns a list of days:
```json
[{
  "date": "2026-05-16",
  "charged": 70,
  "drained": 0,
  "body_battery_level": "HIGH",   // HIGH / MEDIUM / LOW
  "current_feedback": null,
  "events": []
}]
```
Interpretation: `charged` = charged overnight, `drained` = consumed so far today.

### `get_rhr_day`
```
params: { date: "YYYY-MM-DD" }
```
Returns resting heart rate. Fields:
```json
{
  "allMetrics": {
    "metricsMap": {
      "WELLNESS_RESTING_HEART_RATE": [
        { "value": 52.0, "calendarDate": "2026-05-16" }
      ]
    }
  }
}
```
Extract: `allMetrics.metricsMap.WELLNESS_RESTING_HEART_RATE[0].value`

### `get_training_readiness`
```
params: { date: "YYYY-MM-DD" }
```
Returns a list (usually 1 item):
```json
[{
  "date": "2026-05-16",
  "score": 84,
  "level": "HIGH",                        // HIGH / MODERATE / LOW
  "feedback": "WELL_RECOVERED",
  "context": "AFTER_WAKEUP_RESET",
  "sleep_score": 87,
  "sleep_factor_percent": 84,
  "sleep_factor_feedback": "GOOD",
  "recovery_time_hours": 0.0,
  "recovery_factor_percent": 99,
  "hrv_factor_percent": 96,
  "hrv_factor_feedback": "GOOD",
  "hrv_weekly_avg": 38,
  "training_load_factor_percent": 100,
  "training_load_feedback": "VERY_GOOD",
  "stress_history_factor_percent": 70,
  "stress_history_feedback": "GOOD",
  "sleep_history_factor_percent": 81,
  "acute_load": 404
}]
```

### `get_training_status`
```
params: { date: "YYYY-MM-DD" }
```
```json
{
  "date": "2026-05-16",
  "training_status_feedback": "PRODUCTIVE_3",   // ks. alla
  "sport": "RUNNING",
  "acute_load": 404,
  "chronic_load": 548,
  "load_ratio": 0.74,
  "acwr_status": "LOW",          // LOW / OPTIMAL / HIGH / VERY_HIGH
  "acwr_percent": 29,
  "training_balance_feedback": "AEROBIC_HIGH_SHORTAGE",   // ks. alla
  "vo2_max": 46.0,
  "vo2_max_precise": 46.2,
  "monthly_load_aerobic_low": 1586.7,
  "monthly_load_aerobic_high": 440.6,
  "monthly_load_anaerobic": 173.8
}
```

**training_status_feedback values:**
`PEAKING` / `MAINTAINING` / `RECOVERY` / `DETRAINING` / `PRODUCTIVE_1/2/3` / `UNPRODUCTIVE` / `STRAINED` / `OVERREACHING`
- `RECOVERY` = intentional recovery (ok)
- `DETRAINING` = load has dropped too low (warning)

**training_balance_feedback values:**
- `AEROBIC_HIGH_SHORTAGE` = Z3–Z4 (tempo/threshold) deficit — a long easy run won't fix this
- `AEROBIC_LOW_SHORTAGE` = Z1–Z2 base work deficit
- `ANAEROBIC_SHORTAGE` = anaerobic work deficit
- `BALANCED` = balance ok

### `get_hrv_data`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Returns HRV trend across multiple days. Use when history is needed — single overnight HRV is also available from `get_sleep_summary` (`avg_overnight_hrv`).

### `get_stress_data`
```
params: { date: "YYYY-MM-DD" }
```
⚠️ Returns ~35 KB of time-series data. Use only if stress level is relevant — otherwise skip.

---

## Domain 2: Activity fetching and analysis

### `get_activities_by_date` ⭐ primary fetch tool
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Returns all activities for the date range in a single call — no pagination.

Key fields per activity:
```
activityId          (number — IMPORTANT: always use number type, not string)
activityName
startTimeLocal      "2026-05-13T20:14:12"
distance            in metres → divide by 1000 for km
duration            in seconds → divide by 60 for minutes
activityType.typeKey   e.g. "trail_running", "running", "strength_training"
averageHR
maxHR
calories
trainingEffectLabel    "AEROBIC_BASE" / "TEMPO" / "VO2MAX" / "ANAEROBIC_CAPACITY" / "RECOVERY"
aerobicTrainingEffect
anaerobicTrainingEffect
directWorkoutRpe    (integer or null — Garmin's own RPE value)
directWorkoutFeel   (numeric code or null → map: 1=very_weak, 2=weak, 3=normal, 4=strong, 5=very_strong)
```

⚠️ **Elevation data is not in this call** — use `get_activity_splits` per activity.

### `get_activity`
```
params: { activity_id: 12345678 }   // number, not string
```
Full details for a single activity. Use when `directWorkoutRpe` / `directWorkoutFeel` or other fields not returned by `get_activities_by_date` are needed.

### `get_activity_splits` ⭐ elevation source
```
params: { activity_id: 12345678 }   // number
```
Returns lap-level data. Sum `elevation_gain_meters` across all laps → total elevation for the activity.
Note: `get_activities_by_date` does not include elevation — `get_activity_splits` is the only reliable source.

### `get_activity_typed_splits`
```
params: { activity_id: 12345678 }   // number
```
Separates an interval session into warmup / work / cooldown phases. Use for interval analysis — whole-session average pace/HR is misleading when it includes warmup and cooldown.

### `get_activity_split_summaries`
```
params: { activity_id: 12345678 }
```
Alternative to `get_activity_typed_splits` — returns a summary of split types. Use when only a summary is needed, not each individual interval.

---

## Domain 3: Training Load & Trends

### `get_training_load_trend`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Returns load trend across multiple days — acute load, chronic load, load ratio. Use for weekly or monthly load overview.

### `get_training_readiness` + `get_training_status`
See Domain 1 above — both include training load data.

---

## Domain 4: Workout creation and scheduling

### `upload_workout` / `create_walk_run_workout` / `create_strength_workout`
Creates a workout in Garmin Connect. Use `upload_workout` when the workout has multiple steps (warmup, repeats, cooldown).

**⚠️ Critical rules when creating workouts:**

1. **Use absolute bpm values** — never Garmin zone numbers (`workoutTargetTypeId: 4`, fields `targetValueOne` / `targetValueTwo`). Garmin's built-in zones use %HRmax and do not match LTHR-based boundaries.

2. **Always prefix with `[Coach]`** so coach workouts can be identified. E.g. `[Coach] Hill repeats 5x4 min Z4`.

3. **Z1/Z1–Z2 easy runs use a single step** — the whole run is the easy effort, no separate warmup/cooldown.

4. **Interval sessions (hill repeats, track)**: warmup, recoveries, and cooldown are lap-button-based (`conditionType: PRESS_LAP`) — only the active efforts are time-based. Reason: fixed time targets for non-effort phases are impractical on trails.

5. **Tempo/threshold sessions**: three time-based steps: warmup (10 min, no target) + main effort (HR target) + cooldown (10 min, no target).

6. **`endCondition` is an object + `endConditionValue` is a separate field** ⚠️ — the API returns a 400 error if you use the old format (`conditionType` + `endConditionValue` as separate siblings). Correct structure for a time-based step:
   ```json
   "endCondition": {
     "conditionTypeId": 2,
     "conditionTypeKey": "time"
   },
   "endConditionValue": 3300
   ```
   For lap-button steps (`conditionTypeId: 1, conditionTypeKey: "lap.button"`) the `endConditionValue` field is not needed. **Do not put `endConditionValue` inside the `endCondition` object** — it causes time=0 in the calendar even though the upload succeeds.

**HR target values:** Always read zone boundaries from the `Athlete Config` block in `athlete-profile.md`. Use `targetValueOne` / `targetValueTwo` (bpm) with `workoutTargetTypeId: 4`. Never hardcode specific bpm values here.

**Sport type:**
- Road running: `sportTypeId: 1, sportTypeKey: "running"`
- Trail running: `sportTypeId: 1, sportTypeKey: "trail_running"`
- Strength training: `sportTypeId: 5, sportTypeKey: "strength_training"`

### `schedule_workout`
```
params: { workout_id: 12345, date: "YYYY-MM-DD" }
```
Schedules a workout to the Garmin calendar. Always call after `upload_workout`.
**Only after user approval** — do not schedule before the user has confirmed the plan.

### `get_scheduled_workouts`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Returns workouts scheduled to the calendar. Check the `completed` field before deleting.

### `delete_workout`
```
params: { workout_id: 12345 }
```
⚠️ **Never delete a workout with `completed = true`.** It is training history.

---

## Use-case cookbook

### Daily readiness check
Call in parallel (this order follows the daily-readiness skill):
1. `get_sleep_summary` (date: today) — HRV, sleep score
2. `get_training_readiness` (date: today) — readiness score
3. `get_training_status` (date: today) — training status, ACWR
4. `get_body_battery` (start+end: today) — body battery
5. `get_rhr_day` (date: today) — resting HR

### Activity cache update
1. `get_activities_by_date` (start: last cached date + 1, end: today)
2. Per new activity: `get_activity_splits` (activity_id: number) → elevation
3. If needed: `get_activity` per activity → RPE / feel

### Interval analysis (do not use whole-session averages)
1. `get_activity_typed_splits` → extract only "INTERVAL"-type segments
2. Whole-session avg_hr / pace is misleading — the relevant data is the interval phase itself

### Workout creation and scheduling (training-plan skill)
1. Build workout object (see Domain 4 rules)
2. `upload_workout` → get `workout_id`
3. `schedule_workout` (workout_id, date)
4. Repeat per session

### Cleaning up old [Coach] workouts before a new plan
1. `get_scheduled_workouts` (full date range of new plan)
2. Filter: name starts with `[Coach]` AND `completed = false`
3. `delete_workout` per removed workout

---

## Known quirks

| # | Problem | Solution |
|---|---------|----------|
| 1 | `activity_id` must be `number`, not `string` | Always convert: `int(activity_id)` or `Number(activityId)` |
| 2 | `get_sleep_data` returns ~200 KB of time-series data | Always use `get_sleep_summary` (~350 B) instead |
| 3 | Garmin HR zones in the API use %HRmax boundaries (88/106/123/141/157 bpm) | Use absolute bpm values from athlete-profile.md |
| 4 | `get_activity_hr_in_timezones` uses the same %HRmax boundaries | Calculate your own distribution with LTHR boundaries from `get_activity_splits` data |
| 5 | Elevation data is missing from `get_activities_by_date` | Always fetch `get_activity_splits` per activity to calculate elevation |
| 6 | `training_balance_feedback: AEROBIC_HIGH_SHORTAGE` = Z3–Z4 deficit | A long easy run won't fix this — a tempo/threshold/interval session is needed |
| 7 | `RECOVERY` training status ≠ `DETRAINING` | Recovery = intentional recovery (ok). Detraining = load dropped too low (warning). |
| 8 | `vo2_max` vs `vo2_max_precise` | Use `vo2_max_precise` for more accurate analysis. But the lab-confirmed value in athlete-profile.md overrides both Garmin estimates. |
| 9 | `delete_workout` returns Python error `'dict' object has no attribute 'status_code'` | MCP wrapper bug — the operation succeeds anyway. Verify with `get_scheduled_workouts` that the workout was removed. |
| 10 | `get_scheduled_workouts` does not return past weeks | API returns empty list if all workouts are completed or the date range is in the past. Does not mean no workouts existed — they just no longer appear in the API. |

---

## Future: script specification

*To be filled in phase 2, when moving from MCP to direct API calls.*

Garmin käyttää OAuth2-autentikointia (garth-kirjasto hoitaa token-hallinnan). Keskeisiä REST-endpointteja:
- Aktiviteetit: `GET /activitylist-service/activities/search/activities`
- Yksittäinen aktiviteetti: `GET /activity-service/activity/{activityId}`
- Splits: `GET /activity-service/activity/{activityId}/splits`
- Sleep: `GET /wellness-service/wellness/dailySleepData/{date}`
- HRV: `GET /hrv-service/hrv/{date}`
- Training readiness: `GET /metrics-service/metrics/trainingReadiness/{date}`
