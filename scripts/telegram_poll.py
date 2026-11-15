#!/usr/bin/env python3
"""
telegram_poll.py
────────────────
One poll cycle of the Telegram coaching bot. Intended to run hourly (DSM Task Scheduler) inside the
coach container:

    docker compose run --rm -T coach python3 scripts/telegram_poll.py

What it does:
  1. Reads new Telegram messages (Bot API getUpdates) from the allowed chat. No messages -> exit
     immediately; Claude is NOT called, so empty runs cost nothing.
  2. Calls `claude -p` once with scripts/prompts/telegram-poll.md. Claude reads the athlete context,
     updates the conversation log / events log, and returns the replies as JSON.
  3. Sends the replies via the Bot API and only then advances the offset file.

Configuration (environment; see deploy/nas/telegram.env.example):
  TELEGRAM_BOT_TOKEN          bot token                               (required)
  TELEGRAM_ALLOWED_CHAT_ID    the only chat id that is served         (required)
  TELEGRAM_OFFSET_FILE        default <athlete>/telegram-last-update.txt
  TELEGRAM_CONVLOG_FILE       default <athlete>/telegram-conversation-log.md
  COACH_ATHLETE_DIR           see scripts/resolve_athlete.py
  CLAUDE_BIN                  default "claude"
  COACH_LOG_DIR               default /var/log/coach

Only one poller may use a bot token at a time (Telegram would answer 409 to the other).
Pure stdlib.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_athlete import resolve  # noqa: E402

TZ = ZoneInfo("Europe/Helsinki")
WORKSPACE = Path(__file__).resolve().parent.parent
PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "telegram-poll.md"
ALLOWED_TOOLS = "Read,Glob,Grep,Edit,Write"
MAX_FAILURES = 3
ERROR_TEXT = os.environ.get(
    "TELEGRAM_ERROR_TEXT",
    "Sorry, I could not process your message because of a technical error. Please try again later.",
)


def log(msg: str) -> None:
    line = f"{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        d = Path(os.environ.get("COACH_LOG_DIR", "/var/log/coach"))
        with open(d / "telegram-poll.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def tg(token: str, method: str, params: dict, timeout: int = 30):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=timeout) as r:
            body = json.load(r)
    except urllib.error.HTTPError as e:  # Telegram puts the reason in the body
        raise RuntimeError(f"Telegram {method} HTTP {e.code}: {e.read()[:200]!r}") from None
    if not body.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {str(body)[:200]}")
    return body["result"]


def read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return default


def write_int(path: Path, value: int) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(str(value))  # plain integer, no trailing newline
    os.replace(tmp, path)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE))
    except ValueError:
        return str(path)


def build_prompt(athlete: Path, convlog: Path, msgs: list) -> str:
    now = datetime.now(TZ)
    values = {
        "{{ATHLETE_DIR}}": rel(athlete),
        "{{CONVLOG}}": rel(convlog),
        "{{EVENTS_LOG}}": rel(athlete / "events-log.md"),
        "{{TODAY}}": now.strftime("%Y-%m-%d"),
        "{{NOW}}": now.strftime("%H:%M"),
        "{{MESSAGES_JSON}}": json.dumps(msgs, ensure_ascii=False, indent=2),
    }
    text = PROMPT_FILE.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace(k, v)
    return text


def run_claude(prompt: str) -> str:
    cmd = [os.environ.get("CLAUDE_BIN", "claude"), "-p", prompt,
           "--allowedTools", ALLOWED_TOOLS, "--max-turns", "30"]
    # stdin=DEVNULL: otherwise `claude -p` waits ~3 s for piped input before proceeding
    r = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, timeout=900,
                       stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"claude exited {r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout


def parse_replies(text: str, n: int) -> list:
    dec = json.JSONDecoder()
    found = None
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("replies"), list):
            found = obj["replies"]  # keep the last valid one
    if found is None or len(found) != n or not all(isinstance(x, str) and x.strip() for x in found):
        raise RuntimeError(f"could not parse {n} replies from Claude output: {text[-300:]!r}")
    return found


def main() -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    allowed = int(os.environ["TELEGRAM_ALLOWED_CHAT_ID"])
    athlete = resolve()
    offset_file = Path(os.environ.get("TELEGRAM_OFFSET_FILE") or athlete / "telegram-last-update.txt")
    convlog = Path(os.environ.get("TELEGRAM_CONVLOG_FILE") or athlete / "telegram-conversation-log.md")
    fail_file = offset_file.with_name(offset_file.name + ".fails")

    lock = open(offset_file.with_name(offset_file.name + ".lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another poll is still running; exiting")
        return 0

    last = read_int(offset_file)
    updates = tg(token, "getUpdates", {
        "offset": last + 1, "limit": 100, "timeout": 0,
        "allowed_updates": json.dumps(["message"]),
    })
    if not updates:
        return 0  # nothing new; Claude is not called
    max_id = max(u["update_id"] for u in updates)

    msgs = []
    for u in updates:
        m = u.get("message") or {}
        if m.get("chat", {}).get("id") == allowed and m.get("text"):
            ts = datetime.fromtimestamp(m["date"], TZ)
            msgs.append({"time": ts.strftime("%H:%M"), "date": ts.strftime("%Y-%m-%d"),
                         "text": m["text"][:4000]})
    if not msgs:
        write_int(offset_file, max_id)  # only other chats / non-text updates: skip them silently
        return 0

    log(f"{len(msgs)} new message(s); calling claude")
    try:
        replies = parse_replies(run_claude(build_prompt(athlete, convlog, msgs)), len(msgs))
    except Exception as e:  # noqa: BLE001 - any failure must leave the offset untouched
        fails = read_int(fail_file) + 1
        fail_file.write_text(str(fails))
        log(f"ERROR ({fails}/{MAX_FAILURES}): {e}")
        if fails >= MAX_FAILURES:
            try:
                tg(token, "sendMessage", {"chat_id": allowed, "text": ERROR_TEXT})
            finally:
                write_int(offset_file, max_id)  # give up on these messages
                fail_file.unlink(missing_ok=True)
        return 1

    for text in replies:
        tg(token, "sendMessage", {"chat_id": allowed, "text": text[:4000]})
    write_int(offset_file, max_id)
    fail_file.unlink(missing_ok=True)
    log(f"replied to {len(msgs)} message(s); offset -> {max_id}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"FATAL: {e}")
        sys.exit(1)
