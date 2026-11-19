# NAS runtime — setup and operations

A container on a Synology NAS runs the headless coach: one `claude -p` call per job (daily cache sync,
Telegram replies, interactive SSH sessions) against the athlete's data. Placeholders used below:
`<admin>` the NAS admin user, `<nas-ip>` the NAS address, `<id>` the athlete folder name under
`athletes/`, `<owner>/<repo>` the GitHub repository of the code.

Assumptions: DSM 7.4 with Container Manager, SSH on (port 22), a NAS user `coach` (uid 1031, gid 100),
shared folder `docker`.

## What runs where

| Service (compose.yaml) | Purpose | Code mount |
|---|---|---|
| `coach` | one-off headless jobs: `run-daily-sync.sh`, tests | read-only |
| `coach-edit` | interactive SSH session (`coach-chat.sh`), `update-coach.sh` git pull | writable |
| `coach-telegram` | always-on Telegram long-polling loop (`scripts/telegram_poll.py --loop`) | read-only |

| Script (copied from `deploy/nas/` to the NAS folder) | Use |
|---|---|
| `run-daily-sync.sh [athlete-id]` | daily cache sync + dashboard rebuild (Task Scheduler) |
| `update-coach.sh` | pull the code from GitHub and put it into use (by hand) |
| `coach-chat.sh [-c]` | interactive coach session over SSH |

## 1. Folder layout on the NAS (File Station)

```
/volume1/docker/coach/
  Dockerfile  compose.yaml  mcp.json  *.sh   <- from deploy/nas/
  .env                                        <- COACH_ATHLETE_ID=<id> (see 4)
  app/                                        <- the code repo, a git checkout (see 2)
  athletes/<id>/                              <- athlete data (see 2)
  home/  logs/  secrets/                      <- container HOME (tokens, ssh key), run logs, credentials
```

## 2. Upload (File Station drag-and-drop)

- Copy the files of `deploy/nas/` (Dockerfile, compose.yaml, mcp.json, the `.sh` scripts) into
  `/volume1/docker/coach/`.
- Copy the **code repo** into `app/`, **including `.git/`** (clone it on a PC first; `update-coach.sh`
  needs the checkout), but not `docs/archive/` or the contents of `athletes/`. Keep an empty
  `app/athletes/` folder (the mount point for the data volume).
- Copy `athletes/<id>/` into `/volume1/docker/coach/athletes/<id>/`. Athlete folders are git-ignored; they
  never travel through git.

## 3. Ownership and the token (SSH as admin)

```bash
ssh <admin>@<nas-ip>
cd /volume1/docker/coach
sudo chown -R 1031:100 app athletes home logs secrets
sudo chmod 700 secrets
# Paste the token from `claude setup-token` when prompted (input is hidden, not stored in history):
read -rs T; printf 'CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$T" | sudo tee secrets/claude.env >/dev/null; unset T
sudo chown 1031:100 secrets/claude.env && sudo chmod 600 secrets/claude.env
```

## 4. Which athlete: `.env`

compose.yaml serves the athlete named in `COACH_ATHLETE_ID`. Create `/volume1/docker/coach/.env` (the name
is exactly `.env`; Compose reads it automatically; it contains no secrets), see `dotenv.example`:

```bash
echo 'COACH_ATHLETE_ID=<id>' | sudo tee .env >/dev/null
```

Without it every `docker compose` command stops with "set COACH_ATHLETE_ID in ./.env".

## 5. Build and test

`docker compose` is the Compose v2 plugin; on an older Container Manager use `docker-compose`.

```bash
sudo docker compose build
sudo docker compose run --rm coach claude --version
sudo docker compose run --rm coach python3 scripts/resolve_athlete.py
sudo docker compose run --rm coach claude -p "Reply with exactly the word: ok"
sudo docker compose run --rm coach python3 scripts/update-dashboard.py
sudo docker compose run --rm coach claude -p "Read athletes/<id>/athlete-profile.md and name the goal race in one line." --allowedTools Read
```

Expected: a version number; `/workspace/athletes/<id>`; `ok`; the dashboard updated on the NAS copy;
a one-line answer from the profile.

## Phase B — Garmin and Oura inside the container

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

## Phase C — Telegram bot (always-on)

The bot is `scripts/telegram_poll.py` (prompt: `scripts/prompts/telegram-poll.md`). The `coach-telegram`
service runs it as a long-polling loop: replies arrive within seconds, an empty poll does not call Claude
and an idle loop writes nothing to disk. The old hourly Cowork/Task Scheduler poll is retired: **only one
poller may use a bot token**, so switch the old poll task off when the service takes over a token.
(`python3 scripts/telegram_poll.py` without `--loop` does a single poll for manual tests.)

**Test phase (separate test bot, production untouched):**

1. In Telegram, @BotFather → `/newbot` → note the token. Send the new bot a message ("hello").
2. Create `secrets/telegram.env` from `telegram.env.example` (test token, your chat id, and the two
   `TELEGRAM_*_FILE` test-state lines with `<id>` filled in) **before any other compose command** (compose
   reads every env file). Then `sudo chown 1031:100 secrets/telegram.env && sudo chmod 600 secrets/telegram.env`.
3. One cycle by hand: `sudo docker compose run --rm -T coach python3 scripts/telegram_poll.py`, or start
   the service: `sudo docker compose up -d coach-telegram`.
4. Check `athletes/<id>/telegram-test-conversation-log.md`, `logs/telegram-poll.log` and
   `sudo docker compose logs --tail 50 coach-telegram`.

**Cutover to the production bot:** stop the old poller (Cowork scheduled task) first, put the production bot
token in `secrets/telegram.env`, delete the two `TELEGRAM_*_FILE` lines (the defaults are
`<athlete>/telegram-last-update.txt` and `<athlete>/telegram-conversation-log.md`, which carry the
production offset and conversation memory), then
`sudo docker compose up -d --force-recreate coach-telegram`.

After changing `scripts/telegram_poll.py` the container must be restarted
(`sudo docker compose restart coach-telegram`; `update-coach.sh` does it). Prompt-only changes apply on the
next message. What the chat run may call is set in `ALLOWED_TOOLS` in `scripts/telegram_poll.py`: read-only
Garmin tools, a few reversible Garmin writes, Oura, file tools and three fixed scripts
(`scripts/hr_zones.py`, `scripts/monthly_summary.py`, `scripts/program_health.py`) — there is no free shell.

## Scheduling (DSM Task Scheduler, user root)

| Task | Command | Schedule |
|---|---|---|
| Daily sync | `/volume1/docker/coach/run-daily-sync.sh` | daily, e.g. 06:30 |

Enable "send run details by email … only when the script terminates abnormally": the script
exits non-zero on failure. Output goes to `logs/daily-sync.log`.

## If the Telegram bot stops answering

There is no automatic monitoring (a deliberate choice: the bot is not critical). Docker restarts a crashed
container (`restart: unless-stopped`), but a hung one has to be noticed by hand. Over SSH:
`sudo docker compose ps coach-telegram`, `sudo docker compose logs --tail 50 coach-telegram` and
`logs/telegram-poll.log`; `sudo docker compose restart coach-telegram` fixes most things.

## Updating the code (GitHub, deploy key)

The code reaches the NAS through git, never by hand. `app/` is a checkout whose `origin` is the SSH URL
`git@github.com:<owner>/<repo>.git`; the container authenticates with an SSH **deploy key** stored in the
container home (`home/.ssh/deploy_key` on the NAS, `/home/coach/.ssh/deploy_key` inside), selected by
`core.sshCommand` in the repo's git config. One-time setup:

```bash
cd /volume1/docker/coach
sudo docker compose run --rm coach-edit sh -c 'mkdir -p ~/.ssh && ssh-keygen -t ed25519 -N "" -f ~/.ssh/deploy_key -C coach-nas && cat ~/.ssh/deploy_key.pub'
# GitHub: repository → Settings → Deploy keys → add the printed public key
# (tick "Allow write access" only if SSH coach sessions on the NAS should push).
sudo docker compose run --rm coach-edit git -C /workspace remote set-url origin git@github.com:<owner>/<repo>.git
sudo docker compose run --rm coach-edit git -C /workspace config core.sshCommand 'ssh -i /home/coach/.ssh/deploy_key -o StrictHostKeyChecking=accept-new'
```

Then, whenever there is something new on GitHub: `sudo /volume1/docker/coach/update-coach.sh`. It stops if
`app/` has uncommitted changes (e.g. from an SSH coach session), pulls fast-forward only, copies changed
deploy files (compose.yaml, mcp.json, Dockerfile, the `.sh` scripts) next to compose.yaml, rebuilds the image
if the Dockerfile changed, recreates `coach-telegram` if code or configuration it uses changed, runs a smoke
test and logs to `logs/update.log`. It also stops with a clear message if `.env` is missing.

SSH coach sessions (`coach-chat.sh`) can edit the code because `coach-edit` mounts it writable; commit those
edits and push, or discard them, before the next `update-coach.sh`.

## Several athletes (groundwork)

- Athlete folders are independent; nothing in the code names an athlete. `COACH_ATHLETE_ID` in `.env` is the
  default athlete of every service.
- Daily sync per athlete: schedule one Task Scheduler task per athlete, `run-daily-sync.sh <id>` (it passes
  `COACH_ATHLETE_DIR` for that run and tags the log entry).
- Telegram: one bot (token + chat id) and one `coach-telegram` container **per athlete**. This still has to
  be added to compose.yaml (a service per athlete with its own env file and `COACH_ATHLETE_DIR`; see the
  development backlog); today `coach-telegram` serves the athlete in `.env`.

## Notes

- Athlete data on the NAS is a **copy** of the PC's: athlete folders are git-ignored and there is no
  automatic data sync. Let only one machine write to an athlete's data (PC/Cowork or NAS), otherwise the
  copies diverge.
- Claude Code, the uv tag, the garmin_mcp commit and the oura-mcp version are pinned (below).

## Upgrading pinned versions

Versions are pinned: Claude Code and the uv tag in `Dockerfile`, the garmin_mcp commit and the
oura-mcp version in `mcp.json`. To upgrade one:

1. Change the number (latest Claude Code: `npm view @anthropic-ai/claude-code version`; garmin_mcp:
   `git ls-remote https://github.com/Taxuspt/garmin_mcp HEAD`; oura: `npm view @daveremy/oura-mcp version`).
2. Copy `Dockerfile` / `mcp.json` from `app/deploy/nas/` to `/volume1/docker/coach/` (or run
   `update-coach.sh` after committing), then `sudo docker compose build --no-cache` and
   `sudo docker compose restart coach-telegram`.
3. Run the two connectivity tests under "Phase B", then send one Telegram message.
4. If something breaks, set the previous number back and rebuild.

`garmin-mcp-auth` (token renewal) uses the same pinned URL if you add `@<commit>` to it.
