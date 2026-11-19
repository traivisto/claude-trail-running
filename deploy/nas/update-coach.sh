#!/bin/sh
# Update the coach from GitHub and put the new version into use.
# Run as root on the NAS:   sudo /volume1/docker/coach/update-coach.sh
#
# What it does:
#   1. Stops if app/ has uncommitted changes (e.g. from an SSH coach session) - commit or discard first.
#   2. git pull --ff-only inside the coach-edit container (uses the deploy key; keeps file ownership).
#   3. Copies changed deploy files (compose.yaml, mcp.json, Dockerfile, *.sh) from app/deploy/nas/ to
#      this folder, rebuilds the image if the Dockerfile changed.
#   4. Recreates the always-on coach-telegram container if code or configuration it uses changed
#      (prompt-only changes need no restart: the prompt is read on every run).
#   5. Runs a smoke test and appends a summary to logs/update.log.
# The exit code is non-zero on failure.
cd /volume1/docker/coach || exit 1
DC="/usr/local/bin/docker compose"
GIT="$DC run --rm -T coach-edit git -C /workspace"
LOG=logs/update.log

say() { echo "$*"; echo "$(TZ=Europe/Helsinki date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

dirty=$($GIT status --porcelain) || { say "ERROR: git status failed"; exit 1; }
if [ -n "$dirty" ]; then
  say "ERROR: app/ has uncommitted changes - commit or discard them first (SSH coach session):"
  echo "$dirty"
  exit 1
fi

before=$($GIT rev-parse HEAD) || exit 1
$GIT pull --ff-only || { say "ERROR: git pull failed (diverged history or no network?)"; exit 1; }
after=$($GIT rev-parse HEAD) || exit 1
if [ "$before" = "$after" ]; then
  say "Already up to date ($(echo "$after" | cut -c1-7))"
  exit 0
fi
changed=$($GIT diff --name-only "$before" "$after")
say "Updated $(echo "$before" | cut -c1-7) -> $(echo "$after" | cut -c1-7)"

rebuild=0
restart=0
for f in compose.yaml mcp.json Dockerfile run-daily-sync.sh coach-chat.sh update-coach.sh; do
  if ! cmp -s "app/deploy/nas/$f" "$f"; then
    cp "app/deploy/nas/$f" "$f.new" && chmod +x "$f.new" && mv "$f.new" "$f"  # mv: safe for a running script
    say "  updated $f"
    case "$f" in Dockerfile) rebuild=1; restart=1 ;; compose.yaml|mcp.json) restart=1 ;; esac
  fi
done
chmod +x run-daily-sync.sh coach-chat.sh update-coach.sh 2>/dev/null

echo "$changed" | grep -Eq '^(scripts/(telegram_poll|resolve_athlete)\.py)$' && restart=1

if [ "$rebuild" = 1 ]; then
  say "  rebuilding image"
  $DC build || { say "ERROR: build failed"; exit 1; }
fi
if [ "$restart" = 1 ]; then
  say "  recreating coach-telegram"
  $DC up -d --force-recreate coach-telegram || { say "ERROR: could not start coach-telegram"; exit 1; }
fi

out=$($DC run --rm -T coach python3 scripts/resolve_athlete.py </dev/null 2>&1) \
  && say "Smoke test ok (athlete: $out)" || { say "ERROR: smoke test failed: $out"; exit 1; }
say "Done. Changed files:"
echo "$changed"
