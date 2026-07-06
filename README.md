# Trail Running Coach

An AI coaching system for trail and ultra runners. Connects your Garmin and Oura data with a persistent local workspace to give you daily readiness assessments, training plans, and race preparation — all tailored to your specific profile and goal race.

---

## Getting started (new athlete)

Follow these steps once before using any coaching features.

**Step 1 — Connect your data sources**

Copy `claude_desktop_config.example.json` to `%APPDATA%\Claude\claude_desktop_config.json`, fill in your API tokens, and restart Claude Desktop from the system tray. See the [MCP servers](#mcp-servers-data-sources) section below for token setup instructions.

**Step 2 — Open your workspace in Cowork**

In Claude Desktop, open this folder as your Cowork workspace. Claude will read `CLAUDE.md` automatically and know how to use all the coaching skills.

**Step 3 — Copy your workspace files**

Copy these files from `setup-template/` to the workspace root:

| File | What it is |
|------|-----------|
| `athlete-profile.md` | Your biometrics, HR zones, training history |
| `race-card.md` | Your target race details |
| `events-log.md` | Log for illness, travel, disruptions |
| `memory.md` | Technical notes and coaching continuity |
| `training-dashboard.html` | Blank dashboard — populated by `update-dashboard.py` |

**Step 4 — Fill in your athlete profile**

Ask Claude for help: *"Help me fill in my athlete profile"*

Claude can pull your resting HR, HRV baseline, and recent training volume directly from Garmin to pre-fill the key fields. At minimum you'll need:

- `lthr_bpm` — your lactate threshold heart rate
- `max_hr_bpm` — your maximum HR
- `resting_hr_bpm_range` and `hrv_baseline_ms_range` — for daily readiness interpretation
- `hr_zone_z1_max` through `hr_zone_z5_range` — used when creating Garmin workouts

**Step 5 — Fill in your race card**

Ask Claude for help: *"Help me fill in my race card for [race name]"*

Claude can look up race details online and help structure aid stations, cutoffs, and pacing targets. The more detail you add, the better the training plan can be tailored.

**Step 6 — Edit the dashboard header**

Open `training-dashboard.html` in a text editor and update the name and race at the top:

```html
<title>[YOUR NAME] — Training Dashboard</title>
<span class="title">[YOUR NAME]</span>
<span class="sub">[Race name · Race date]</span>
```

**Step 7 — Build your activity cache**

Ask Claude: *"Update my activity cache"*

This fetches your Garmin history and builds `activity-cache.csv`. The first sync may take a few minutes depending on how far back your history goes.

**Step 8 — Ask for a training program**

Ask: *"Create a training program for my race"*

Claude will build a periodised season plan (`training-program.md`) based on your profile, race date, and current fitness.

**You're ready.** Ask for a plan, check your daily readiness, or review last month's training.

---

## Daily use

**Morning check-in** — *"How do I feel today?"* or *"What's my readiness?"*

Claude combines Garmin Body Battery, HRV, sleep, training readiness score, recent training load, and any logged disruptions into a 🟢 / 🟡 / 🔴 verdict with a specific recommendation. If Oura is set up, body temperature and Oura readiness score are included automatically.

**Get a training plan** — *"Make me a plan for this week"* or *"Plan the next 10 days"*

Claude builds a plan, saves it as a draft for you to review, then pushes sessions to your Garmin calendar only after you approve. Running and strength sessions go to Garmin as guided workouts with your LTHR-based HR targets.

**Monthly review** — *"How was my training in March?"*

Generates a compact coaching summary from the local cache — no API calls needed. Works across multiple months for trend analysis.

**Log a disruption** — Add a line to `events-log.md`:
```
2026-03-17  SICK      Throat infection, rest day
2026-03-20  CLEARED   Back to normal
2026-03-22  TRAVEL    2-day work trip
```
Types: `SICK`, `CLEARED`, `TRAVEL`, `STRESS`, `ALCOHOL`, `POOR_SLEEP`

The daily readiness skill reads this log and adjusts its interpretation — for example, explaining suppressed HRV as illness rather than training fatigue.

---

## Training dashboard

The dashboard is a standalone HTML file (`training-dashboard.html`) that visualises your training history. It has no server or build step — just open it in any browser.

**What it shows:**
- Daily training calendar (colour-coded by km)
- Weekly volume (km, hours, or elevation)
- Rolling 28-day load trend
- Monthly purpose mix (aerobic base, long runs, tempo, recovery, cross-training)
- All-time modality breakdown (trail, road, swim, strength, etc.)
- Full activity table with sort and filter

**How it works:** `update-dashboard.py` reads `activity-cache.csv` and rewrites the data arrays inside the HTML. The script uses Python's standard library only — no external packages needed.

**Updating:**
```
python update-dashboard.py
```
Claude runs this automatically after every cache sync. You can also run it manually or double-click `update-dashboard.bat` on Windows.

**For a new install:** Copy `setup-template/training-dashboard.html` to the workspace root, edit the name and race lines (Step 4 above), then run `update-dashboard.py` after building your cache.

---

## Planning system

**Level 1 — Strategic: `training-program.md`**
Defines phases, blocks, volume ranges, and session priorities for the full season. The "why" behind weekly decisions. Updated only at major milestones: phase transitions, illness gaps, LTHR test results.

**Level 2 — Tactical: `current-plan.md`**
A concrete plan for a specific period (5 days, 1–2 weeks). Generated fresh on request by the `training-plan` skill — always overwrites the previous active plan. Saved as a draft first; pushed to Garmin only after your approval. Replaced plans are archived to `arkisto/` with a date-stamped filename.

What goes to Garmin: running sessions + strength training, as `[Coach]`-prefixed workouts with absolute HR targets based on your LTHR zones. Swimming, walking, and rest days are noted in the plan file only.

---

## Skills reference

| Skill | What it does | When to use |
|-------|-------------|-------------|
| `training-plan` | Creates a training plan, saves as draft, pushes to Garmin on approval | Whenever you want a plan for the next X days |
| `daily-readiness` | Recovery + readiness assessment with coaching recommendation | Every morning |
| `activity-cache-updater` | Syncs new Garmin activities to local cache | Runs automatically when cache is stale; or ask "update my activity cache" |
| `coach-monthly-summary` | Training volume, intensity, patterns for a given month | Monthly reviews, multi-month trend |
| `garmin-activity-tagger` | Classifies a single activity (purpose, modality, terrain) | When you want to understand what a specific session was |
| `program-health-check` | Audits whether recent training is on track with the strategic program — red/yellow/green report on volume, long runs, strength, hills, back-to-backs, milestones | Before phase transitions, after disruptions, or any time you want a program status check |
| `quick-lookup` | Fast factual lookups from local files — km totals, race cutoffs, nutrition timing, drop bag, events log, current phase. No API calls. | Any simple data retrieval question |
| `garmin-mcp` *(reference)* | Documents Garmin MCP tool selection, parameter formats, response shapes, and known quirks. Claude reads this before making any Garmin API calls — not invoked directly by the user. | — |
| `workspace-audit` | Pre-release architecture audit — checks file system, templates, personal data isolation, skill integrity, path portability, and documentation. Produces a ✅/⚠️/❌ report with a release verdict. | Before sharing this workspace as a plugin, or after major structural changes |

Invoke any skill just by asking naturally — Claude recognises the intent and loads the right skill automatically.

**Activity classification:** The cache updater classifies each activity directly by applying the tagger logic step by step. There is no separate Python script required — Claude handles the full classification and writes the result to CSV.

---

## MCP servers (data sources)

All MCP servers are configured in:
`%APPDATA%\Claude\claude_desktop_config.json`

A ready-to-use template with all three connectors is included in this repo:
**[`claude_desktop_config.example.json`](claude_desktop_config.example.json)**

Copy it to `%APPDATA%\Claude\claude_desktop_config.json`, replace the placeholder token values, and restart Claude Desktop from the system tray.

### Garmin Connect
Provides: activity data, Body Battery, sleep score, training readiness, HRV, heart rates.

Connector: `Taxuspt/garmin_mcp` (uvx, local dev)

Start manually before a session (PowerShell):
```
cmd /c uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp
```

Credentials: stored at `~/.garminconnect` (auto-managed by garth library).
First-time auth: `uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth`

### Oura Ring (optional)
Provides: body temperature deviation, readiness score, HRV balance, sleep quality.

Oura is fully optional. All coaching skills work without it — Garmin data is sufficient. If you have an Oura Ring:

1. Create a Personal Access Token at cloud.ouraring.com → Developer → Personal Access Tokens
2. Add it to `claude_desktop_config.json` under the `oura` server's `env` block:
   ```json
   "OURA_PERSONAL_ACCESS_TOKEN": "your_token_here"
   ```
3. Restart Claude Desktop.

### Telegram (optional)
Provides: a remote interface to send coaching questions and log events from your phone, without opening Cowork.

Telegram is fully optional. To enable it:

1. Create a Telegram bot via @BotFather and copy the bot token
2. Add it to `claude_desktop_config.json` under the `telegram-nemo` server's `env` block:
   ```json
   "TELEGRAM_BOT_TRAIL_COACH": "your_bot_token_here"
   ```
3. Restart Claude Desktop. A scheduled task polls for new messages hourly.

---

## Key files

| File | Purpose | Personal? |
|------|---------|-----------|
| `athlete-profile.md` | Your biometrics, HR zones, training history. Fill in once, update after tests. | ✅ |
| `race-card.md` | Target race: course overview, aid stations, cutoffs, target splits. Coaching reference. | ✅ |
| `race-day-guide.md` | Race execution detail: heat management, nutrition plan, drop bag, checklists. | ✅ |
| `training-program.md` | Season plan: phases, blocks, priorities, volume ranges. Generated by Claude. | ✅ |
| `events-log.md` | Log of illness, travel, and other disruptions. Edit manually. | ✅ |
| `memory.md` | Technical notes and cross-session coaching continuity. | ✅ |
| `CLAUDE.md` | Active coaching rules Claude follows automatically. | ⬜ |
| `activity-cache.csv` | All classified activities. The central data store. | ✅ |
| `training-dashboard.html` | Visual training overview. Open in browser. Auto-regenerated after cache sync. | ✅ |
| `update-dashboard.py` | Regenerates the dashboard from the cache. No external dependencies. | ⬜ |
| `update-dashboard.bat` | Windows shortcut to run the dashboard script. | ⬜ |
| `oura-fetch.py` | Legacy fallback for Oura data (writes `oura-today.json`). Not needed — Oura is fetched live via the MCP connector (see above). | ⬜ |
| `current-plan.md` | Active training plan (rolling). Overwritten when a new plan is created; previous plan archived to `arkisto/`. | ✅ |
| `setup-template/` | Blank starting files for new athletes. Copy to workspace root. | ⬜ |

---

## Troubleshooting

**Garmin data not available** — Start the Garmin MCP server manually (see above). If it's already running, restart it.

**Activity cache is stale** — Ask: *"Update my activity cache"*. Requires Garmin MCP running.

**Training dashboard shows old data** — Run `python update-dashboard.py` from the workspace folder, or double-click `update-dashboard.bat`.

**Skills not triggering** — Skills in this workspace are loaded directly from their `SKILL.md` files in subdirectories (e.g. `daily-readiness/SKILL.md`). No global installation needed. If a skill isn't running, check that the subdirectory and SKILL.md file exist.
