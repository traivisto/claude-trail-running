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

## Step 0: Discover workspace

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. All checks below are relative to it.

---

## Step 1: File system — stale and unexpected files

Check for files that should not be present in a clean release.

```bash
WORKSPACE="<discovered path>"

echo "=== __pycache__ ==="
find "$WORKSPACE" -name '__pycache__' -not -path '*/arkisto/*' 2>/dev/null

echo "=== *.skill files outside arkisto ==="
find "$WORKSPACE" -name '*.skill' -not -path '*/arkisto/*' 2>/dev/null

echo "=== *.plugin files in root ==="
find "$WORKSPACE" -maxdepth 1 -name '*.plugin' 2>/dev/null

echo "=== Suspicious temp files (no extension, short random name) ==="
find "$WORKSPACE" -maxdepth 2 -not -path '*/arkisto/*' -not -path '*/.git/*' \
  -type f -not -name '*.*' 2>/dev/null | grep -E '/[a-zA-Z0-9]{6,12}$'
```

**Flag rules:**
- `__pycache__/` anywhere outside arkisto → ⚠️ (harmless but clutters repo)
- `*.skill` files outside arkisto → ⚠️ (old packaging format, superseded)
- `*.plugin` in workspace root → ⚠️ (should be in arkisto)
- Files with no extension and a short random-looking name → ❌ (build artifact)

### 1b: Required generic files present

Verify that all non-personal files a new user needs are actually present in the workspace root.

```bash
for f in oura-fetch.py update-dashboard.py update-dashboard.bat README.md CLAUDE.md; do
  [ -f "$WORKSPACE/$f" ] && echo "EXISTS: $f" || echo "MISSING: $f"
done
```

Any missing file → ❌

### 1c: .gitignore present and covers sensitive files

```bash
if [ -f "$WORKSPACE/.gitignore" ]; then
  echo ".gitignore EXISTS"
  grep -l 'oura.env\|telegram-config\|activity-cache\|oura-today' "$WORKSPACE/.gitignore" \
    && echo "Sensitive files covered ✅" || echo "Sensitive files NOT covered ⚠️"
else
  echo ".gitignore MISSING ⚠️"
fi
```

`.gitignore` absence → ⚠️ (not blocking now, but required before any git/GitHub setup)

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
  --include='SKILL.md' 2>/dev/null
```

Any match → ❌

### 3b: Check CLAUDE.md for personal content

Read `CLAUDE.md` with the Read tool. Scan for:
- Athlete name appearing as a proper noun (not as a placeholder)
- Specific numeric HR values (pattern: `\d{3}\s*bpm` in a coaching context)
- Specific race names
- Personal file paths

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
find "$WORKSPACE" -name 'SKILL.md' -not -path '*/arkisto/*' \
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
find "$WORKSPACE" -path '*/arkisto' -prune -o \
  -path '*-updater' -prune -o \
  -mindepth 2 -maxdepth 3 -type f \
  -not -name 'SKILL.md' \
  -not -path '*/evals/*' \
  -not -path '*/setup-template/*' \
  -not -path '*/.git/*' \
  2>/dev/null | grep -E '/(activity-cache-updater|coach-monthly-summary|daily-readiness|garmin-activity-tagger|garmin-mcp|program-health-check|quick-lookup|training-plan|workspace-audit)/'
```

Any unexpected file inside a skill directory → ⚠️. Review manually to check for personal data.

For `evals/` subfolders, check they contain only eval configuration (JSON with test cases),
not real athlete activity data:

```bash
find "$WORKSPACE" -path '*/evals/*.json' -not -path '*/arkisto/*' 2>/dev/null | \
  xargs -I{} sh -c 'echo "=== {} ===" && head -3 "{}"'
```

---

## Step 5: Path portability

Every workflow SKILL.md must discover the workspace at runtime rather than relying on a
hardcoded folder name. A hardcoded path like `claude-trail-running/activity-cache.csv`
will silently break when a new user names their folder differently.

### 5a: Check for hardcoded workspace folder references

```bash
# Find any SKILL.md that references a path with a hardcoded folder prefix
# Pattern: word-chars/filename.ext  where the prefix is not a variable
grep -rn '[a-zA-Z0-9_-]\+/athlete-profile\|[a-zA-Z0-9_-]\+/activity-cache\|[a-zA-Z0-9_-]\+/race-card\|[a-zA-Z0-9_-]\+/events-log\|[a-zA-Z0-9_-]\+/current-plan' \
  "$WORKSPACE" --include='SKILL.md' 2>/dev/null | \
  grep -v 'WORKSPACE/' | grep -v 'setup-template/'
```

Any match that is not prefixed with `WORKSPACE/` or a bash variable → ❌

### 5b: Check that workflow skills use workspace discovery

```bash
# Each workflow SKILL.md should contain the find-based discovery command
for skill_dir in activity-cache-updater coach-monthly-summary daily-readiness \
                 garmin-activity-tagger program-health-check quick-lookup training-plan; do
  f="$WORKSPACE/$skill_dir/SKILL.md"
  if grep -q 'find /sessions' "$f" 2>/dev/null; then
    echo "✅ $skill_dir — workspace discovery present"
  else
    echo "❌ $skill_dir — workspace discovery MISSING"
  fi
done
```

(garmin-mcp is reference-only and does not need workspace discovery.)

---

## Step 6: Documentation accuracy

### 6a: setup-template/ files match README Step 1 table

Read the README.md Step 1 table (the copy-from-setup-template instructions) and compare
to the actual files in setup-template/. Flag any file mentioned in README but missing
from setup-template/, or any file in setup-template/ not mentioned in README.

### 6b: CLAUDE.md skill table paths match disk

Already covered in Step 4 — no separate check needed.

### 6b: README skill table ↔ CLAUDE.md skill table consistency

Read both files and extract their skill lists. Every skill in CLAUDE.md should also appear
in README's Skills reference section, and vice versa. This catches the case where a new
skill is added to CLAUDE.md but the README is not updated (or the reverse).

- In CLAUDE.md but missing from README skills table → ⚠️
- In README but missing from CLAUDE.md → ⚠️
- Perfect match → ✅

### 6c: Optional integrations documented

Read README.md and verify:
- Oura is documented as optional with `oura-fetch.py` + `oura.env` instructions
- Telegram is documented as optional with `telegram-trail-coach.json` gate
- Neither is presented as required

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
