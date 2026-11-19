#!/usr/bin/env python3
"""
telegram_poll.py
────────────────
Telegram coaching bot. Two ways to run it inside the coach container:

  Single poll (e.g. DSM Task Scheduler, or a manual test):
      docker compose run --rm -T coach python3 scripts/telegram_poll.py

  Long-polling loop (always-on container, replies within seconds; see the `coach-telegram` service in
  deploy/nas/compose.yaml):
      python3 scripts/telegram_poll.py --loop

What one cycle does:
  1. Reads new Telegram messages (Bot API getUpdates) from the allowed chat. No messages -> nothing
     happens; Claude is NOT called, so idle cycles cost nothing (and write nothing to disk).
  2. Calls `claude -p` once with scripts/prompts/telegram-poll.md. Claude reads the athlete context,
     updates the conversation log / events log, and returns the replies as JSON.
  3. Sends the replies via the Bot API and only then advances the offset file.

In --loop mode getUpdates is a long poll (Telegram holds the request open up to TELEGRAM_POLL_TIMEOUT
seconds and answers the moment a message arrives). Network errors and failed Claude runs are retried
with a back-off; the process only ends on SIGTERM/SIGKILL (Docker restarts it).

Configuration (environment; see deploy/nas/telegram.env.example):
  TELEGRAM_BOT_TOKEN          bot token                               (required)
  TELEGRAM_ALLOWED_CHAT_ID    the only chat id that is served         (required)
  TELEGRAM_OFFSET_FILE        default <athlete>/telegram-last-update.txt
  TELEGRAM_CONVLOG_FILE       default <athlete>/telegram-conversation-log.md
  TELEGRAM_POLL_TIMEOUT       long-poll seconds in --loop mode, default 50
  COACH_ATHLETE_DIR           see scripts/resolve_athlete.py
  CLAUDE_BIN                  default "claude"
  COACH_LOG_DIR               default /var/log/coach

Only one poller may use a bot token at a time (Telegram would answer 409 to the other); a lock file
also keeps a second local instance from running next to a loop. Pure stdlib.
Changes to this file need a restart of the loop container; edits to the prompt file apply immediately.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import time
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
# Read-only Garmin tools (training, activities, health metrics) + the whole Oura server (read-only).
# Deliberately left out: get_activity_hr_in_timezones (Garmin's %HRmax zones; use scripts/hr_zones.py),
# menstrual/pregnancy data, device settings/alarms, badges/challenges, nutrition.
GARMIN_READ_TOOLS = ",".join("mcp__garmin__" + t for t in (
    "count_activities", "get_acclimation", "get_activities", "get_activities_by_date",
    "get_activities_fordate", "get_activity", "get_activity_exercise_sets", "get_activity_fit_data",
    "get_activity_gear", "get_activity_power_in_timezones", "get_activity_split_summaries",
    "get_activity_splits", "get_activity_typed_splits", "get_activity_types", "get_activity_weather",
    "get_all_day_events", "get_all_day_stress", "get_body_battery", "get_body_battery_events",
    "get_body_composition", "get_calendar_events", "get_cycling_ftp", "get_daily_steps",
    "get_daily_weigh_ins", "get_devices", "get_endurance_score", "get_energy_balance",
    "get_fitnessage_data", "get_floors", "get_garmin_coach_workouts", "get_gear", "get_goals",
    "get_heart_rate_zones", "get_heart_rates", "get_heart_rates_summary", "get_hill_score",
    "get_hrv_data", "get_hrv_trend", "get_lactate_threshold", "get_morning_training_readiness",
    "get_personal_record", "get_power_duration_curve", "get_primary_training_device",
    "get_progress_summary_between_dates", "get_race_predictions", "get_recovery_time_remaining",
    "get_respiration_summary", "get_respiration_trend", "get_rhr_day", "get_running_tolerance",
    "get_running_tolerance_trend", "get_scheduled_workouts", "get_sleep_data", "get_sleep_summary",
    "get_sleep_summary_range", "get_spo2_data", "get_stats", "get_stats_and_body", "get_stats_range",
    "get_steps_data", "get_stress_data", "get_stress_summary", "get_training_effect",
    "get_training_load_balance", "get_training_load_trend", "get_training_plan_workouts",
    "get_training_readiness", "get_training_status", "get_user_summary", "get_vo2max_trend",
    "get_weekly_intensity_minutes", "get_weekly_steps", "get_weekly_stress", "get_weigh_ins",
    "get_workout_by_id", "get_workouts"))
# Writes, all training-related and reversible: (1) workout planning (training-plan skill step 7: create,
# schedule and clean up [Coach] workouts, behind a two-step approval in the prompt); (2) feedback on a
# recorded activity (RPE, feel, name, description). NOT allowed: delete_activity, set_activity_type /
# event_type, HR-zone settings, weigh-ins/body composition/nutrition/gear, courses, device settings.
GARMIN_WRITE_TOOLS = ",".join("mcp__garmin__" + t for t in (
    "upload_workout", "schedule_workout", "delete_workout",
    "set_perceived_effort", "set_activity_feel", "set_activity_name", "set_activity_description"))
ALLOWED_TOOLS = os.environ.get(
    "TELEGRAM_ALLOWED_TOOLS",
    # The only Bash allowed is the fixed HR-zone script (no free shell).
    f"Read,Glob,Grep,Edit,Write,Bash(python3 scripts/hr_zones.py:*),"
    f"{GARMIN_READ_TOOLS},{GARMIN_WRITE_TOOLS},mcp__oura")
MAX_TURNS = os.environ.get("TELEGRAM_MAX_TURNS", "60")  # a week of workouts is ~25 tool calls
MCP_CONFIG = os.environ.get("COACH_MCP_CONFIG", "/etc/coach/mcp.json")
POLL_TIMEOUT = int(os.environ.get("TELEGRAM_POLL_TIMEOUT", "50"))
MAX_FAILURES = 3
RETRY_AFTER_CLAUDE_FAILURE = 60  # seconds, loop mode
MAX_BACKOFF = 300                # seconds, loop mode, network errors
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
           "--allowedTools", ALLOWED_TOOLS, "--max-turns", MAX_TURNS]
    if Path(MCP_CONFIG).exists():
        cmd += ["--mcp-config", MCP_CONFIG]
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


def poll_once(token: str, allowed: int, athlete: Path, offset_file: Path, convlog: Path,
              timeout: int) -> int:
    """One getUpdates + (if there are messages) one Claude run. Returns 0 (idle or success) or 1
    (Claude/sending failed; the offset was not advanced, so the messages are retried)."""
    fail_file = offset_file.with_name(offset_file.name + ".fails")
    last = read_int(offset_file)
    updates = tg(token, "getUpdates", {
        "offset": last + 1, "limit": 100, "timeout": timeout,
        "allowed_updates": json.dumps(["message"]),
    }, timeout=timeout + 15)
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


def main() -> int:
    loop = "--loop" in sys.argv[1:]
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    allowed = int(os.environ["TELEGRAM_ALLOWED_CHAT_ID"])
    athlete = resolve()
    offset_file = Path(os.environ.get("TELEGRAM_OFFSET_FILE") or athlete / "telegram-last-update.txt")
    convlog = Path(os.environ.get("TELEGRAM_CONVLOG_FILE") or athlete / "telegram-conversation-log.md")

    lock = open(offset_file.with_name(offset_file.name + ".lock"), "w")  # held for the process lifetime
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another poll is still running; exiting")
        return 0

    if not loop:
        return poll_once(token, allowed, athlete, offset_file, convlog, timeout=0)

    log(f"long-polling started (timeout {POLL_TIMEOUT}s)")
    backoff = 5
    while True:
        try:
            rc = poll_once(token, allowed, athlete, offset_file, convlog, timeout=POLL_TIMEOUT)
            backoff = 5
            if rc != 0:
                time.sleep(RETRY_AFTER_CLAUDE_FAILURE)  # let a transient Claude/Garmin problem pass
        except Exception as e:  # noqa: BLE001 - network/Telegram errors: back off and keep going
            log(f"poll error: {e}; retrying in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        log(f"FATAL: {e}")
        sys.exit(1)
