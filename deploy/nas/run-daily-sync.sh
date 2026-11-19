#!/bin/sh
# Daily activity-cache sync + dashboard rebuild. Run by DSM Task Scheduler (user root), e.g. 06:30.
# Place this file in /volume1/docker/coach/ next to compose.yaml. The exit code is passed through, so
# Task Scheduler's "only when the script terminates abnormally" email works as a failure alert.
#
#   run-daily-sync.sh              the athlete from COACH_ATHLETE_ID in ./.env
#   run-daily-sync.sh <athlete-id> that athlete (folder name under athletes/); schedule one task per athlete
cd /volume1/docker/coach || exit 1

ID="$1"
case "$ID" in
  "") ID_ARGS=""; TAG="" ;;
  *[!A-Za-z0-9_-]*) echo "invalid athlete id: $ID" >&2; exit 2 ;;
  *) ID_ARGS="-e COACH_ATHLETE_DIR=/workspace/athletes/$ID"; TAG=" [$ID]" ;;
esac

# ATHLETE_DIR is resolved inside the container from $COACH_ATHLETE_DIR (set by compose or by -e above).
PROMPT='Run the activity-cache-updater skill (read /workspace/activity-cache-updater/SKILL.md). Resolve ATHLETE_DIR as CLAUDE.md describes (the COACH_ATHLETE_DIR environment variable is set). Sync new Garmin activities into the cache; if any were added, also run the aerobic-efficiency-updater skill and scripts/update-dashboard.py as CLAUDE.md describes. If nothing is new, say so and change nothing. Report briefly what you did.'

OUT=$(/usr/local/bin/docker compose run --rm -T $ID_ARGS coach claude -p "$PROMPT" \
  --mcp-config /etc/coach/mcp.json \
  --allowedTools "Read,Glob,Grep,Edit,Write,Bash(python3 scripts/update-dashboard.py:*),Bash(python3 scripts/resolve_athlete.py:*),mcp__garmin,mcp__oura" \
  --max-turns 40 </dev/null 2>&1)
RC=$?

{ echo "=== $(TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M:%S')$TAG exit=$RC"; echo "$OUT"; } >> logs/daily-sync.log
echo "$OUT"
exit $RC
