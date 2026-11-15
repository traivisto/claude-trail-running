# Tenant-ready refactor — spec

Status: IMPLEMENTED on branch `tenant-ready` (2026-11-15), uncommitted at time of writing. See "As built" at the end for deviations from this plan.
Goal: separate **code** (shared, reusable) from **athlete data** (private, per athlete) so that
(1) the workspace can later run headless on the NAS and (2) adding a second athlete means adding a
directory, not forking the repo. Behaviour for the current athlete must stay identical.

Non-goals (deliberately later): Garmin Personal API sync, Garmin interface abstraction, NAS container,
multi-user connector credentials, localization.

---

## 1. Target layout

```
claude-trail-running/              <- public/shared code repo
  CLAUDE.md                        <- generic coaching-system instructions (no athlete data)
  <skill>/SKILL.md  (x10)
  scripts/
    resolve_athlete.py              <- NEW: prints the athlete data root (importable)
    new-athlete.py                 <- NEW: scaffolds athletes/<id>/ from setup-template/
    update-dashboard.py            <- moved from root, takes the data root
    update-dashboard.bat           <- thin wrapper
    oura-fetch.py                  <- legacy; token path made per-athlete (or retired)
  setup-template/                  <- blank starter files (already exists)
  docs/
  athletes/                        <- git-ignored entirely (except .gitkeep)
    <id>/                          <- one directory per athlete; later its own PRIVATE git repo
      athlete-profile.md  race-card.md  race-day-guide.md
      training-program.md current-plan.md
      events-log.md  memory.md
      activity-cache.csv  aerobic-efficiency-splits.csv
      training-dashboard.html
      telegram-last-update.txt  telegram-conversation-log.md  oura-today.json
      arkisto/                     <- personal history (plans, exports, screenshots)
      reference/                   <- race cards, PDFs and other reference material
```

Why `athletes/<id>/` inside the repo rather than an external folder: Claude Code/Cowork opens one
folder and loads `CLAUDE.md` + skills from it; keeping data inside keeps that working with zero
config, while `.gitignore` keeps it out of the shared repo.

## 2. Data-root resolution (the one new mechanism)

All skills and scripts get the athlete directory the same way. Resolution order:

1. `$COACH_ATHLETE_DIR` if set (absolute path) — used by cron/NAS and by multi-athlete setups.
2. Else, if exactly one `athletes/*/athlete-profile.md` exists, use that directory — so the current
   single-athlete PC setup needs **no configuration**.
3. Else fail with a clear message listing the candidates (never guess between athletes).

Implemented once in `scripts/resolve_athlete.py` (pure stdlib, works on Windows and Linux) and
imported by the Python scripts. Skills call it instead of the current Step 0.

This replaces `find /sessions -maxdepth 4 -name 'athlete-profile.md'` in 9 skills
(activity-cache-updater, aerobic-efficiency-updater, coach-monthly-summary, daily-readiness,
garmin-activity-tagger, program-health-check, quick-lookup, training-plan, workspace-audit).
That command only works inside the Cowork Linux sandbox — it does not work on Windows or on the NAS,
so it must go regardless of the multi-user goal.

## 3. File-by-file changes

### 3.1 Moves (personal data → `athletes/<id>/`)
Plain filesystem moves (these files are git-ignored, so there is no git history to preserve).
Back up first (section 5, step 1).

| From (root) | To |
|---|---|
| athlete-profile.md, race-card.md, race-day-guide.md | athletes/<id>/ |
| training-program.md, current-plan.md | athletes/<id>/ |
| events-log.md | athletes/<id>/ |
| activity-cache.csv, aerobic-efficiency-splits.csv | athletes/<id>/ |
| training-dashboard.html | athletes/<id>/ |
| telegram-last-update.txt, telegram-conversation-log.md, oura-today.json | athletes/<id>/ |
| oura.env | outside the repo: `~/mcps/oura.env` (already the documented preferred location) |
| race reference PDFs | athletes/<id>/reference/ |
| arkisto/ | **split**: athlete material (training-plan-*.md, training-program-*.md, cache backups, screenshots, xlsx) → athletes/<id>/arkisto/; dev material (`*.plugin`, `*-workspace` eval folders, COACH-SYSTEM-SUMMARY.md) → `docs/archive/` |

### 3.2 `memory.md` — needs a manual split (cannot be mechanical)
It mixes two things:
- **Shared technical knowledge** (Garmin MCP quirks, field-name drift, API units, mount-staleness,
  connector setup) → `docs/technical-notes.md` (code repo; scrub personal paths/bot names first).
- **Athlete-specific coaching observations and setup** (Telegram bot details, personal Garmin/Oura
  config, athlete insights) → `athletes/<id>/memory.md`.
`CLAUDE.md` "Technical memory" section is updated to point at both.

### 3.3 Scripts
- `update-dashboard.py`: replace `BASE = Path(__file__).parent` (lines 19–22) with the resolved
  athlete dir (CLI arg `--athlete-dir`, else `resolve-athlete.py`). CACHE, SPLITS_CACHE and DASH
  become `<athlete>/...`. No other logic changes (it is stdlib-only and path-agnostic otherwise).
- `update-dashboard.bat`: unchanged logic, calls `scripts\update-dashboard.py`, forwards args.
- `oura-fetch.py`: reads `~/mcps/oura.env` or a workspace-root `oura.env`; make it read
  `$OURA_ENV_FILE` / athlete-dir `oura.env`. It is a legacy fallback — confirm whether to retire it.
- `git-push.bat`: unchanged (commits the code repo only; athlete data is ignored). Add a second
  script later for the private data repo (NAS phase).
- New: `resolve-athlete.py`, `new-athlete.py` (copies `setup-template/` into `athletes/<id>/`, including
  a blank dashboard).

### 3.4 `CLAUDE.md`
- Replace "Skills discover this workspace automatically by searching for athlete-profile.md" with the
  resolution order from section 2.
- Every bare filename reference (13 occurrences: athlete-profile.md, race-card.md, activity-cache.csv,
  events-log.md, memory.md, telegram-last-update.txt, current-plan.md, arkisto/, ...) becomes
  "`<athlete>/<file>`", defined once at the top as `ATHLETE_DIR`.
- "Dashboard update rule": run `scripts/update-dashboard.py` with the athlete dir instead of "from this folder".
- "File reading rule — Cowork mount staleness": make conditional ("when running in Cowork's Linux
  sandbox"); it does not apply to headless/NAS runs.
- Keep the generic rules (HR zones, load/rest reasoning, workout creation, plan workflow) as they are.

### 3.5 Skills — path references (mechanical, one skill at a time)
Approximate reference counts to bare filenames: training-plan 19, program-health-check 17,
daily-readiness 14, quick-lookup 12, coach-monthly-summary 7, garmin-activity-tagger 7,
aerobic-efficiency-updater 6, activity-cache-updater 5, garmin-mcp 3, workspace-audit 26.

Per skill: (a) replace Step 0 discovery with the resolver; (b) prefix data-file references with
`$ATHLETE_DIR/`; (c) review prose that says "workspace root" / "this folder".

Specific items found:
- `activity-cache-updater/SKILL.md:107` hardcodes `/sessions/.../activity-cache.csv` and a Cowork-only
  workaround (append via bash because Edit is invisible to the sandbox). Make it two-mode: Cowork
  sandbox vs plain filesystem.
- Eval files (`*/evals/*.json`) may reference file names; check and update.
- `workspace-audit` currently *requires* `athlete-profile.md` etc. in the workspace root and checks
  `.gitignore` for them; invert: personal files must be **absent** from the root and `athletes/*` must be
  ignored. Its Step 0 discovery changes too.

### 3.6 `.gitignore`
Replace the personal-file list with:
```
athletes/*
!athletes/.gitkeep
```
Keep credentials patterns (`*.env`, `telegram-trail-coach.json`) and the other ignores. Keep the old
per-file entries for one release so a half-migrated checkout cannot leak.

### 3.7 README / setup docs
New-install steps change from "copy setup-template to workspace root" to
`python scripts/new-athlete.py <id>`. Update the 26 references.

### 3.8 Outside the repo
- **Cowork scheduled task `telegram-trail-coach-poll`** (hourly 08:02–22:02): its prompt and the
  offset file path (`.../telegram-last-update.txt`) must point at the new location. Not stored in the
  repo, so it is easy to forget — do it in the same session as the moves.
- MCP configs (Garmin token dir `~/.garminconnect`, Oura token): unchanged in this phase.
  Becoming per-athlete is a NAS/multi-user-phase item.

## 4. Important finding that affects the NAS plan

Personal data is git-ignored, so the PC and the NAS **cannot** sync athlete data through the shared
code repo. Decision for the NAS phase: make each `athletes/<id>/` its own **private** git repo
(preferred; history + conflict handling) or sync it with Syncthing/rsync. Layout in this spec works
for either — `athletes/<id>/` is self-contained.

## 5. Migration order (each step independently testable; work on a branch `tenant-ready`)

1. **Backup.** Zip the whole folder to a location outside OneDrive; note the current git HEAD.
2. Add `scripts/resolve-athlete.py` and `new-athlete.py`; test resolver with no data moved (expect
   failure message, then add a temp `athletes/test/`).
3. Create `athletes/<id>/`; move the files in 3.1 (not `memory.md` yet). Update `.gitignore`.
4. Update `update-dashboard.py` + `.bat`; run it; diff the regenerated dashboard against the backup
   (should be byte-identical apart from data timestamps).
5. Split `memory.md` (3.2); update `CLAUDE.md` (3.4).
6. Update skills one at a time (3.5). After each, run a smoke test (table below).
7. Update `workspace-audit`, README, setup-template, `.gitignore` cleanup; run workspace-audit.
8. Update the Cowork scheduled task; wait for one poll cycle and confirm the offset file advances.
9. Commit on the branch; merge when the verification list passes.

## 6. Verification checklist

| Check | Expected |
|---|---|
| `resolve-athlete.py` with no env | prints `athletes/<id>` |
| `COACH_ATHLETE_DIR` set to another path | uses it |
| Two athlete dirs, no env | fails with a listing, no guessing |
| `update-dashboard.py` | regenerates dashboard identical to pre-migration |
| activity-cache-updater (no new activities) | confirms cache current, writes nothing |
| daily-readiness | reads profile/cache/events from the new location |
| quick-lookup ("km last week") | same answer as before the move |
| training-plan draft | writes `current-plan.md` in the athlete dir; archives to athlete `arkisto/` |
| Telegram poll | offset file in athlete dir advances; empty run stays cheap |
| `git status` | no athlete data tracked; `athletes/` ignored |
| grep for bare personal filenames / `/sessions/` / `C:\Users` in code | none left |

## 7. Rollback
Restore from the backup zip and `git checkout main`. Because the refactor is on a branch and the
data moves are the only non-git-tracked changes, rollback is the zip restore.

## 8. Open questions (answered)
1. Athlete id to use for the directory?
2. Split `memory.md` now (cleaner) or move it whole and split later (faster)?
3. Retire `oura-fetch.py`/`oura-today.json` (MCP is primary), or keep as fallback?
4. Do the dev-only arkisto items (`.plugin`, eval workspaces) go to `docs/archive/` or stay ignored/deleted?
5. Keep Finnish text in `memory.md`/events-log as is (yes assumed; localization is a later phase).

---

## 9. As built — deviations and findings

Decisions taken: athlete id chosen by the owner; `memory.md` split now; `oura-fetch.py`/`oura-today.json` retired
(archived); dev-only archive items moved to `docs/archive/` (git-ignored).

Deviations from the plan above:
- `scripts/resolve-athlete.py` is named `resolve_athlete.py` (a hyphenated file cannot be imported).
- **Skills resolve ATHLETE_DIR with Glob, not by running the script** (rules live once in `CLAUDE.md`
  → "Athlete directory"). Glob goes through the host filesystem, so it avoids the Cowork mount-staleness
  problem and works on Windows/NAS. Python scripts use `resolve_athlete.py`, which applies the same rules.
- `requirements.txt` removed (it only listed `requests` for the retired `oura-fetch.py`).
- `docs/archive/` is git-ignored (old eval transcripts may contain personal data).
- `scripts/update-dashboard.py` still crashes on Windows consoles with a cp1252 code page when it prints
  `→` (pre-existing, unrelated); run with `PYTHONIOENCODING=utf-8` or fix separately.

Findings:
- `aerobic-efficiency-splits.csv` was **tracked** by git (it was never in `.gitignore`), so personal
  workout data already exists in earlier commits. It is now untracked and ignored, but git history still
  holds it; rewrite history before publishing the repo.
- Two different Oura tokens existed (workspace `oura.env` vs `~/mcps/oura.env`); the workspace copy was
  moved to `~/mcps/oura.env.from-workspace`, not deleted. Decide which is current.
- A new athlete's cache files are not scaffolded; `activity-cache-updater` must create them on first sync
  (not yet tested end to end).
