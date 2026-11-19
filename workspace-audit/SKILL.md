---
name: workspace-audit
description: >
  Audits the workspace architecture before releasing an updated plugin for other users.
  Checks for stale files, template completeness, personal data isolation in generic files,
  skill integrity, path portability, and documentation accuracy. Produces a structured
  ✅/⚠️/❌ report and a final ready-to-release verdict.
  Trigger phrases: "audit workspace", "tarkista workspace ennen pluginia",
  "onko workspace jaettavissa", "pre-release check", "release check".
---

# Workspace Audit — Pre-Plugin Release

Run a structured architecture audit to verify the workspace is clean, portable, and safe
to share as a plugin. This skill checks structure and logic — it does **not** check whether
the athlete's personal data is correctly filled in (that is the job of `athlete-onboarding-check`).

**Output:** A ✅/⚠️/❌ report per section, followed by a final verdict and a list of
actionable items. Report only — do not fix anything automatically.

---

## Step 0: Locate the workspace root

**WORKSPACE** is the code repo root — the directory that contains `CLAUDE.md`, `scripts/` and the skill
folders (normally the current working directory). It is **not** an athlete directory: the audit checks
the shared code, and personal data under `athletes/` must be absent from everything that would be
released. Do not use bash `find /sessions`.

---

## Step 1: File system — stale and unexpected files

Check for files that should not be present in a clean release.

```bash
WORKSPACE="<discovered path>"

echo "=== __pycache__ ==="
find "$WORKSPACE" -name '__pycache__' -not -path '*/docs/archive/*' -not -path '*/athletes/*' 2>/dev/null

echo "=== *.skill files outside docs/archive ==="
find "$WORKSPACE" -name '*.skill' -not -path '*/docs/archive/*' -not -path '*/athletes/*' 2>/dev/null

echo "=== *.plugin files in root ==="
find "$WORKSPACE" -maxdepth 1 -name '*.plugin' 2>/dev/null

echo "=== Suspicious temp files (no extension, short random name) ==="
find "$WORKSPACE" -maxdepth 2 -not -path '*/docs/archive/*' -not -path '*/athletes/*' -not -path '*/.git/*' \
  -type f -not -name '*.*' 2>/dev/null | grep -E '/[a-zA-Z0-9]{6,12}$'
```

**Flag rules:**
- `__pycache__/` tracked by git (`git ls-files | grep pycache`) → ⚠️; present on disk but untracked
  and covered by `.gitignore` → ℹ️ note only (local runtime artifact, never released)
- `*.skill` files outside docs/archive → ⚠️ (old packaging format, superseded)
- `*.plugin` in workspace root → ⚠️ (should be in docs/archive)
- Files with no extension and a short random-looking name → ❌ (build artifact)

### 1b: Required generic files present

Verify that all non-personal files a new user needs are actually present in the workspace root.

```bash
for f in scripts/update-dashboard.py scripts/update-dashboard.bat scripts/resolve_athlete.py scripts/new-athlete.py \
         scripts/telegram_poll.py scripts/hr_zones.py scripts/monthly_summary.py scripts/program_health.py scripts/hr_histogram.py scripts/prompts/telegram-poll.md \
         deploy/nas/README.md deploy/nas/Dockerfile deploy/nas/compose.yaml deploy/nas/mcp.json \
         deploy/nas/update-coach.sh deploy/nas/run-daily-sync.sh deploy/nas/coach-chat.sh \
         deploy/nas/claude.env.example deploy/nas/telegram.env.example deploy/nas/dotenv.example \
         docs/technical-notes.md README.md CLAUDE.md .gitignore claude_desktop_config.example.json; do
  [ -f "$WORKSPACE/$f" ] && echo "EXISTS: $f" || echo "MISSING: $f"
done
```

Any missing file → ❌

Also compare `git ls-files` (excluding `athletes/`) against CLAUDE.md/README mentions: a tracked
script or deploy file that no documentation mentions → ⚠️ (undocumented). Root helper files
(`git-push.bat`, `claude_desktop_config.example.json`) must be free of personal paths, remotes and
tokens (see 3a/3d).

(The legacy `oura-fetch.py` was retired and archived; Oura is fetched via the MCP connector. Its absence is not an error.)

### 1c: .gitignore present and covers sensitive files

```bash
if [ -f "$WORKSPACE/.gitignore" ]; then
  echo ".gitignore EXISTS"
  grep -q '^athletes/\*' "$WORKSPACE/.gitignore" \
    && echo "athletes/ ignored ✅" || echo "athletes/ NOT ignored ❌"
  grep -q '\.env' "$WORKSPACE/.gitignore" \
    && echo "Credential files covered ✅" || echo "Credential files NOT covered ⚠️"
else
  echo ".gitignore MISSING ⚠️"
fi
```

`.gitignore` absence → ⚠️ (not blocking now, but required before any git/GitHub setup).
`athletes/*` not ignored → ❌.

### 1d: Personal data is not in the code repo

Personal files must live only under `athletes/<id>/`, never in the workspace root, and none may be
tracked by git.

```bash
echo "=== personal files in root (must be none) ==="
for f in athlete-profile.md race-card.md race-day-guide.md training-program.md current-plan.md \
         events-log.md memory.md activity-cache.csv aerobic-efficiency-splits.csv hr-histograms.csv \
         training-dashboard.html telegram-last-update.txt telegram-conversation-log.md \
         telegram-test-offset.txt telegram-test-conversation-log.md coach-backlog.md \
         oura.env oura-today.json arkisto; do
  [ -e "$WORKSPACE/$f" ] && echo "FOUND IN ROOT: $f"
done
echo "=== tracked personal data (must be none) ==="
git -C "$WORKSPACE" ls-files | grep -E '^athletes/' | grep -v '^athletes/\.gitkeep$'
git -C "$WORKSPACE" ls-files | grep -E '(^|/)(athlete-profile|race-card|race-day-guide|training-program|current-plan|events-log|memory|activity-cache|aerobic-efficiency-splits|hr-histograms|training-dashboard)\.(md|csv|html)$' | grep -v '^setup-template/'
```

Any hit → ❌. (Git history may still contain earlier commits of such files; flag that a history
rewrite is needed before publishing the repo.)

### 1e: Deploy files hold no secrets or athlete identity

`deploy/nas/` is released code: it may contain only templates. Real tokens, chat IDs and athlete
folder names belong in untracked files on the NAS (`secrets/*.env`, `.env`).

```bash
echo "=== tracked non-example env/secret files (must be none) ==="
git -C "$WORKSPACE" ls-files | grep -E '(^|/)(\.env|secrets/|.*\.env)$' | grep -v '\.example$'
echo "=== token-like values in deploy/ and root helpers ==="
grep -rnE '[0-9]{8,10}:[A-Za-z0-9_-]{30,}|sk-ant-[A-Za-z0-9_-]+|oat01-|(TOKEN|CHAT_ID|API_KEY)=[^<$ ][^ ]{8,}' \
  "$WORKSPACE/deploy" "$WORKSPACE/claude_desktop_config.example.json" "$WORKSPACE/git-push.bat" 2>/dev/null
echo "=== hardcoded athlete ids / remotes ==="
grep -rnE 'COACH_ATHLETE_(ID|DIR)=[^<$ ]|athletes/[a-z0-9_-]+/' "$WORKSPACE/deploy" 2>/dev/null | grep -v 'athletes/<id>/'
grep -rn 'git remote\|github.com/[A-Za-z0-9_-]*/' "$WORKSPACE/git-push.bat" "$WORKSPACE/deploy" 2>/dev/null
```

- A tracked real env file, or a token-like value → ❌
- A hardcoded athlete id/folder → ❌
- Pinned third-party URLs in `mcp.json` / Dockerfile (public repos, e.g. `Taxuspt/garmin_mcp`) → fine
- Home-directory paths inside the container config (e.g. `/home/coach/...` in `mcp.json`) are
  container-internal; note them as ℹ️ but do not fail 3a for `deploy/`.

---

## Step 2: Template completeness

Verify `setup-template/` contains all required files and that each file uses placeholders
rather than real athlete or race data.

**Required files:**
- `setup-template/athlete-profile.md`
- `setup-template/race-card.md`
- `setup-template/events-log.md`
- `setup-template/memory.md`
- `setup-template/training-dashboard.html`

For each file, check existence:
```bash
for f in athlete-profile.md race-card.md events-log.md memory.md training-dashboard.html; do
  [ -f "$WORKSPACE/setup-template/$f" ] && echo "EXISTS: $f" || echo "MISSING: $f"
done
```

For the `.md` template files, use the **Read tool** to check content — look for placeholder
patterns (`[YOUR NAME]`, `[Full name]`, `[Race name]`, `[Year]`, `[bpm]`) and the **absence**
of real values. Flag if a template contains:
- A real person's name (proper noun where a placeholder is expected)
- Specific numeric HR values in place of `[bpm]` placeholders
- A specific race name in place of `[Race name]`
- A personal file path (`C:\Users\...`, `/Users/...`, `/home/...`)

### 2b: No personal files accidentally in setup-template/

The setup-template/ folder should contain only blank template files. Check that no
personal workspace files have been copied there by mistake.

```bash
# List all files in setup-template/ — any file not in the expected set is suspicious
find "$WORKSPACE/setup-template" -type f | sort
```

Expected contents: `athlete-profile.md`, `race-card.md`, `events-log.md`, `memory.md`,
`training-dashboard.html`. Any other file → ❌ (possible personal data leak).

For `training-dashboard.html`, check via bash:
```bash
grep -c 'rawSessions = \[\]' "$WORKSPACE/setup-template/training-dashboard.html" && echo "Data arrays empty ✅" || echo "Data arrays NOT empty ❌"
grep 'YOUR NAME' "$WORKSPACE/setup-template/training-dashboard.html" && echo "Placeholders present ✅" || echo "Placeholders MISSING ❌"
```

---

## Step 3: Personal data isolation in generic files

Generic files are those that should work for *any* athlete — CLAUDE.md, all `*/SKILL.md`
files, README.md, and setup-template files.

**Definition of personal data:** Any content that describes a specific athlete or race —
athlete name, biometric values (specific LTHR, max HR, HR zone boundaries), race name,
race date, geographic location tied to the athlete, or personal file paths.

### 3a: Check for personal file paths in SKILL.md files

```bash
grep -rn 'C:\\Users\|/Users/\|/home/' "$WORKSPACE" \
  --include='SKILL.md' --include='*.py' --include='*.bat' --include='*.sh' --include='*.md' \
  --include='*.json' --include='*.yaml' --include='Dockerfile' \
  --exclude-dir=athletes --exclude-dir=archive --exclude-dir=.git --exclude-dir=workspace-audit 2>/dev/null
```

(`workspace-audit/` is excluded because this file quotes the patterns it searches for.)

Any match → ❌, except container-internal paths under `deploy/nas/` (the `coach` user's home inside
the image, e.g. `/home/coach/.garminconnect`), which are ℹ️. Judge each hit on whether it names a
real person's machine/home.

### 3b: Check CLAUDE.md for personal content

Read `CLAUDE.md` with the Read tool. Scan for:
- Athlete name appearing as a proper noun (not as a placeholder)
- Specific numeric HR values (pattern: `\d{3}\s*bpm` in a coaching context)
- Specific race names
- Personal file paths

### 3b2: Check SKILL.md files for athlete-specific HR values

```bash
grep -nE '\b[0-9]{3}\s*(–|-)\s*[0-9]{3}\s*bpm|\b1[0-9]{2}\s*bpm|LTHR[^a-z]{1,5}1[0-9]{2}' \
  "$WORKSPACE"/*/SKILL.md | grep -v '^[^:]*workspace-audit/'
```

Compare every hit with the `Athlete Config` block of the athlete directory (read it with the Read
tool; never quote the values in the report). A value that equals one of that athlete's zone
boundaries, LTHR, max HR or baselines → ❌ (personal biometrics in a generic file; replace with
`<zone max from Athlete Config>` or an obviously fictional example). Documented Garmin %HRmax
boundaries are public defaults but are derived from one athlete's max HR → ⚠️ if they equal that
athlete's values.

### 3c: Check README.md for personal content

Read `README.md`. Check that all examples use generic placeholders, not real athlete data.
Example values in code blocks (like HR zones) should use `[X]` syntax, not real numbers.

---

## Step 4: Skill integrity

Verify that the skills referenced in CLAUDE.md all exist on disk, and that no extra
or orphaned skill directories are present.

### 4a: List skills declared in CLAUDE.md

Read `CLAUDE.md` with the Read tool and extract every skill path from the skill table
(lines matching the pattern `` `skill-name/SKILL.md` ``).

### 4b: List SKILL.md files on disk

```bash
find "$WORKSPACE" -name 'SKILL.md' -not -path '*/docs/archive/*' -not -path '*/athletes/*' \
  -not -path '*/setup-template/*' 2>/dev/null | sort
```

### 4c: Compare

- In CLAUDE.md but missing on disk → ❌
- On disk but not in CLAUDE.md → ⚠️ (undocumented skill)
- Perfect match → ✅

### 4d: Check for legacy skills/ folder

```bash
[ -d "$WORKSPACE/skills" ] && echo "LEGACY skills/ folder EXISTS ❌" || echo "No legacy skills/ folder ✅"
```

### 4e: Check skill subdirectory contents

Each skill directory should contain `SKILL.md` and optionally an `evals/` subfolder.
Check that no personal data files (csv, json with athlete data, personal logs) are
present inside skill directories.

```bash
for d in $(find "$WORKSPACE" -maxdepth 2 -name SKILL.md -not -path '*/athletes/*' -not -path '*/docs/*' \
           -not -path '*/setup-template/*' -not -path '*/.git/*' -exec dirname {} \;); do
  find "$d" -type f -not -name 'SKILL.md' -not -path '*/evals/*'
done
```

Any unexpected file inside a skill directory → ⚠️. Review manually to check for personal data.

For `evals/` subfolders, check they contain only eval configuration (JSON with test cases),
not real athlete activity data:

```bash
find "$WORKSPACE" -path '*/evals/*.json' -not -path '*/docs/archive/*' -not -path '*/athletes/*' 2>/dev/null | \
  xargs -I{} sh -c 'echo "=== {} ===" && head -3 "{}"'
```

---

## Step 5: Path portability

Every workflow SKILL.md must resolve the athlete directory at runtime (`ATHLETE_DIR`, see
`CLAUDE.md` → "Athlete directory") rather than relying on a hardcoded folder name or the
Cowork-only `find /sessions` command. A hardcoded path like `claude-trail-running/activity-cache.csv`
will silently break when a new user names their folder differently or runs on another machine.

### 5a: Check for hardcoded workspace folder references

```bash
# Find any SKILL.md that references a path with a hardcoded folder prefix
# Pattern: word-chars/filename.ext  where the prefix is not a variable
grep -rn '[a-zA-Z0-9_-]\+/athlete-profile\|[a-zA-Z0-9_-]\+/activity-cache\|[a-zA-Z0-9_-]\+/race-card\|[a-zA-Z0-9_-]\+/events-log\|[a-zA-Z0-9_-]\+/current-plan' \
  "$WORKSPACE" --include='SKILL.md' 2>/dev/null | \
  grep -v 'ATHLETE_DIR/' | grep -v 'setup-template/' | grep -v '^[^:]*workspace-audit/'
```

Ignore prose matches such as "cache/events-log" (a phrase, not a path).

Any match that is not prefixed with `ATHLETE_DIR/` or a bash variable → ❌. Also flag any remaining
`find /sessions` in a SKILL.md → ❌ (Cowork-only discovery).

### 5b: Check that workflow skills resolve ATHLETE_DIR

```bash
# Each workflow SKILL.md should contain the ATHLETE_DIR resolution step and no Cowork-only find
for skill_dir in activity-cache-updater aerobic-efficiency-updater coach-monthly-summary daily-readiness \
                 garmin-activity-tagger program-health-check quick-lookup training-plan; do
  f="$WORKSPACE/$skill_dir/SKILL.md"
  if grep -q 'Resolve \*\*ATHLETE_DIR\*\*' "$f" 2>/dev/null && ! grep -q 'find /sessions' "$f"; then
    echo "✅ $skill_dir — ATHLETE_DIR resolution present"
  else
    echo "❌ $skill_dir — ATHLETE_DIR resolution MISSING or Cowork-only find still present"
  fi
done
```

(garmin-mcp is reference-only and does not need athlete-directory resolution.)

---

## Step 6: Documentation accuracy

### 6a: setup-template/ files match README Step 1 table

Read the README.md Step 1 instructions (`python scripts/new-athlete.py <id>` copies `setup-template/` to `athletes/<id>/`) and compare
to the actual files in setup-template/. Flag any file mentioned in README but missing
from setup-template/, or any file in setup-template/ not mentioned in README.

### 6b: CLAUDE.md skill table paths match disk

Already covered in Step 4 — no separate check needed.

### 6c: README skill table ↔ CLAUDE.md skill table consistency

Read both files and extract their skill lists (README: the "Skills reference" table; CLAUDE.md:
"Workspace skills" table). Every skill in CLAUDE.md should also appear
in README's Skills reference section, and vice versa. Compare against the on-disk list from 4b too
(helper skills such as `aerobic-efficiency-updater` are easy to forget). This catches the case where a new
skill is added to CLAUDE.md but the README is not updated (or the reverse).

- In CLAUDE.md but missing from README skills table → ⚠️
- In README but missing from CLAUDE.md → ⚠️
- Perfect match → ✅

### 6d: Optional integrations documented

Read README.md and verify it matches the **current architecture** (MCP-first):
- Oura is documented as optional, fetched live via the `mcp__oura__` MCP connector (daveremy/oura-mcp). `oura-fetch.py` + `oura.env` were retired; any mention must say so (not present them as a working fallback). The env var name in README must match `claude_desktop_config.example.json` and `deploy/nas/mcp.json` (currently `OURA_TOKEN` in mcp.json) → mismatch ⚠️.
- Telegram is documented as optional via the always-on `coach-telegram` container on the NAS
  (`scripts/telegram_poll.py --loop`, config in `deploy/nas/`, secrets in `secrets/telegram.env`), with silent skip when no bot is configured. The retired `telegram-nemo` Cowork plugin (`mcp__telegram-nemo__`, hourly scheduled task) and the old `telegram-trail-coach.json` HTTP setup must not be presented as the current setup → ⚠️ outdated.
- The NAS runtime (`deploy/nas/README.md`, `update-coach.sh`, daily sync, chat wrapper) is mentioned in README or CLAUDE.md with a pointer to `deploy/nas/README.md` → missing ⚠️.
- Every script and deploy file listed in 1b appears in the README "Key files" table or is covered by a documented pointer → missing ⚠️.
- Neither integration is presented as required.

Cross-check `CLAUDE.md` statements against `docs/technical-notes.md` and `deploy/nas/README.md`
(same architecture wording, same file names). Contradiction → ⚠️.

---

## Step 7: Produce the report

Output a structured report. Use this format exactly:

```
## Workspace Audit — Pre-Plugin Release
Date: YYYY-MM-DD

### 1. File system
[✅/⚠️/❌] [finding]
...

### 2. Template completeness
[✅/⚠️/❌] [finding per file]
...

### 3. Personal data isolation
[✅/⚠️/❌] [finding per file checked]
...

### 4. Skill integrity
[✅/⚠️/❌] [finding]
...

### 5. Path portability
[✅/⚠️/❌] [finding per skill]
...

### 6. Documentation
[✅/⚠️/❌] [finding]
...

---
[🟢 Ready to release — no blocking issues]
[🟡 Ready with minor caveats — N warnings to address]
[🔴 Not ready — N issues must be fixed before release]

**Action items:**
- ❌ [specific fix required]
- ⚠️ [optional improvement]
```

**Verdict rules:**
- Any ❌ → 🔴 Not ready
- Only ⚠️, no ❌ → 🟡 Ready with minor caveats
- All ✅ → 🟢 Ready to release
