# Trail Running Coaching System

This folder contains a trail running coaching system. The code (skills, scripts, templates, this file) is shared and contains no personal data. Each athlete's personal data (profile, race goals, caches, plans, history) lives in its own directory under `athletes/<id>/`, which is git-ignored. Skills handle the coaching logic.

## Where this runs
Everything runs on the **NAS** (Synology, Docker). Interactive Claude Code sessions (SSH, `coach-chat.sh`) run in the `coach-edit` container, where the code is writable: **development, commits and pushes happen there** (the PC is no longer a development machine). Headless runs (daily sync, the Telegram chat bot) run in their own containers with read-only code. Athlete data lives in `athletes/<id>/` on the NAS volume and is never copied anywhere by hand. Host-side commands (`sudo ./update-coach.sh`, `docker compose ...` in `/volume1/docker/coach`) are not visible from inside the container; the user runs them on the NAS host. Details: `deploy/nas/README.md`.

## Athlete directory (ATHLETE_DIR)

All personal files are read from and written to **`ATHLETE_DIR`** = `athletes/<id>/` (relative to this workspace root). Every bare filename in this file and in the skills (`athlete-profile.md`, `race-card.md`, `activity-cache.csv`, `events-log.md`, `memory.md`, `current-plan.md`, `training-program.md`, `race-day-guide.md`, `training-dashboard.html`, `aerobic-efficiency-splits.csv`, `hr-histograms.csv`, `telegram-last-update.txt`, `arkisto/`) means `ATHLETE_DIR/<that file>`.

**Resolve ATHLETE_DIR at the start of every workflow, in this order:**
1. `$COACH_ATHLETE_DIR`, if set (used for headless/NAS runs and multi-athlete setups);
2. otherwise Glob `athletes/*/athlete-profile.md` — if exactly one match, use its directory;
3. if there are several matches and none was named by the user, ask which athlete. Never guess between athletes and never mix files from two athlete directories.

Python scripts use `scripts/resolve_athlete.py`, which applies the same rules. To set up a new athlete run `python scripts/new-athlete.py <id>`, then fill in `athlete-profile.md` and `race-card.md` in the new directory.

## Workspace skills

Each skill lives in its own subfolder as `skill-name/SKILL.md`. Before starting any task that matches a skill's trigger, read the corresponding SKILL.md file and follow its instructions exactly. The available skills are:

| File | Use when |
|------|----------|
| `daily-readiness/SKILL.md` | User asks about today's condition, readiness to train, how recovered they are ("how am I today?", "should I rest?", "what should I do today?") |
| `activity-cache-updater/SKILL.md` | Cache needs syncing with latest Garmin data (also triggered automatically by other skills) |
| `aerobic-efficiency-updater/SKILL.md` | Splits cache (`aerobic-efficiency-splits.csv`) for the dashboard's aerobic efficiency chart needs syncing — runs automatically after every activity-cache sync |
| `coach-monthly-summary/SKILL.md` | User asks for a monthly training summary or multi-month comparison |
| `garmin-activity-tagger/SKILL.md` | Classifying or tagging a specific activity by type/purpose |
| `program-health-check/SKILL.md` | User asks if training is on track, program audit, phase progress ("is my program on track?", "program status") |
| `training-program/SKILL.md` | Creating, revising or reviewing the multi-week training program (`training-program.md`): goals, blocks, volume targets, tests, checkpoint ("make a program", "is the program still sensible?"). Not for week plans (`training-plan`) or status reports (`program-health-check`). |
| `quick-lookup/SKILL.md` | Factual data lookups from local files — km last week, race start time, cutoffs, drop bag contents, phase dates |
| `training-plan/SKILL.md` | Creating or updating a training plan, pushing workouts to Garmin |
| `garmin-mcp/SKILL.md` | **Reference only** — read before making Garmin MCP calls. Maps use cases to tools, documents response shapes, lists known quirks. Not a workflow skill. |
| `workspace-audit/SKILL.md` | Pre-release architecture audit before sharing as a plugin — checks file system, templates, personal data isolation, skill integrity, path portability, and documentation. |

Always prefer a skill over ad-hoc reasoning when one matches the request.

## Garmin MCP rule
Before making any Garmin MCP tool calls, read `garmin-mcp/SKILL.md` for tool selection, parameter formats, response field names, and known quirks. This prevents common mistakes (wrong activity_id type, using get_sleep_data instead of get_sleep_summary, wrong HR zone approach, etc.).

## Athlete context rule
Before answering any coaching question — including gear, pacing, race strategy, training, or health — always resolve ATHLETE_DIR and read `athlete-profile.md` and `race-card.md` from it first. Do not rely on general knowledge when athlete-specific data is available. This applies even to seemingly simple questions where the answer might differ based on the athlete's profile, race distance, or history.

## Activity analysis rule — HR zones
Whenever a single activity's heart rate is analysed (e.g. "how did today's run look?", interval review, zone distribution), read `garmin-mcp/SKILL.md` and the `Athlete Config` block in `athlete-profile.md` first.

1. **Never use `get_activity_hr_in_timezones`** or Garmin's own zone numbers/time-in-zone figures — they use %HRmax-based boundaries and do not match the athlete's LTHR-based zones.
2. **Compute the distribution yourself** with the boundaries from `Athlete Config`, from per-second HR in `get_activity_fit_data` with `include_records=true`. The result is large (~1 MB for a 1 h run) and is saved to a file: process it in code (Python), do not read it into context. Assign values that fall between two zones to the lower zone for the gap above a zone's max (e.g. with Z3 140–150 and Z4 152–160: 151 counts as Z3; 161 counts as Z4) and say so.
3. For interval sessions, report time in target zone per interval (use the lap `start_time` values from the same data), not only the whole-run totals.
4. If the fit data is unavailable, fall back to lap-level avg/max HR from `get_activity_splits` and state that the zone split is approximate.

## Technical memory
Two files, by scope:
- `docs/technical-notes.md` (shared, athlete-independent) — connector setup, known API quirks, workout-structure rules, Cowork mount staleness. Read it when troubleshooting connector issues or when a skill behaves unexpectedly.
- `ATHLETE_DIR/memory.md` (this athlete) — athlete-specific setup (bot/chat IDs, credentials locations), evolving coaching observations and permanent coaching decisions. Read it when answering questions about training history context not covered in athlete-profile.md.

## Events log scope
`events-log.md` is the canonical store for any **date-bound event tied to this athlete** that isn't a training session — sickness, travel, alcohol, stress, lab/field tests, milestones, gear changes. When a relevant event surfaces in conversation (e.g. "tein LTHR-testin tänään", "lensin Berliiniin", "uudet kengät"), append it to events-log.md proactively, in the documented format. Permanent technical knowledge (API quirks, connector setup) stays in `docs/technical-notes.md`, athlete-specific lasting observations in `ATHLETE_DIR/memory.md`; one-off events go to `events-log.md`.

## File reading rule — Cowork mount staleness
**Legacy — does not apply on the NAS** (see "Where this runs"): all sessions there use a normal filesystem, where bash (`cat`, `grep`) and the Read tool see the same, fresh files. The rule below applies only if the workspace is ever opened in Cowork's Linux sandbox. Details in `docs/technical-notes.md`.

Cowork's Linux sandbox sees workspace files through a mount that is essentially a session-start snapshot with an overlay for in-session edits. **External changes that happen during a session do not propagate to the bash view.** This affects `activity-cache.csv` whenever it has been updated by Garmin sync or `update-dashboard.py` outside Cowork, and any other file written by something other than Claude's Edit/Write tools.

**Rule:** Read workspace files using the Read tool, never via `cat`, `head`, `tail`, `grep`, or other bash commands. Use bash only for computation (Python aggregations, classification logic, etc.) — and even then, feed file content via Read-tool output, not by reading from the mount.

This applies particularly strictly to `activity-cache.csv`, which can be updated externally between sessions or by the activity-cache-updater skill mid-session.

## Activity cache sync rule
The cache must be current before any coaching analysis. **Always sync at the start of every workflow** that reads the cache — the check is a single lightweight API call and costs nothing if there is nothing new.

**Default behaviour (mandatory):** At the start of any workflow that reads the cache (readiness, health check, monthly summary, training plan, etc.), call `get_activities_by_date` from the day after the last cached date through today. If any new activities are returned, run the activity-cache-updater skill before proceeding. If nothing is returned, continue immediately — the cache is confirmed current. Do not skip this step even if the cache appears recent; a planned workout may have been completed earlier the same day.

**Exception — skip the Garmin call only if** the cache was already synced earlier in this same session (i.e. the activity-cache-updater skill has already run and confirmed the cache is up to date).

**Exception — quick-lookup:** the `quick-lookup` skill is deliberately offline (no API calls, speed is its purpose). It does **not** sync. Instead, if the cache frontier is older than yesterday, its answer must include a one-line staleness caveat (e.g. "cache covers through [date] — recent days may be missing"). If the user then wants exact current numbers, run the sync.

**This section is the single source of truth for cache freshness.** Skills must not define their own divergent freshness checks — they reference this rule.

**Additional trigger — new activity spotted mid-workflow:** If at any point Claude fetches a Garmin activity and finds it is not yet in the cache, run the activity-cache-updater skill immediately before continuing.

In all cases: do not wait for the user to ask, and do not skip the sync in favour of answering faster.

## Dashboard update rule
After every activity cache sync (activity-cache-updater skill), first run the `aerobic-efficiency-updater` skill (fetches splits for new qualifying road runs; it is a no-op if there are none), then always run `python scripts/update-dashboard.py` from the workspace root (`python3` on Linux; add `--athlete-dir <ATHLETE_DIR>` when ATHLETE_DIR is not the only athlete). This regenerates `ATHLETE_DIR/training-dashboard.html` from the updated cache. Tell the user to refresh the dashboard in their browser.

## Garmin workout creation rules

When creating workouts via `upload_workout`:

1. **Always use absolute HR values**, never Garmin's zone numbers. Garmin's built-in zones are %HRmax-based and do not match LTHR-based zones. Use `targetValueOne` / `targetValueTwo` (bpm) with `workoutTargetTypeId: 4`. Read the athlete's HR zone boundaries from the `Athlete Config` block in `athlete-profile.md`.

2. **Always prefix the workout name with `[Coach]`** so coach-created workouts can be identified and distinguished from manually created ones. Example: `[Coach] Easy run 50 min Z1`.

3. **Always schedule workouts to the Garmin calendar** using `schedule_workout` after uploading. This pushes the session to the watch so the athlete sees it on the device and gets guided alerts during the run. Note: scheduling happens as part of the training-plan approval step — upload and schedule only after the user has explicitly approved the draft, not before.

## Training plan workflow

Use the `training-plan` skill for all training plan creation. The skill handles the full workflow:
- Requires explicit duration before starting (never guess)
- Checks for conflicts with existing approved plans before proceeding
- Saves draft to `current-plan.md` (always overwrites the previous active plan) and presents for approval
- Pushes to Garmin only after explicit approval (running + strength to Garmin, swimming/walking/rest noted in file only)
- Archives the previous plan to `ATHLETE_DIR/arkisto/` with a date-stamped filename when replaced

## Optional: Oura Ring
Oura data is fetched live via the `mcp__oura__` MCP tools (daveremy/oura-mcp, token stored in the MCP config). Skills call `mcp__oura__oura_daily_summary` directly — no local file or script needed (the legacy `oura-fetch.py` was retired). If the MCP tools are unavailable, all skills continue with Garmin data only.

## Optional: Telegram remote interface
A Telegram bot is the remote interface: the athlete sends coaching questions and status updates from the
phone and gets short replies. It runs on the NAS as the always-on `coach-telegram` container
(`scripts/telegram_poll.py --loop`, prompt `scripts/prompts/telegram-poll.md`), configured in
`deploy/nas/` (bot token and chat id in `secrets/telegram.env` there, never in the repo). The old Cowork
plugin / hourly scheduled task is retired. If no bot is configured, skip all Telegram steps silently. State
is in `ATHLETE_DIR/telegram-last-update.txt` (offset) and `ATHLETE_DIR/telegram-conversation-log.md`
(same-day memory); a test bot uses `telegram-test-*` files. The chat run has no free shell, only the fixed
scripts `scripts/hr_zones.py`, `scripts/monthly_summary.py` and `scripts/program_health.py`, and cannot edit code; improvement ideas
go to the development backlog (below). Design and
operations: `docs/technical-notes.md` (Telegram, NAS runtime) and `deploy/nas/README.md`; athlete-specific
setup in `ATHLETE_DIR/memory.md`.

## Load and rest reasoning rule
Rest and load recommendations must be grounded in measured data and must not present program structure as a physiological need.

1. **Numbers before verdicts.** When recommending rest, a lighter session or a harder one, base it on measured figures and quote them: age and size of the last hard session, last 7 days' load, ACWR, Garmin/Oura readiness, HRV vs weekly average. Do not use vague words such as "moderate load" or "heavy week" without a number. Light activity (easy swim, walk, short Z1) is not counted as load unless the data says so.
2. **Separate the two kinds of reason.** State explicitly whether a decision is (a) program structure (e.g. "Monday is a rest day in the program", a convention that can be changed) or (b) a physiological need (readiness, HRV, soreness, illness). Never present (a) as if it were (b).
3. **Small signals stay small.** A weak signal (HRV dip within BALANCED, one sensitive-HR run) is used for the go/no-go on the next hard session, not as grounds for blocking easy activity the same day.

## Development backlog (coach-backlog.md)
`ATHLETE_DIR/coach-backlog.md` is the **single place for every future improvement** of this coaching
system: missing tools/scripts/permissions that came up in Telegram chat, ideas and fixes from SSH sessions,
documentation and clean-up tasks, multi-user groundwork, reminders (e.g. token renewals). It lives in the
athlete directory because that is the only place the chat bot can write (the code is read-only for chat
runs) and it is backed up with the rest of the athlete data; it is git-ignored.

- **Who adds entries:** the Telegram bot (only after the athlete agreed) and any interactive session
  (when the athlete says "add this to the backlog" or when work is left undone). Format per entry:
  `## YYYY-MM-DD — <title> [open]` with `- Source: telegram|ssh`, `- Asked/Why`, `- Missing/Scope`,
  `- Proposal`, `- Example` lines as relevant.
- **Development happens in interactive SSH sessions.** At the start of an interactive session (not a
  headless `-p` run), if the backlog has `[open]` entries, list them in one line each and ask which to
  work on. Headless runs never work on backlog items.
- When an entry is done, change its tag to `[done YYYY-MM-DD]` and note the commit. Never delete entries.
