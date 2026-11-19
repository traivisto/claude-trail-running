# Technical notes (shared, athlete-independent)

Evolving technical knowledge for the coaching system: connector setup, API quirks, workout-structure
rules and workspace conventions. Nothing here is athlete-specific; athlete-specific setup and coaching
observations live in `athletes/<id>/memory.md`. Read this when troubleshooting a connector, when a skill
behaves unexpectedly, or when a Garmin response looks wrong.

Language: shared files are English. Skill `description` fields also carry the athlete's own-language
trigger phrases so skills fire in either language.

---

## Telegram remote interface — design

- Runs on the NAS as the always-on `coach-telegram` container: `scripts/telegram_poll.py --loop` long-polls
  the Telegram Bot API (no Cowork plugin, no hourly scheduled task; those are retired). One bot and one
  allowed chat id per athlete (`secrets/telegram.env`); only one poller may use a bot token.
- One cycle: read new messages of the allowed chat → if there are none, do nothing (Claude is not called,
  nothing is written) → otherwise one `claude -p` run with `scripts/prompts/telegram-poll.md` → send the
  replies → only then advance the offset. A failed run is retried; after 3 failures the athlete gets a
  fixed error text and the messages are dropped.
- State (default, per athlete): offset in `<athlete>/telegram-last-update.txt` (plain integer), same-day
  conversation memory in `<athlete>/telegram-conversation-log.md` (reset daily). In the **test phase** the
  env file points both to `telegram-test-offset.txt` / `telegram-test-conversation-log.md` and uses a
  separate test bot, so the production offset and log stay untouched until cutover
  (`deploy/nas/README.md`, "Phase C").
- The chat run is deliberately limited (`ALLOWED_TOOLS` in the script): read-only Garmin tools, a few
  reversible Garmin writes (`[Coach]` workouts behind a two-step approval; RPE/feel/name/description of an
  activity), Oura, file tools, and **no free shell** — only the fixed scripts `scripts/hr_zones.py` (HR
  zones of one run), `scripts/monthly_summary.py` (monthly summary from the cache) and
  `scripts/program_health.py` (weekly aggregates for the program health check). The code is
  read-only for chat runs, so improvement ideas go to `<athlete>/coach-backlog.md` (after the athlete
  agrees) and are worked on in SSH sessions.
- No health monitoring by design: Docker restarts a crash, a hang is noticed by hand (SSH; see
  `deploy/nas/README.md`).

## NAS runtime — operations

Full steps in `deploy/nas/README.md`. In short:

- **Three compose services** share one image: `coach` (headless one-off jobs, code read-only),
  `coach-edit` (SSH sessions, code writable), `coach-telegram` (always-on bot). Which athlete they serve is
  `COACH_ATHLETE_ID` in `.env` next to compose.yaml; nothing in the code names an athlete.
- **Scheduling** is DSM Task Scheduler, not cron in the container: `run-daily-sync.sh [athlete-id]` (cache
  sync, aerobic-efficiency splits, dashboard).
- **Updating**: `update-coach.sh` does a fast-forward `git pull` of `app/` from GitHub inside `coach-edit`,
  copies changed deploy files to the NAS folder, rebuilds/recreates what changed and smoke-tests. Git
  authenticates with an SSH **deploy key** in the container home (`~/.ssh/deploy_key`, selected by
  `core.sshCommand` in the repo's git config); the public key is registered as a repository deploy key on
  GitHub. It refuses to run over uncommitted changes in `app/`.
- **Pinned versions**: Claude Code and uv in the Dockerfile, garmin_mcp commit and oura-mcp in `mcp.json`.
  Upgrade procedure in the README.
- **Data**: athlete folders are git-ignored, so athlete data never moves through git. Let one machine write
  per athlete.

## Garmin MCP — setup

- Connector: Taxuspt/garmin_mcp via `uvx`. On the NAS it is started per run from `deploy/nas/mcp.json`
  (pinned commit). On a PC (Cowork) it is started manually in a terminal before a session:
  `uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp`
  (on Windows prefix with `cmd /c`).
- Auth tokens: `~/.garminconnect`, managed by the `garth` library. Renew with
  `uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth`.
- Parameter types: `activity_id` must be a **number**, not a string, otherwise a 422 error.
- Key tools: `get_activities_by_date`, `get_activity`, `get_body_battery`, `get_hrv_data`,
  `get_sleep_summary` (light, ~350 B — use this, NOT `get_sleep_data` which returns ~200 KB),
  `get_rhr_day`, `get_training_readiness`, `get_training_status`.

### Quirk — `recovery_time_hours` after ultra distances
After a 100 km / 18 h effort `get_morning_training_readiness` returned `recovery_time_hours: 1976`
(~82 days). This is an algorithm artifact: the model is calibrated for normal sessions and scales
acute load roughly linearly, so an ultra pushes the input far outside range. Cross-check with Body
Battery, HRV, sleep score and Oura readiness during ultra recovery windows, and never repeat the literal
figure to the athlete without this caveat.

### Quirk — field names drifted from `garmin-mcp/SKILL.md` (2026-08-06)
Corrected in `garmin-mcp/SKILL.md`; summary:
- `get_activities_by_date`: fields are `id`/`name`/`type`/`start_time`/`distance_meters`/`duration_seconds`/
  `avg_hr_bpm`/`max_hr_bpm` (not camelCase `activityId`/`startTimeLocal`/...). It **does** include
  `elevation_gain_meters`/`elevation_loss_meters`, so no per-activity `get_activity_splits` call is needed for elevation.
- `get_training_readiness` / `get_training_status`: single `date` param, not `start_date`/`end_date`
  (a range throws a validation error).
- `get_activity`: RPE/feel fields are `workout_rpe`/`workout_feel`. `workout_feel` uses 0/25/50/75/100
  (very_weak/weak/normal/strong/very_strong). The RPE ×10 quirk still holds (divide by 10).
- This may be a wrapper version bump rather than isolated drift: re-check other documented field names
  when something behaves unexpectedly. On the NAS the `garmin_mcp` commit is pinned in `deploy/nas/mcp.json`.

### Quirk — `get_activity_weather` units
`temperature_celsius` / `apparent_temperature_celsius` can be degrees **Fahrenheit** mislabeled as Celsius
(e.g. 61 for a July race in Lapland ≈ 16 °C). Sanity-check against season/location and convert
(°C = (°F − 32) × 5/9) if implausible.

## HR zones — API inconsistency
Coaching analysis uses LTHR-based zone boundaries from the `Athlete Config` block in `athlete-profile.md`.
Garmin Connect, the API (`get_activity_hr_in_timezones`) and the workout editor use %HRmax-based boundaries
and ignore LTHR settings. Never use Garmin's zone numbers or time-in-zone; compute
the distribution from per-second FIT HR (see `CLAUDE.md` "Activity analysis rule — HR zones"). Workout
creation rules (absolute bpm, `[Coach]` prefix) are also in `CLAUDE.md`.

## Oura MCP
- Package: `daveremy/oura-mcp` (`@daveremy/oura-mcp`), run via `npx`. Token in the MCP config as `OURA_TOKEN`.
- Skills call `mcp__oura__oura_daily_summary` directly (or `oura_readiness` / `oura_sleep`). No local
  file or script is needed; the legacy `oura-fetch.py` / `oura-today.json` path was retired (archived
  in `docs/archive/`).
- `oura_daily_summary` response shape:
  ```json
  { "date": "YYYY-MM-DD",
    "readiness": { "score": 67, "temperature_deviation": 0.07, "temperature_trend_deviation": 0.04,
                   "contributors": { "body_temperature": 99, "...": "..." } },
    "sleep": { "score": 71, "contributors": { "deep_sleep": 55, "rem_sleep": 39, "...": "..." } } }
  ```
- Tools: `oura_daily_summary`, `oura_sleep`, `oura_readiness`, `oura_activity`, `oura_stress`,
  `oura_trends`, `oura_workouts`, `oura_heart_rate`, `oura_spo2`, `oura_sessions`.
- Check whether Oura is moving away from personal access tokens to OAuth before relying on this for others.

## Interpreting interval sessions
For interval runs the relevant data is the work portion itself (e.g. 25 min in Z4), not the whole-run
average pace/HR, which includes warm-up and cool-down and is misleading. Analyse the work segments from
`get_activity_typed_splits` / lap data separately.

## Garmin workout structure rules
- **Z1 and Z1–Z2 runs:** a single workout step (duration + HR range); no separate warm-up/cool-down.
  Structure: 1 × [X min, ≤ Z1 ceiling or Z1–Z2 range].
- **Quality sessions** (tempo, hill repeats, intervals): warm-up and cool-down are separate steps.
- **Hill and terrain-based interval sessions:** warm-up, recoveries between climbs and cool-down must
  **not** be time-bound — end them with the lap button (`conditionType: PRESS_LAP`). Only the quality
  interval itself is time-bound (e.g. 4 min climb in Z4). Reason: on trails, time limits for descents and
  recoveries cannot be honoured. Example 4 × 4 min Z4: warm-up PRESS_LAP; × 4 [4 min Z4; recovery
  PRESS_LAP]; cool-down PRESS_LAP.
- **Garmin lap-button quirk:** the lap button in a Garmin workout **always** advances to the next step,
  whether the step's end condition is TIME or PRESS_LAP. Setting a GPS anchor via lap press mid-workout
  is not possible. Use PRESS_LAP-based repeat groups (RepeatGroupDTO) where the button is intentionally
  the lap-end action.

## Cache freshness
`CLAUDE.md` "Activity cache sync rule" is the single source of truth: frontier check with
`get_activities_by_date` at the start of every workflow (also covers same-day sessions). Skills must not
define their own freshness checks. Exception: `quick-lookup` is deliberately offline and adds a
staleness caveat to its answer.

## Skill update process
Skills are workspace-local — each in its own subfolder (`skill-name/SKILL.md`) of the code repo. Update by
editing `SKILL.md` directly; no packaging or global installation. **Note:** `list_skills` /
`mcp__skills__list_skills` shows only globally installed skills and does not see workspace-local ones.
To check which skills exist, use `Glob` for `**/SKILL.md`. Never state that a skill is missing before checking.

## Cowork mount staleness (important, Cowork only)
In Cowork, the Linux sandbox sees workspace files through a mount that is effectively a snapshot taken at
session start plus an overlay for in-session Edit changes. External changes (OneDrive sync, a cache
updated by the Garmin sync, a dashboard regenerated from the command line) **do not propagate to the bash
view** during the session, so `tail`, `wc -l`, `grep`, `cat` can show stale data.

Rule (when running in Cowork's sandbox): read workspace files with the Read tool, never via bash; use bash
only for computation and feed it content obtained through Read. The mount behaves like an overlayfs:
- files changed with Edit: content visible in bash, mtime frozen at snapshot time;
- files written by bash inside the mount: content and mtime fresh;
- files changed externally (OneDrive): content and mtime frozen at snapshot time.
OneDrive's "always keep on this device" setting does not fix this. **Does not apply** to headless runs on a
normal filesystem (e.g. NAS) or in Claude Code on the host OS.

## Backlog — planned skills
- `athlete-onboarding-check` — new-athlete setup check: `athlete-profile.md` has no placeholders,
  `race-card.md` is filled in, activity cache exists, Garmin MCP reachable; advise what is missing.
  (`workspace-audit` already exists for pre-release architecture checks.)
