---
name: training-plan
description: "Creates a structured training plan for the athlete's trail running coaching, saves it as a draft for review, and — after explicit approval — pushes workouts to Garmin Connect calendar. Use this skill whenever the user asks for a training plan, program, or schedule. Trigger phrases include: make a training plan, plan my week, plan the next 2 weeks, put workouts on the calendar, what should I train this week. Finnish triggers: tee ohjelma, suunnittele ensi viikko, tee 2 viikon ohjelma, laita treenit kalenteriin, mitä treenaan tällä viikolla. Also use when the user wants to adjust or replace an existing plan, or asks to push a draft plan to Garmin."
---

# Training Plan Skill

Creates a coaching-quality training plan, saves it as a draft, presents it for approval, then pushes to Garmin on confirmation.

## Step 0: Discover workspace and load athlete config

Run this to find the workspace directory:

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. Read `WORKSPACE/athlete-profile.md` and extract the `Athlete Config` block — you need the HR zone boundaries (`hr_zone_z1_max`, `hr_zone_z2_range`, `hr_zone_z3_range`, `hr_zone_z4_range`, `hr_zone_z5_range`) to set correct bpm targets for Garmin workouts. These vary per athlete and must not be hardcoded.

## Key workspace files

- **WORKSPACE/training-program.md** — phase/block context, volume ranges, session priorities. Always read this first.
- **WORKSPACE/activity-cache.csv** — classified activity history. Read last 14 days for load context.
- **WORKSPACE/events-log.md** — illness, travel, disruptions. Explains anomalies the watch can't.
- **WORKSPACE/athlete-profile.md** — HR zones, biometrics. Already loaded in Step 0.
- **WORKSPACE/current-plan.md** — active training plan (rolling, always overwritten when a new plan is created).

---

## Step 1: Require duration and confirm date range

If the user has not specified how long the plan should cover, ask before doing anything else:

> "How long should the plan cover? (e.g. 5 days, 1 week, 2 weeks)"

Do not guess or assume a default duration. A plan without a defined end date is incomplete.

### Resolving "next week" ambiguity

When the user says "next week" or similar, determine today's weekday before proceeding:

- **If today is Monday:** "next week" is ambiguous — could mean the rest of this calendar week (Tue–Sun) OR the next full calendar week (Mon–Sun, starting in 6 days). Always confirm:
  > "Do you mean this week (Tue [D.M.]–Sun [D.M.]) or next week starting Monday ([D.M.]–[D.M.])?"
  Fill in the actual dates before asking.

- **Any other weekday:** "next week" = next calendar Mon–Sun. No clarification needed — proceed.

Do not assume and do not proceed until the date range is confirmed when today is Monday.

---

## Step 2: Check for conflicts with existing plans

Read `WORKSPACE/current-plan.md` if it exists. Check:
- Its **status** (Draft or Approved)
- Its **date range**

**If an Approved plan overlaps with the requested dates:**
Flag it and confirm with the user before proceeding:

> "You have an active plan [dates] with Garmin workouts on [X, Y, Z]. Replace them with the new plan?"

If the user confirms, proceed — Step 6a will automatically clean up the old [Coach] workouts from Garmin before scheduling new ones.

**If only a Draft plan exists:** Silently overwrite — it was never pushed to Garmin.

---

## Step 3: Gather context

Read these in parallel **using the Read tool, not bash** (see CLAUDE.md File reading rule — bash sees a stale mount):

1. `training-program.md` — current phase, active goals, session priority list, volume range
2. `activity-cache.csv` — last 14 days: total km, elevation, session types, last hard session, rest days, consecutive training days. Read only the tail using `offset` near end-of-file with `limit: 50` — this gives plenty of context for a 14-day window at minimal token cost.
3. `events-log.md` — any entries in last 14 days

Also fetch live readiness data if available (these can fail silently):
- `mcp__garmin__get_body_battery` (today)
- `mcp__garmin__get_morning_training_readiness` (today)
- `mcp__oura__oura_readiness` with `{"date": "YYYY-MM-DD"}` (today)

If Garmin/Oura is unavailable, proceed with cache data only — note it briefly in the plan context line.

---

## Step 4: Build the plan

### Determine the week's character

Based on the training-program.md block rhythm (Build → Peak → Recovery) and recent load from the cache, decide if this is a build week, peak week, or recovery week. Post-illness or after a very hard block, default to recovery/rebuild framing even if the calendar says otherwise.

### Session selection

Use the **session priority list** from the current phase in training-program.md as your guide. For Phase 1 (Foundation):
1. Long run (Z1–Z2) — the week's anchor, scheduled on a day with no hard session before or after
2. Strength (30 min) — 1×/week early Foundation, aim for 2×/week once running volume is re-established. Never the day before a long run.
3. Easy aerobic runs (Z1) — genuine recovery pace, at or below `hr_zone_z1_max` from Athlete Config
4. Quality session (tempo Z4) — only in build/peak weeks, never when returning from illness or injury

### Volume

Stay within the phase's volume range from training-program.md. When returning from disruption, target the lower end. Recovery weeks: ~65% of recent peak.

### Day-by-day placement

Fit sessions to the requested date range. Prioritise:
- Long run on a day where the next day can be easy or rest
- Strength on easy-run days (after the run) or standalone rest days
- Back-to-back long weekends only in Phase 2+
- Rest days are real days — include at least one per 7-day window

**Hard constraints — check these before finalising any plan:**
- **Never schedule strength on two consecutive days.** Minimum 48 h between strength sessions. If 2×/week, place on non-adjacent days (e.g. Tue + Thu).
- **Never schedule strength the day immediately before the long run.** The day before the long run must be easy running or full rest only.

---

## Step 5: Save as Draft

Save to `WORKSPACE/current-plan.md`. This is always the same file — it gets overwritten each time a new plan is created. History is preserved in the Garmin calendar (completed workouts) and the activity cache.

Use this structure:

```
# Training Plan: [start date full] – [end date full]

**Status:** Draft — not yet pushed to Garmin
**Created:** [today's date] · **Phase:** [current phase name]
**Context:** [1–2 sentences: why this plan looks the way it does — post-illness, build week, etc.]

---

## [Weekday DD.M.] — [Session label]
[What to do: duration, HR zone (with bpm values), terrain notes, any coaching cue]

## [Weekday DD.M.] — Rest / Swimming / Strength
[Brief note on what/why]

[...one section per day...]

---

**Total running volume:** ~X km
**Strength sessions:** X
**Longest session:** X min
```

---

## Step 6: Present for approval

Show the plan and explicitly wait for approval. Say something like:

> "Here is your plan [dates]. Review it — any changes, or shall I push it to Garmin?"

**For each quality session in the plan** (hill repeats, intervals, tempo, threshold), include a short Garmin structure preview directly below the session description. Format:

```
📋 Garmin structure:
  • Warmup — lap button
  • × [N]: [X] min [zone] ([bpm]–[bpm] bpm) — time-based
  • Recovery — lap button
  • Cooldown — lap button
```

For simple aerobic runs, no preview is needed — the structure is straightforward (warmup / main / cooldown, all time-based).

Do not touch Garmin until the user confirms. If changes are requested, edit the file and show the updated plan. Repeat until approved.

---

## Step 7: Push to Garmin (on approval only)

### Step 7a: Clean up existing [Coach] workouts for the plan's date range

Before uploading any new workout, remove stale coach-created workouts that would otherwise pile up alongside the new ones.

1. Call `mcp__garmin__get_scheduled_workouts` for the plan's full date range.
2. From the results, collect every workout whose name starts with `[Coach]`.
3. For each such workout, check the `completed` field:
   - **`completed = false` (or absent/null)** → safe to delete. Call `mcp__garmin__delete_workout` with the workout ID.
   - **`completed = true`** → the athlete has already run this session. **Never delete it.** Skip silently.
4. This step silently covers both formally planned workouts and ad-hoc ones (like individually scheduled sessions added outside a training plan).

**Safety rule (non-negotiable):** A completed workout is a training record. It must never be deleted by this skill under any circumstances, even if a newer plan covers the same date.

---

For each **running session** in the plan, create a structured workout and schedule it:

### Workout structure

**Z1 and Z1–Z2 easy runs** are a single step — the whole run is the easy effort, no warmup/cooldown needed:
1. Single step: time-based, HR target matching the zone (e.g. 100–124 bpm for Z1, 100–141 bpm for Z1–Z2)

**Tempo and threshold runs** have three time-based steps:
1. Warmup: 10 min, no HR target (`workoutTargetTypeId: 1, workoutTargetTypeKey: "no.target"`)
2. Main effort: time-based, with HR target
3. Cooldown: 10 min, no HR target

**Hill/interval quality sessions** (mäkitoistot, track intervals) use lap-button steps for warmup, recovery, and cooldown — only the active effort is time-based. This is because terrain makes fixed durations impractical for non-effort phases. Structure:
1. Warmup: `conditionType: PRESS_LAP`, no HR target
2. Repeat × N:
   a. Active effort: time-based (e.g. 4 min), Z4 HR target
   b. Recovery: `conditionType: PRESS_LAP`, no HR target
3. Cooldown: `conditionType: PRESS_LAP`, no HR target

### HR targets — always absolute bpm, never zone numbers
Garmin's built-in zone numbers use %HRmax and do not match LTHR-based zones. Always use `targetValueOne` / `targetValueTwo` with `workoutTargetTypeId: 4`. Read the actual bpm boundaries from `athlete-profile.md` Athlete Config (`hr_zone_z1_max`, `hr_zone_z2_range`, etc.).

Example mapping (replace with athlete's actual values):

| Zone | targetValueOne | targetValueTwo |
|------|---------------|---------------|
| Z1 only | 100 | hr_zone_z1_max |
| Z1–Z2 | 100 | hr_zone_z2_range upper |
| Z3 | hr_zone_z3_range lower | hr_zone_z3_range upper |
| Z4 (tempo) | hr_zone_z4_range lower | hr_zone_z4_range upper |
| Z5 | hr_zone_z5_range lower | hr_zone_z5_range upper |

### Workout naming
Always prefix with `[Coach]`. Examples:
- `[Coach] Easy run 50 min Z1`
- `[Coach] Aerobic base 80 min Z1-Z2`
- `[Coach] Trail run 75 min Z1-Z2`
- `[Coach] Tempo 45 min Z4`

### Sport type
- Road running: `sportTypeId: 1, sportTypeKey: "running"`
- Trail running: `sportTypeId: 1, sportTypeKey: "trail_running"`

### After uploading each workout
Immediately call `schedule_workout` with the workout ID and the correct date.

### Strength training workouts
Strength sessions are planned sessions and belong in the Garmin calendar. Create a simple workout:
- Name: `[Coach] Strength training 30 min`
- Sport: `sportTypeId: 5, sportTypeKey: "strength_training"`
- Structure: one step, 30 minutes, no HR target (`workoutTargetTypeId: 1`)
- Schedule to the correct date

### What NOT to push to Garmin
Rest days, swimming, walking. These are spontaneous or extra activities — note them in the plan file but do not create Garmin workouts.

---

## Step 8: Finalise

After all Garmin workouts are scheduled, update `current-plan.md` status line:

```
**Status:** Approved — pushed to Garmin [today's date]
```

If the plan represents a meaningful milestone (first week back, new long-run distance, phase transition), also update the **Current Position** section in `training-program.md`.

Confirm to the user: which workouts are now in Garmin, on which dates, with which HR targets.
