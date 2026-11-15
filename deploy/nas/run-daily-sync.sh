#!/bin/sh
# Daily activity-cache sync + dashboard rebuild. Run by DSM Task Scheduler (user root), e.g. 06:30.
# Place this file in /volume1/docker/coach/ next to compose.yaml. The exit code is passed through, so
# Task Scheduler's "only when the script terminates abnormally" email works as a failure alert.
cd /volume1/docker/coach || exit 1

PROMPT='Run the activity-cache-updater skill (read /workspace/activity-cache-updater/SKILL.md). ATHLETE_DIR is athletes/tommi. Sync new Garmin activities into the cache; if any were added, also run the aerobic-efficiency-updater skill and scripts/update-dashboard.py as CLAUDE.md describes. If nothing is new, say so and change nothing. Report briefly what you did.'

OUT=$(/usr/local/bin/docker compose run --rm -T coach claude -p "$PROMPT" \
  --mcp-config /etc/coach/mcp.json \
  --allowedTools "Read,Glob,Grep,Edit,Write,Bash(python3 scripts/update-dashboard.py:*),Bash(python3 scripts/resolve_athlete.py:*),mcp__garmin,mcp__oura" \
  --max-turns 40 </dev/null 2>&1)
RC=$?

{ echo "=== $(TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M:%S') exit=$RC"; echo "$OUT"; } >> logs/daily-sync.log
echo "$OUT"
exit $RC
