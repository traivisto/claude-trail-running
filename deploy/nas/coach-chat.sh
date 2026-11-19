#!/bin/sh
# Interactive coach session inside the container (Garmin + Oura MCP tools available, workspace writable).
# Run over SSH with a terminal:   ssh -t <admin>@<nas> "sudo /volume1/docker/coach/coach-chat.sh"
# Continue the previous conversation:  ... coach-chat.sh -c     (history is kept in ./home)
# Any extra arguments are passed to `claude`.
cd /volume1/docker/coach || exit 1
exec /usr/local/bin/docker compose run --rm coach-edit claude --mcp-config /etc/coach/mcp.json "$@"
