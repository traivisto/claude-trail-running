---
name: training-program
description: "Designs or revises the athlete's multi-week training program (training-program.md): goals, phases/blocks, volume targets, tests, flexibility rules and checkpoint. Conversation-led; this skill only fixes the questions to settle and the structure the other skills depend on. Triggers: make a training program, new program, plan the next phase/season, back-plan from a race, revise/review the program, is the program still sensible. Finnish triggers: tee ohjelma, uusi ohjelma, suunnittele kausi, tee kisaohjelma, päivitä ohjelma, katselmoi ohjelma, onko ohjelma vielä järkevä. NOT for a week or two of sessions (use training-plan) and NOT for a status report (use program-health-check)."
---

# Training Program Skill (high level)

The program is decided in conversation with the athlete. This skill does not dictate content (goals, periodisation, session types); it makes sure the right questions are asked first and that the file has the structure `program-health-check`, `training-plan` and `scripts/program_health.py` rely on.

## Step 0: Resolve athlete directory

Resolve **ATHLETE_DIR** as in `CLAUDE.md` → "Athlete directory". Read (Read tool, not bash) `athlete-profile.md`, `race-card.md`, `events-log.md` and the existing `training-program.md` if any.

Whenever this skill reads the activity cache (Step 2 item 2, Step 4 item 3, Step 5 via `scripts/program_health.py`), first apply the **Activity cache sync rule** in `CLAUDE.md` (single source of truth for cache freshness).

## Step 1: Mode

- **New program** (no active program, or a race was just chosen): continue to Step 2.
- **Revision / review** of a running program: do the review in Step 5 first, then Steps 2–4 only for what changes.

## Step 2: Settle these before writing anything

Ask the athlete (one or two at a time, skip what the files already answer). Do not start writing until each has an answer or an explicit "unknown, assume X".

1. **Purpose and measure.** What is the primary goal, and how will we know it moved (an instrument, not a feeling)? A goal without a measure is a direction, say so.
2. **Capacity.** Realistic time per week, travel, usual illness, work peaks. Base targets on what the athlete has actually managed (`python3 scripts/program_health.py 12`), plus a stretch, not on what the plan "should" be.
3. **Race situation.** Race chosen, option, or none? If an option: date, distance, decision deadline. Back-plan the build length (16–20 weeks for ultras) and say when the latest start is.
4. **Previous program.** What was delivered vs planned (volume, quality, strength, tests)? What was never measured?
5. **Constraints.** Rest days, fixed weekly commitments, injuries on hold.
6. **Other sports.** Which other sports does the athlete do seasonally (skiing, cycling, swimming), and which sessions may they replace (easy run, strength, rest)?
7. **Season.** What does the calendar do to training? In Finland, Nov–Feb means early darkness and wet, icy or cold conditions: lower expectations for outdoor quality and long runs, studded shoes on ice, quality possibly indoors. Summer may mean heat, trips or different terrain. Settle where quality sessions and tests are done in that season.

## Step 3: Required structure of `training-program.md`

The file must contain these, each with a unit and scope:

- **Goals:** primary and secondary, each with its measure. State explicitly what is *not* a goal.
- **Volume:** **running minutes per week** (Trail + Road), normal week and deload week, as targets to aim for. Say what total training hours means (context only, unless decided otherwise). Do not use km as a target.
- **Weekly structure:** the usual shape of a week (sessions, rest days, strength frequency **and session length**; `training-plan` uses it, default 30 min if none is stated). Weekdays are a default pattern, not fixed: the athlete's calendar changes, and no weekday is a sacred rest or session day. State the sequencing constraints (hard session spacing, long run, strength spacing) instead of weekday rules, and say that sessions and rest are placed dynamically by load and upcoming sessions. A weekend is only preferred for long sessions because time is easier to find.
- **Blocks** (older programs say "phase"; the other skills read whichever word the file uses, but use "block" in new programs): dates, purpose, the Tuesday-style key session, deload week per block written exactly as `Week N (d.m.–d.m.) deload, X min` (the script parses this; always write the start month, also when the week crosses a month boundary). Say **what a deload week contains**: which sessions stay (e.g. quality kept at reduced volume or dropped, strength, long run length), because `training-plan` and `program-health-check` both need it.
- **Known disruptions:** named windows (travel, camps, exams) with their adjusted expectations, either as their own section or under Current Position → Open items.
- **Protected sessions and minimum week:** what stays when time or health is short.
- **Other sports:** which sessions they may replace and which they may not (default: Tuesday-style quality and the long run stay runs), and how the running-minute target changes while they replace runs. By default other sports are not running minutes and are not scored by `program-health-check`; their load shows in Garmin CTL/ACWR. Light activity (easy swim, walk) is not counted as load unless the data says so.
- **Season rules:** per season that matters, the adjusted expectations (e.g. winter: ice → quality on a treadmill/indoor track or dropped, no speed work on ice, long run may shorten) and the adjusted running-minute range.
- **Illness / travel rules:** easy only when ill, no catching up missed quality, how long a test may slip before it is dropped.
- **Test calendar:** date, test, *what it measures* (ceiling, threshold, aerobic economy), **where** (a test that must be repeatable in a season with unreliable weather is done indoors: indoor track or the same treadmill at fixed incline; name the venue/device and use the same one every time), and baseline plan. Indoor results are not comparable with outdoor results; keep one series per venue type. Say how distance and time are recorded where GPS does not work (indoors): count laps (lap button each lap or the watch's track/indoor mode), take distance = laps × lap length + the fraction of the last lap, and log that figure in `events-log.md` as the authoritative result (the watch distance in the cache may be off). A baseline missed in week N is done in N+1 or dropped explicitly. A maximal test costs a quality session; keep few, spaced 6–8 weeks. **State the test week's shape:** a maximal test replaces that week's quality session (default; say so if it does not), and the strength spacing before the test (general rule: strength is never placed immediately before a test; state a longer spacing, e.g. ≥ 72 h before a standard-route test, only for the tests that need it). `training-plan` applies exactly these rules and no broader ones.
- **Checkpoint:** a date where the program is reviewed and the next step (race build or continue) is decided.
- **Current Position** section (last updated, block, open items) and an "On a race decision" line.
- **Scored areas:** list the areas `program-health-check` may score in this phase (see its applicability rule); anything not listed is not scored.

Headings are free, except that the deload lines must match the format above and the section must be titled "Scored areas (program-health-check)". Keep the athlete's earlier rationale sections if they still hold; mark superseded numbers instead of silently deleting them.

## Step 4: Write, archive, check

1. If a program exists, copy it to `ATHLETE_DIR/arkisto/training-program-<name>-YYYY-MM-DD.md` first.
2. Show the athlete a short summary of changes before writing; write after approval.
3. Run `python3 scripts/program_health.py`; confirm the planned deload weeks are marked `D` and nothing errors.
4. Check: every goal has a measure, every number has a unit, no target is stated only in km, and any older km-based section or Current Position figure that still stands is marked superseded or restated in minutes.
5. Log the decision as a MILESTONE in `events-log.md` and lasting decisions in `memory.md`.

## Step 5: Review mode

Compare plan vs delivery with numbers: run `python3 scripts/program_health.py 12`, read the events log, list quality sessions, strength dates, tests done vs planned. Ask: are the goals still sensible given capacity? Are the tests answering a question that will change a decision? Is the volume target a capacity or a wish? Present findings with the numbers first (CLAUDE.md load rule), then options; the athlete decides. Never revise silently.

## Notes

- A plan for a week or two is `training-plan`; a status report is `program-health-check`. This skill produces or revises the program they read.
- No Garmin writes in this skill.
