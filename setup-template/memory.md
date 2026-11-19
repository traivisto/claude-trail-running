# Coaching Memory — [Athlete Name]

Persistent cross-session memory for coaching continuity. Updated at end of significant sessions.
Complements athlete-profile.md (stable background) and events-log.md (raw event data).

---

## Infrastructure & tooling

- **Garmin MCP**: Taxuspt/garmin_mcp via uvx, started by Claude Code from its MCP config (reconnect with `/mcp` if it drops); manual start for debugging: `uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp`
- **Oura** (optional): fetched live via `mcp__oura__` MCP tools (daveremy/oura-mcp, token in Claude Desktop MCP config). Skills call `mcp__oura__oura_daily_summary` directly and skip Oura gracefully if the tools are unavailable. Legacy fallback: `oura-fetch.py` + `oura.env` → `oura-today.json` (not needed when the MCP connector is configured).
- **Skill update process**: Edit SKILL.md → zip as .skill → present_files → "Copy to your skills"

---

## Active health situation

*(Update as needed)*

---

## Coaching observations & decisions

*(Key insights, agreed priorities, patterns noticed)*

---

## Activity cache status

- **Last updated:** [date]
- **Covers:** [date range] ([N] activities)

---

## Open items

- [ ] [Action item]
