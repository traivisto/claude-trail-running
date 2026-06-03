# Coaching Memory — [Athlete Name]

Persistent cross-session memory for coaching continuity. Updated at end of significant sessions.
Complements athlete-profile.md (stable background) and events-log.md (raw event data).

---

## Infrastructure & tooling

- **Garmin MCP**: LOCAL DEV connector (Taxuspt/garmin_mcp via uvx). In Cowork mode, requires manual start: `cmd /c uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp`
- **Oura** (optional): run `oura-fetch.py` manually before a morning check-in. Requires `oura.env` with `OURA_API_TOKEN=...`. Output: `oura-today.json`. Skills read this file and skip Oura gracefully if it's missing.
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
