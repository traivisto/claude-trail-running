---
name: program-health-check
description: >
  Audits whether recent training is on track with the strategic training
  program and goal race. Produces a red/yellow/green report on phase progress,
  volume trend, long-run progression, strength frequency, hill/technical
  exposure, night sessions, key milestones, and time to race. Reads
  training-program.md, race-card.md, activity-cache.csv, athlete-profile.md,
  and events-log.md. Triggers: "is my program on track", "weeks to race",
  "program status", "program audit", "how is the program progressing",
  "training status check", "race preparation status". Finnish triggers:
  "ohjelman tilanne", "tarkista ohjelman tilanne", "ollaanko raiteilla",
  "miten ohjelma etenee", "ohjelmakatselmus", "valmistautumisen tila".
  Do NOT confuse with
  daily-readiness — this audits the strategic program across weeks, not
  today's physical condition. Use also when training-plan crosses a phase
  boundary or follows an extended disruption.
---

# Program Health Check

Run a structured audit of program adherence. The goal is to surface drift
before it becomes a problem: missing key sessions, volume stagnation,
neglected race-specific work, phase boundaries that are slipping.

This skill produces **a report, never a plan**. If the report identifies
something that needs fixing, the athlete then invokes the `training-plan`
skill explicitly.

---

## Step 0: Resolve athlete directory

Resolve **ATHLETE_DIR** as defined in `CLAUDE.md` → "Athlete directory": `$COACH_ATHLETE_DIR` if set, otherwise Glob `athletes/*/athlete-profile.md` (exactly one match → its directory; several → ask which athlete). Do not use bash `find`.


---

## Step 1: Load all context (in parallel where possible)

Read these files **using the Read tool, not bash** (see CLAUDE.md File reading rule):

1. `ATHLETE_DIR/training-program.md` — phase map, volume ranges, session priorities per phase, current position, explicit race-specific milestones
2. `ATHLETE_DIR/race-card.md` — race date, start time, distance, elevation, terrain notes
3. `ATHLETE_DIR/athlete-profile.md` Athlete Config — `long_run_threshold_min` (long-run judgement, by duration), `long_run_threshold_km` (used by the script only for the back-to-back column), `hill_modifier_threshold_m_per_km`, HRV/RHR baselines
4. `ATHLETE_DIR/events-log.md` — illness, travel, disruptions, tests, milestones (the script also prints the last 60 days; read the file for older context)

The activity cache itself is read by `scripts/program_health.py` (Step 3), not by you. Before running it, apply the **Activity cache sync rule** in `CLAUDE.md` (single
source of truth for cache freshness): call `get_activities_by_date` from the day
after the last cached date through today, and run the `activity-cache-updater`
skill if anything new is returned. Do not skip this because the cache looks recent.

---

## Step 2: Compute time-to-race (skip if no active race)

Check `athlete-profile.md` Current Goal / `training-program.md` header first.
If no next race is decided (the program is an interim/maintenance phase —
e.g. "Next race: Not yet decided"), **skip time-to-race entirely.** This is
not an error state — race-card.md may still hold the most recent *completed*
race for reference, but it is not a countdown target. Report the header as
"No active race — interim/maintenance phase check" and move on to Step 3.

If a next race **is** decided, extract the race start date from
`race-card.md` and compute:

- Days until race
- Weeks until race (integer)
- Which block of the program this falls in (older programs say "phase"), according to the block map
  in `training-program.md`

Flag if the calendar block in the program file (e.g. "Block 4 starts 21.12.")
does not match the program's **Current Position** section (stale update).

---

## Step 3: Weekly aggregates (computed by script)

Do **not** compute these by hand. Run `python3 scripts/program_health.py [weeks]` (from the workspace
root, `python3` on Linux; default 8 ISO weeks) after the sync in Step 1. It is the single place where
the aggregates are defined, in every environment (interactive session, Telegram), so its docstring is the
authority for the exact definitions. Per ISO week it prints: running km, running minutes (RunMin), minutes of Trail running (Trail), all-modality hours, D+, longest run
(km/min), strength sessions, hill sessions (>= 200 m), technical-terrain sessions, night sessions, quality
sessions (purpose, name keyword or anaerobic TE > 2.5), grey-zone sessions (avg-HR proxy from `Athlete
Config`), back-to-back weekends (Sat long run + Sun >= 10 km); plus the 4-week volume trend (average running
minutes, with km alongside, per non-deload week, 4 vs the previous 4), the dates of quality and strength sessions, **zone minutes per week** (Z1-Z5, trail separately, from `hr-histograms.csv`; `cov` shows runs without a histogram, then the zone minutes are a lower bound), D+ per calendar
month, night sessions in 8 weeks and the last 60 days of the events log. Planned deload weeks are marked
`D` (read from `training-program.md`) and are excluded from the trend.

The script only counts. Whether a column applies, and every red/yellow/green verdict, comes from
Steps 4-5 and the current phase text. If a number looks wrong, check the cache row with the Read tool
rather than recomputing the whole table.

---

## Step 4: Extract program expectations

Parse `training-program.md` for the current phase block. If it has a **Scored areas** section, only those areas are scored (everything else follows the applicability rule below as "not applicable"); programs written before that section existed fall back to the phase text. From it determine:

- Expected weekly volume range, normally **running minutes** (e.g. "240–300 min, deload 190–230 min"); quote `RunMin` first and km second. Apply the program's season rules and other-sports rule: a week where skiing or cycling replaces runs is scored against the adjusted range the program states, not the normal one
- Session priorities for this block (long run, strength, etc.) — use
  whatever order/list the current block's text and the program's Weekly
  Structure actually give, not a fixed assumption. A maintenance phase may
  rank strength or quality above the long run, unlike a race-build phase.
- Phase-specific requirements, read literally from the current phase's text
  — do not assume race-build requirements apply. Examples seen in past
  programs include "back-to-back weekends from Phase 2", "one night run per
  block", "overnight simulation", "power hike drill per block" — these only
  apply if the *current* program file's *current* phase actually states
  them. An interim/maintenance phase (no race decided) typically states
  none of these, and that is expected, not a gap.
- Strength frequency for this phase
- Explicit milestones listed anywhere in the program file (Current Position,
  Open items, phase goals) — for an interim program these may be things
  like "physio consult", "aerobic efficiency test", "review checkpoint
  date", not just race-prep milestones.
- **Minimum-week and illness rules:** a week the program's rules classify as a minimum week (travel, illness recovery, as logged in the events log) is scored against the minimum (one quality, one strength, one long run), and missed quality in an illness week is not a gap. Tests slipping more than a week are "dropped" per the program, not red.
- Any named disruption windows the program itself already flags (e.g. a
  "Known disruption — travel" section) — these carry their own adjusted
  expectations (usually lower volume, paused hill/quality work) and should
  suppress the normal red/yellow/green thresholds for their date range
  rather than flagging them as drift. Look for such windows anywhere in the
  program file, including Current Position → Open items (e.g. a travel
  period), not only under a "Known disruption" heading.
- **Planned deload weeks** (e.g. "Week 4 (28.9.–4.10.) deload, 200 min"): score that week
  against its own stated volume and the program's description of what a deload week contains, not the block's normal range, and exclude
  deload weeks when judging volume and long-run trends across blocks.
- **Long-run cap by duration:** if the program states the long run as a
  duration (e.g. "90–120 min, ≤ 2 h"), judge long-run progression by
  duration, not distance — distance depends on terrain.

If the program file lists milestones by date or by block (e.g. "LTHR field
test scheduled May 5", "physio consult", "review checkpoint ~28.9"), note
them and check the cache/events-log: has this happened? Is it scheduled?

---

## Step 5: Apply red / yellow / green per area

Use these defaults (skill can override if the program file specifies
tighter/looser tolerances).

**Applicability rule — check this before scoring any row:** only score an
area if the current phase's text in `training-program.md` actually states
a requirement or target for it. If the phase is silent on an area (e.g. an
interim/maintenance phase with no back-to-back-weekend or night-run
requirement, or no explicit hill D+ target), **omit that row from the
report entirely** rather than scoring it red/yellow/green against a
leftover number from a previous race's program. Say so explicitly in one
line under "Checks" (e.g. "Back-to-back weekends: not applicable — current
phase sets no requirement").

| Area | 🟢 Green | 🟡 Yellow | 🔴 Red |
|------|---------|----------|-------|
| Volume vs. phase range (judge by the unit the phase states; the preferred unit is running minutes, `RunMin`; trail terrain makes km a poor measure, so quote RunMin first, then km and D+, and say if the verdict differs by unit) | within range for 3+ of last 4 weeks | below range 2+ weeks | below range 3+ weeks OR above peak range consistently |
| Volume trend (4-wk vs. prev 4-wk) | +5% to +20% in a build phase; flat ±5% in maintenance/recovery/taper | +/- appropriate but inconsistent | stagnant for 8+ weeks in a build phase (not a flag in a maintenance phase) |
| Long-run progression — **build phase** (program states a progression target) | steadily increasing, hitting phase targets | plateaued 3+ weeks | plateaued 5+ weeks OR regressed |
| Long-run progression — **maintenance phase** (program states no progression target) | stable within the stated duration/volume range | drifting below range 2+ weeks | absent 3+ weeks running |
| Strength frequency | meeting phase prescription | 50–80% of prescription | <50% of prescription |
| Hill exposure — weekly D+ (only if phase states a D+ target) | ≥ stated target for 3+ of last 4 weeks | 60–99% of target | < 60% of target for 3+ weeks |
| Hill exposure — big sessions (only if phase names hill/power-hike sessions as a priority) | ≥ 1 session with ≥ 200 m gain per week | 1 per 2 weeks | 0 in last 4 weeks |
| Night sessions (only if an active race starts at night) | on pace for phase plan | ≤ 1 in last 8 weeks with race < 12 weeks | 0 in last 8 weeks with race < 8 weeks |
| Back-to-back weekends (only if phase states this requirement) | ≥ 2 per 4-week block | 1 per 4-week block | 0 per 4-week block |
| Quality/speed session frequency (only if phase names this as a priority, e.g. a speed-development focus) | meeting stated ×/week frequency | 50–80% of stated frequency | <50% of stated frequency |
| Hill exposure — monthly D+ (only if phase states a monthly D+ target) | calendar month on pace for the target (pro-rate the current month) | 60–99% of pro-rated target | < 60% of target for a full month |
| Polarization / grey zone (only if the program states a polarization rule). Judge primarily by **Z3 minutes** from the zone-minute table when `cov` is complete (a Z2 long run the program allows must not count as grey); use the grey-zone session count (avg-HR proxy) only when zone minutes are missing or `cov` is incomplete, and say which basis you used | ≤ 1 grey-zone session in last 4 weeks | 2–3 sessions | ≥ 4 sessions, or a cluster in consecutive weeks (defaults — the program file's own tolerance overrides) |
| Key milestones (whatever the program file lists — race-prep or otherwise, e.g. physio consult, field test, review checkpoint) | all on schedule | 1 slipping | 2+ slipping |
| Disruption context | no active illness, no major recent gap; any program-flagged disruption window (e.g. travel) is proceeding as expected | minor recent disruption, recovered | active illness or CLEARED < 7 days ago |

The worst flag across all *applicable* areas is the headline verdict. Rows
omitted as not-applicable do not count against the verdict.

---

## Step 6: Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PROGRAM HEALTH CHECK — [today's date]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Race:           [race name — race date] OR [No active race — interim/maintenance phase]
 Time to race:   [X weeks X days] OR [n/a]
 Current block:  [Block (or phase) name per program file]
 Program says:   [e.g. Block 3 Threshold, week 4/7] OR [e.g. Phase B — Maintenance & Development, week 3/12]
 Overall:        [🟢 On track / 🟡 Drifting / 🔴 Off track]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Last 8 weeks at a glance**
Week of   RunMin  Km    Hrs   Elev    Long    Str  Qual  Hill≥200m  Grey  Night  B2B
Apr 13    290     47    6:45  610     18.2    2    1     1          0     0      yes
[...]

(Drop the Qual/Grey/Night/B2B columns, the Tech column the script also prints,
or any other column tied to a not-applicable row, when the current block
doesn't call for them — don't display data with no reference point. Mark
deload weeks `D`.)

**Checks**

🟢/🟡/🔴 Volume vs. phase range: [one-line summary + the number]
🟢/🟡/🔴 Volume trend:           [4-wk vs. prev 4-wk, + direction]
🟢/🟡/🔴 Long-run progression:    [longest per week for last 6 weeks]
🟢/🟡/🔴 Strength frequency:      [sessions/week vs. prescription]
🟢/🟡/🔴 Quality frequency:       [quality sessions/week vs. the block's stated frequency; deload and minimum weeks per their rules]
🟢/🟡/🔴 Hill exposure (D+):       [D+ last 4 weeks vs. the target the phase actually states (weekly or monthly); trend]
🟢/🟡/🔴 Hill exposure (sessions): [count sessions ≥200 m gain last 4 weeks]
🟢/🟡/🔴 Polarization:            [Z3 minutes last 4 weeks (zone table), or grey-zone sessions (avg-HR proxy, band as printed on the script's Config line) when zone minutes are incomplete]
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

(Chat mode below replaces this report on Telegram.) Keep the whole report under ~1 KB of output — it is a dashboard, not a
coaching essay.

---

## Step 7: Optional — offer next step

End with a single question only if there are 🔴 items:

> "Haluatko että teen seuraavaksi viikko- tai kahden viikon ohjelman, joka
> korjaa nämä puutteet?"

If the response is yes, hand off to the `training-plan` skill. Otherwise
stop — this skill does not modify files or push to Garmin.

---

## Chat mode (Telegram, headless runs)

Used when the telegram-poll prompt sends you here. A chat reply is plain text, max ~250 words, and the
chat run has no free shell, so do **not** follow Steps 1-6 by hand and do not paste the Step 6 report.
Instead:

1. Run `python3 scripts/program_health.py [weeks]` (one of three fixed shell commands) - the same
   computation as Step 3 in every environment. Chat differs from an interactive run only in three ways:
   no cache sync (the daily sync keeps it current; if the script's last line says the cache is stale,
   keep that caveat and do not call Garmin just for this), a ~250-word reply instead of the Step 6
   report, and no hand-offs.
2. Read `training-program.md` (current phase block, Weekly Structure, Scored areas, flexibility/season/other-sports rules, Current Position, Open items,
   named disruption windows, planned deload weeks, checkpoint date) and `race-card.md` only if a race is decided.
3. Apply Steps 2, 4 and 5 to the script's numbers: the **applicability rule** (score only areas the
   current phase states; skip the rest in one line), deload weeks scored against their own volume, and
   disruption windows (travel, illness) that suppress flags. The headline verdict is the worst applicable
   flag.
4. Reply in the athlete's language, in this order: headline verdict with phase/week (and time to race
   or "no active race") · one line per applicable area with the number (🟢/🟡/🔴 + figure) · the
   one or two biggest gaps · one recommended focus for the next 1-2 weeks. Collapse green areas into one
   line. Quote numbers the script printed, never estimates. Apply the load and rest reasoning rule of
   CLAUDE.md (numbers first; say whether a reason is program structure or physiology).
5. End with the Step 7 question only if there are 🔴 items. Do not edit files, and do not build a plan in
   the same reply; hand-off goes through the training-plan flow.

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
- This skill is also compatible with **interim/maintenance programs that
  have no active race** (e.g. between goal races, phase named "Maintenance
  & Development" rather than "Build"/"Race-specific"). In that mode: skip
  time-to-race, skip race-specific rows (night sessions, back-to-back
  weekends, hill D+ target) unless the phase text explicitly restates them,
  and instead track whatever the phase names as its actual priorities —
  e.g. strength frequency and quality/speed session frequency for a
  development-focused maintenance phase. Do not carry over numeric targets
  (like a 1200 m D+/week hill target) from an old race-specific program
  into a new one without the new program restating them — those numbers
  were calibrated to a specific race's elevation profile and are meaningless
  without it.
- Naming is not fixed: current programs use "Block 1–N", older ones "Phase 1–4"
  or "Phase A/B", or any other scheme. Parse whatever `training-program.md` actually uses;
  don't assume a specific numbering convention.
