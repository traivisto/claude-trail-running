---
name: training-plan
description: "Creates a structured training plan for the athlete's trail running coaching, saves it as a draft for review, and — after explicit approval — pushes workouts to Garmin Connect calendar. Use this skill whenever the user asks for a training plan, program, or schedule. Trigger phrases include: make a training plan, plan my week, plan the next 2 weeks, put workouts on the calendar, what should I train this week. Finnish triggers: tee ohjelma, suunnittele ensi viikko, tee 2 viikon ohjelma, laita treenit kalenteriin, mitä treenaan tällä viikolla. Also use when the user wants to adjust or replace an existing plan, or asks to push a draft plan to Garmin."
---

# Training Plan Skill

Creates a coaching-quality training plan, saves it as a draft, presents it for approval, then pushes to Garmin on confirmation.

## Step 0: Resolve athlete directory and load athlete config

Resolve **ATHLETE_DIR** as defined in `CLAUDE.md` → "Athlete directory": `$COACH_ATHLETE_DIR` if set, otherwise Glob `athletes/*/athlete-profile.md` (exactly one match → its directory; several → ask which athlete). Do not use bash `find`.

Read `ATHLETE_DIR/athlete-profile.md` and extract the `Athlete Config` block — you need the HR zone boundaries (`hr_zone_z1_max`, `hr_zone_z2_range`, `hr_zone_z3_range`, `hr_zone_z4_range`, `hr_zone_z5_range`) to set correct bpm targets for Garmin workouts. These vary per athlete and must not be hardcoded.

## Key workspace files

- **ATHLETE_DIR/training-program.md** — phase/block context, volume ranges, session priorities. Always read this first.
- **ATHLETE_DIR/activity-cache.csv** — classified activity history. Read last 14 days for load context.
- **ATHLETE_DIR/events-log.md** — illness, travel, disruptions. Explains anomalies the watch can't.
- **ATHLETE_DIR/athlete-profile.md** — HR zones, biometrics. Already loaded in Step 0.
- **ATHLETE_DIR/current-plan.md** — active training plan (rolling, always overwritten when a new plan is created).

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

Read `ATHLETE_DIR/current-plan.md` if it exists. Check:
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

1. `training-program.md` — current phase, active goals, session priority list, volume range, and the program's rules: **flexibility rules** (protected sessions, minimum week, illness/travel), **other sports and season rules**, and the **test calendar** (see `training-program/SKILL.md` for the structure)
2. `activity-cache.csv` — last 14 days: total km, elevation, session types, last hard session, rest days, consecutive training days. Read only the tail using `offset` near end-of-file with `limit: 50` — this gives plenty of context for a 14-day window at minimal token cost. For the weekly load figures also run `python3 scripts/program_health.py` (columns RunMin, Trail, RunKm, Hrs, D+) and quote **running minutes (and D+) first, km second**: for a trail runner time is the load measure, km depends on terrain. The same output also lists **zone minutes per week** (Z1-Z5, and trail separately) from `hr-histograms.csv`; quote them for the zone mix of recent weeks, and note when `cov` shows runs without a histogram (then the zone minutes are a lower bound). For one key session use `scripts/hr_zones.py` / the HR-zone rule in `CLAUDE.md`.
3. `events-log.md` — any entries in last 14 days

Also fetch live readiness data if available (these can fail silently):
- `mcp__garmin__get_body_battery` (today)
- `mcp__garmin__get_morning_training_readiness` (today)
- `mcp__oura__oura_readiness` with `{"date": "YYYY-MM-DD"}` (today)

**Load trend check:** also call `mcp__garmin__get_training_load_trend` for at least the last 4 weeks (6 weeks preferred). Look at chronic load (CTL) and its direction, not only today's ACWR — Garmin's "optimal" range is computed from CTL itself (0.8–1.5 × CTL), so ACWR can read OPTIMAL while the base is eroding. Record in the plan's Context line: CTL now, CTL peak of the last 6 weeks, and weekly running minutes (with km as a secondary figure) for the last 3 weeks. If CTL is more than 15 % below the 6-week peak, say so and state whether the drop is planned (deload/taper) or due to missed sessions.

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

Budget the week in **running minutes per HR zone** (plus D+), not in km. Time in zone is what builds a trail runner's fitness; km depends on terrain and conditions and cannot be compared between trail runs. Rules:
- Take the phase's volume range from training-program.md: normal week and deload week as running minutes. Apply the program's season rules (e.g. winter) and its other-sports rule (which sessions skiing, cycling etc. may replace) to the range. If the program states volume in km, convert it to minutes with the athlete's recent road minutes-per-km (`program_health.py`: RunMin / RunKm of road-only weeks) and say so in the plan; suggest restating the program in hours when it is next revised.
- Plan every session as duration + absolute bpm zone (as the Garmin workouts are). Count warm-up and cool-down in the zone they are run in; strides/hill sprints are listed separately, not as zone time. Respect the program's polarization rule (no Z3 by accident).
- **Trail running** (Garmin activity type Trail running, which the athlete picks whenever the route leaves roads/built paths): give time and HR zone only. Never a pace target and never a km figure.
- km are only a rough estimate for road runs, derived from the athlete's recent road pace, and secondary.
- When returning from disruption, target the lower end. Recovery/deload weeks: use the program's stated deload range; if it states none, ~75–80% of the normal-week running-minute target (the ratio the program itself uses).
- **Flexibility rules from the program apply:** when the athlete is ill or travelling, plan the program's **minimum week** (one quality, one strength, one long run); after illness easy only and **no catching up** missed quality; the protected sessions (Tuesday-style quality, weekend long run) are placed first.
- **Tests:** if a test from the program's test calendar falls in the plan's range, schedule it as written (venue, protocol, e.g. indoor lap counting when there is no GPS), keep it clear of strength days (72 h before when the program says so), and do not add a hard session next to it. A baseline test missed in the previous week is done now or dropped, as the program says.

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

### Step 4b: Archive the previous plan before overwriting

Before writing a new `current-plan.md`, check that the existing plan is already in `ATHLETE_DIR/arkisto/` (compare its title/date range against `ATHLETE_DIR/arkisto/training-plan-*.md`). If it is not, copy it to `ATHLETE_DIR/arkisto/training-plan-YYYY-MM-DD.md` (date = today) **first**, then overwrite. Never overwrite `current-plan.md` before this check; a plan that was only in `current-plan.md` is otherwise lost.

### Rest and load justifications in the plan

When the plan explains a rest day or an easy/hard choice, quote measured numbers (last hard session, 7-day load, ACWR, readiness, HRV) and say whether the reason is program structure or a physiological need — see "Load and rest reasoning rule" in `CLAUDE.md`.

---

## Step 5: Save as Draft

Save to `ATHLETE_DIR/current-plan.md`. This is always the same file — it gets overwritten each time a new plan is created. History is preserved in the Garmin calendar (completed workouts) and the activity cache.

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

**Total running time:** X min — planned, summed from the sessions above: Z1 X · Z2 X · Z3 X · Z4 X · Z5 X (strides/sprints separate) · D+ ~X m
**Trail:** X min (time + HR zone only, no km or pace)
**Road km (rough estimate, road runs only):** ~X km
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
1. Single step: time-based, HR target matching the zone (Z1: from a low floor up to `hr_zone_z1_max`; Z1–Z2: up to the top of `hr_zone_z2_range`; both read from `Athlete Config`)

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
