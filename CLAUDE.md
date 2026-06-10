# Trail Running Coaching System

This folder contains a trail running coaching system. Personal data (athlete profile, race goals, training history) lives in the workspace files. Skills handle the coaching logic.

**Skills discover this workspace automatically** by searching for `athlete-profile.md` — no hardcoded paths needed. To set up for a new athlete, update `athlete-profile.md` with their data and create a `race-card.md` for their goal race.

## Workspace skills

Each skill lives in its own subfolder as `skill-name/SKILL.md`. Before starting any task that matches a skill's trigger, read the corresponding SKILL.md file and follow its instructions exactly. The available skills are:

| File | Use when |
|------|----------|
| `daily-readiness/SKILL.md` | User asks about today's condition, readiness to train, how recovered they are ("how am I today?", "should I rest?", "what should I do today?") |
| `activity-cache-updater/SKILL.md` | Cache needs syncing with latest Garmin data (also triggered automatically by other skills) |
| `coach-monthly-summary/SKILL.md` | User asks for a monthly training summary or multi-month comparison |
| `garmin-activity-tagger/SKILL.md` | Classifying or tagging a specific activity by type/purpose |
| `program-health-check/SKILL.md` | User asks if training is on track, program audit, phase progress ("is my program on track?", "program status") |
| `quick-lookup/SKILL.md` | Factual data lookups from local files — km last week, race start time, cutoffs, drop bag contents, phase dates |
| `training-plan/SKILL.md` | Creating or updating a training plan, pushing workouts to Garmin |
| `garmin-mcp/SKILL.md` | **Reference only** — read before making Garmin MCP calls. Maps use cases to tools, documents response shapes, lists known quirks. Not a workflow skill. |
| `workspace-audit/SKILL.md` | Pre-release architecture audit before sharing as a plugin — checks file system, templates, personal data isolation, skill integrity, path portability, and documentation. |

Always prefer a skill over ad-hoc reasoning when one matches the request.

## Garmin MCP rule
Before making any Garmin MCP tool calls, read `garmin-mcp/SKILL.md` for tool selection, parameter formats, response field names, and known quirks. This prevents common mistakes (wrong activity_id type, using get_sleep_data instead of get_sleep_summary, wrong HR zone approach, etc.).

## Athlete context rule
Before answering any coaching question — including gear, pacing, race strategy, training, or health — always read `athlete-profile.md` and `race-card.md` first. Do not rely on general knowledge when athlete-specific data is available. This applies even to seemingly simple questions where the answer might differ based on the athlete's profile, race distance, or history.

## Technical memory
`memory.md` contains technical notes and evolving coaching observations that don't fit the structured files above — including known API quirks, connector setup details, and coaching insights accumulated over time. Read it when troubleshooting connector issues, when a skill behaves unexpectedly, or when answering questions about training history context not covered in athlete-profile.md.

## Events log scope
`events-log.md` is the canonical store for any **date-bound event tied to this athlete** that isn't a training session — sickness, travel, alcohol, stress, lab/field tests, milestones, gear changes. When a relevant event surfaces in conversation (e.g. "tein LTHR-testin tänään", "lensin Berliiniin", "uudet kengät"), append it to events-log.md proactively, in the documented format. Permanent technical knowledge (API quirks, connector setup) stays in `memory.md`; one-off events go to `events-log.md`.

## File reading rule — Cowork mount staleness
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
After every activity cache sync (activity-cache-updater skill), always run `update-dashboard.py` from this folder (use the absolute path to this workspace folder). This regenerates training-dashboard.html from the updated cache. Tell the user to refresh the dashboard in their browser.

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
- Archives the previous plan to `arkisto/` with a date-stamped filename when replaced

## Optional: Oura Ring
Oura data is fetched live via the `mcp__oura__` MCP tools (daveremy/oura-mcp, token stored in Cowork MCP config). Skills call `mcp__oura__oura_daily_summary` directly — no local file or script needed. If the MCP tools are unavailable, all skills continue with Garmin data only.

## Optional: Telegram remote interface
A Telegram bot can be used as a remote interface — send coaching questions and log status updates from your phone without opening Cowork. Requires the `telegram-nemo` Cowork plugin to be installed and configured with a bot token. If the plugin is not installed or the `mcp__telegram-nemo__` tools are unavailable, skip all Telegram steps silently — no error, no prompt to the user. State is tracked in `telegram-last-update.txt` in the workspace. A scheduled task polls for new messages hourly. See `memory.md` for bot setup details specific to this athlete's installation.