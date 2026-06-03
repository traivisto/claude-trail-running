---
name: program-health-check
description: >
  Audits whether recent training is on track with the strategic training
  program and goal race. Produces a red/yellow/green report on phase progress,
  volume trend, long-run progression, strength frequency, hill/technical
  exposure, night sessions, key milestones, and time to race. Reads
  training-program.md, race-card.md, activity-cache.csv, athlete-profile.md,
  and events-log.md. Finnish triggers: "ohjelman tilanne", "tarkista ohjelman
  tilanne", "ollaanko raiteilla", "miten ohjelma etenee", "ohjelmakatselmus",
  "valmistautumisen tila". English: "is my program on track", "weeks to
  race", "program status", "program audit". Do NOT confuse with
  daily-readiness — this audits the strategic program across weeks, not
  today's physical condition ("päivän kunto"). Use also when training-plan
  crosses a phase boundary or follows an extended disruption.
---

# Program Health Check

Run a structured audit of program adherence. The goal is to surface drift
before it becomes a problem: missing key sessions, volume stagnation,
neglected race-specific work, phase boundaries that are slipping.

This skill produces **a report, never a plan**. If the report identifies
something that needs fixing, the athlete then invokes the `training-plan`
skill explicitly.

---

## Step 0: Discover workspace

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**.

---

## Step 1: Load all context (in parallel where possible)

Read these files **using the Read tool, not bash** (see CLAUDE.md File reading rule — bash sees a stale Cowork mount):

1. `WORKSPACE/training-program.md` — phase map, volume ranges, session priorities per phase, current position, explicit race-specific milestones
2. `WORKSPACE/race-card.md` — race date, start time, distance, elevation, terrain notes
3. `WORKSPACE/athlete-profile.md` Athlete Config — `typical_weekly_km`, `long_run_threshold_km`, `hill_modifier_threshold_m_per_km`, HRV/RHR baselines
4. `WORKSPACE/activity-cache.csv` — classified activity history. For 8-week window, read the tail using `offset` near end-of-file with `limit: 200` — covers 100 days even at high session frequency, at much lower token cost than the full file.
5. `WORKSPACE/events-log.md` — illness, travel, disruptions, tests, milestones (last 60 days)

If the cache's most recent date is older than yesterday, run the
`activity-cache-updater` skill first, then continue.

---

## Step 2: Compute time-to-race

From `race-card.md`, extract the race start date. Compute:

- Days until race
- Weeks until race (integer)
- Which phase of the program this falls in, according to the phase map
  in `training-program.md`

Flag if the calendar phase in the program file (e.g. "Phase 2 starts April 20")
does not match the program's **Current Position** section (stale update).

---

## Step 3: Analyse the last 8 weeks from the cache

Group all activities in the cache into ISO weeks for the last 8 weeks. For
each week compute:

- Total running distance (Trail running + Road running modalities)
- Total duration (all modalities)
- Total elevation gain
- Longest single session (distance)
- Count of strength sessions
- Total elevation gain (m D+)
- Count of sessions with elevation gain ≥ 200 m (hill sessions)
- Count of technical-terrain sessions
- Count of night sessions (time_of_day = Night)
- Presence of a back-to-back weekend (Sat long + Sun ≥ 10 km easy)

Also compute a 4-week rolling average of running distance (last 4 weeks vs.
previous 4 weeks) to detect flat vs. progressing volume.

---

## Step 4: Extract program expectations

Parse `training-program.md` for the current phase block. From it determine:

- Expected weekly volume range (e.g. "50–70 km")
- Session priorities for this phase (long run, strength, etc.)
- Phase-specific requirements (e.g. "back-to-back weekends from Phase 2",
  "one night run per block from Phase 2", "overnight simulation in Block 5",
  "power hike drill one per block in Phase 3")
- Strength frequency for this phase
- Explicit milestones listed anywhere in the program file

If the program file lists milestones by date or by block (e.g. "LTHR field
test scheduled May 5", "overnight sim Block 5 week 14"), note them and
check the cache: has this session happened? Is it scheduled?

---

## Step 5: Apply red / yellow / green per area

Use these defaults (skill can override if the program file specifies
tighter/looser tolerances):

| Area | 🟢 Green | 🟡 Yellow | 🔴 Red |
|------|---------|----------|-------|
| Volume vs. phase range | within range for 3+ of last 4 weeks | below range 2+ weeks | below range 3+ weeks OR above peak range consistently |
| Volume trend (4-wk vs. prev 4-wk) | +5% to +20% in a build phase; flat ±5% in recovery/taper | +/- appropriate but inconsistent | stagnant for 8+ weeks in a build phase |
| Long-run progression | steadily increasing, hitting phase targets | plateaued 3+ weeks | plateaued 5+ weeks OR regressed |
| Strength frequency | meeting phase prescription | 50–80% of prescription | <50% of prescription |
| Hill exposure — weekly D+ | ≥ 1200 m D+/week in build phases (race 2934 m D+) | 800–1199 m D+/week | < 800 m D+/week for 3+ weeks |
| Hill exposure — big sessions | ≥ 1 session with ≥ 200 m gain per week in build phases | 1 per 2 weeks | 0 in last 4 weeks |
| Night sessions (if race starts at night) | on pace for phase plan | ≤ 1 in last 8 weeks with race < 12 weeks | 0 in last 8 weeks with race < 8 weeks |
| Back-to-back weekends (Phase 2+) | ≥ 2 per 4-week block | 1 per 4-week block | 0 per 4-week block |
| Key milestones | all on schedule | 1 slipping | 2+ slipping |
| Disruption context | no active illness, no major recent gap | minor recent disruption, recovered | active illness or CLEARED < 7 days ago |

The worst flag across all areas is the headline verdict.

---

## Step 6: Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PROGRAM HEALTH CHECK — [today's date]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Race:           [race name] — [race date]
 Time to race:   X weeks X days
 Current phase:  [Phase name per program file]
 Program says:   [e.g. Phase 2 since Apr 20 — Block 3 peak week]
 Overall:        [🟢 On track / 🟡 Drifting / 🔴 Off track]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Last 8 weeks at a glance**
Week of   Km    Hrs   Elev    Long    Str  Hill≥200m  Tech  Night  B2B
Apr 13    47    6:45  610     18.2    2    1          0     0      yes
[...]

**Checks**

🟢/🟡/🔴 Volume vs. phase range: [one-line summary + the number]
🟢/🟡/🔴 Volume trend:           [4-wk vs. prev 4-wk, + direction]
🟢/🟡/🔴 Long-run progression:    [longest per week for last 6 weeks]
🟢/🟡/🔴 Strength frequency:      [sessions/week vs. prescription]
🟢/🟡/🔴 Hill exposure (D+):       [weekly D+ last 4 weeks vs. 1200 m target; trend]
🟢/🟡/🔴 Hill exposure (sessions): [count sessions ≥200 m gain last 4 weeks]
🟢/🟡/🔴 Night sessions:          [count last 8 weeks; race start time]
🟢/🟡/🔴 Back-to-back weekends:   [count last 4 weeks; phase threshold]
🟢/🟡/🔴 Key milestones:          [bullet list of named milestones with status]
🟢/🟡/🔴 Recent disruptions:      [events log summary]

**What's missing**
- [Concrete gap 1, e.g. "No night run logged in last 8 weeks — race is 11 weeks away and starts at 23:00"]
- [Gap 2]

**Recommended focus for the next 2–3 weeks**
- [1–3 concrete actions the weekly plan should prioritise]

**Stale or missing program info**
- [If training-program.md's Current Position is older than 2 weeks, flag it]
- [If a scheduled milestone date has passed without a cache match, flag it]
```

Keep the whole report under ~1 KB of output — it is a dashboard, not a
coaching essay.

---

## Step 7: Optional — offer next step

End with a single question only if there are 🔴 items:

> "Haluatko että teen seuraavaksi viikko- tai kahden viikon ohjelman, joka
> korjaa nämä puutteet?"

If the response is yes, hand off to the `training-plan` skill. Otherwise
stop — this skill does not modify files or push to Garmin.

---

## Notes

- This skill does **not** update `training-program.md`'s Current Position
  line. That is done manually or by the training-plan skill at phase
  transitions.
- If the race card or training-program file is missing, stop and tell
  the user which file is missing — do not guess.
- If the activity cache is empty for the last 4 weeks (e.g. long illness
  gap), skip most quantitative checks and focus the report on "ready to
  resume" context: days since last session, events log status, baseline
  restoration.
- This skill is compatible with any race type — it weights night sessions
  only if the race card mentions a night/late-evening start, and weights
  hill exposure proportional to the race's elevation profile.
