# NAS runtime — first smoke test

Goal: prove that a container on the Synology NAS can run one headless `claude -p` call and the
repo's scripts against a copy of the athlete data. No scheduling, Telegram or MCP servers yet.

Assumptions: DSM 7.4 with Container Manager, SSH on (port 22), a NAS user `coach` (uid 1031, gid 100),
shared folder `docker`. Replace `<admin>` with your NAS admin user.

## 1. Folder layout on the NAS (File Station)

```
/volume1/docker/coach/
  Dockerfile  compose.yaml            <- from deploy/nas/
  app/                                <- the code repo (see 2)
  athletes/tommi/                     <- athlete data (see 2)
  home/  logs/  secrets/              <- empty folders
```

## 2. Upload (File Station drag-and-drop)

- Copy `deploy/nas/Dockerfile` and `deploy/nas/compose.yaml` into `/volume1/docker/coach/`.
- Copy the **code repo** into `app/`, but **not** `.git/`, `docs/archive/` or the contents of `athletes/`.
  Keep an empty `app/athletes/` folder (it is the mount point for the data volume).
- Copy `athletes/tommi/` into `/volume1/docker/coach/athletes/tommi/`.

## 3. Ownership and the token (SSH as admin)

```bash
ssh <admin>@192.168.86.253
cd /volume1/docker/coach
sudo chown -R 1031:100 app athletes home logs secrets
sudo chmod 700 secrets
# Paste the token from `claude setup-token` when prompted (input is hidden, not stored in history):
read -rs T; printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$T" | sudo tee secrets/claude.env >/dev/null; unset T
sudo chown 1031:100 secrets/claude.env && sudo chmod 600 secrets/claude.env
```

## 4. Build and test

`docker compose` is the Compose v2 plugin; on an older Container Manager use `docker-compose`.

```bash
sudo docker compose build
sudo docker compose run --rm coach claude --version
sudo docker compose run --rm coach python3 scripts/resolve_athlete.py
sudo docker compose run --rm coach claude -p "Reply with exactly the word: ok"
sudo docker compose run --rm coach python3 scripts/update-dashboard.py
sudo docker compose run --rm coach claude -p "Read athletes/tommi/athlete-profile.md and name the goal race in one line." --allowedTools Read
```

Expected: a version number; `/workspace/athletes/tommi`; `ok`; the dashboard updated on the NAS copy;
a one-line answer from the profile.

## Phase B — Garmin and Oura inside the container

Upload `mcp.json` and the updated `compose.yaml` to `/volume1/docker/coach/`.

```bash
cd /volume1/docker/coach
# Oura token (hidden input). Use the token the working Cowork `oura` server uses.
read -rs T; printf 'OURA_TOKEN=%s\n' "$T" | sudo tee secrets/oura.env >/dev/null; unset T
sudo chown 1031:100 secrets/oura.env && sudo chmod 600 secrets/oura.env

# One-time Garmin login (asks for email, password and MFA code; tokens go to ./home/.garminconnect)
sudo docker compose run --rm -it coach uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth
sudo docker compose run --rm coach uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth --verify
```

Connectivity tests (read-only):

```bash
sudo docker compose run --rm coach claude -p "Call mcp__garmin__get_activities_by_date for the last 3 days and report only how many activities you got." --mcp-config /etc/coach/mcp.json --allowedTools "mcp__garmin__get_activities_by_date"
sudo docker compose run --rm coach claude -p "Call mcp__oura__oura_daily_summary for today and report only the readiness score." --mcp-config /etc/coach/mcp.json --allowedTools "mcp__oura__oura_daily_summary"
```

Garmin tokens last about six months; re-run `garmin-mcp-auth --force-reauth` when they expire.

## Phase C — Telegram poll (test bot first)

The poller is `scripts/telegram_poll.py` (prompt: `scripts/prompts/telegram-poll.md`). Empty polls do not
call Claude. Only one poller may use a bot token, so test with a **separate test bot** while the Cowork
task still serves the production bot.

1. In Telegram, @BotFather → `/newbot` → note the token. Send the new bot a message ("hello").
2. Upload `scripts/telegram_poll.py` and `scripts/prompts/telegram-poll.md` into `app/scripts/` (and
   `app/scripts/prompts/`), and the updated `compose.yaml`.
3. Create `secrets/telegram.env` from `telegram.env.example` (token, your chat id) **before any other
   compose command** (compose reads every env file). Then
   `sudo chown 1031:100 secrets/telegram.env && sudo chmod 600 secrets/telegram.env`.
4. Run one cycle: `sudo docker compose run --rm -T coach python3 scripts/telegram_poll.py`
5. Check `athletes/tommi/telegram-test-conversation-log.md` and `logs/telegram-poll.log`.

## Notes

- Data copied to the NAS is a **copy**; do not run both PC and NAS writers on it until the sync step
  (private git repo or similar) is in place.
- Pin `CLAUDE_CODE_VERSION` in the Dockerfile and the `uv` image tag after the first successful build.
- Garmin/Oura/Telegram MCP servers, a workspace `.mcp.json`, cron scheduling and data sync come next.
