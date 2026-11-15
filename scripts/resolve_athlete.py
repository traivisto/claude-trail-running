#!/usr/bin/env python3
"""
resolve_athlete.py
──────────────────
Prints the athlete data directory (ATHLETE_DIR) used by all skills and scripts.

Resolution order:
  1. $COACH_ATHLETE_DIR (absolute path) if set
  2. the single athletes/*/athlete-profile.md under the workspace root, if exactly one
  3. otherwise exit with an error listing the candidates (never guess)

Usage:
    python scripts/resolve_athlete.py          # prints the path
    python scripts/resolve_athlete.py --list   # prints all candidates

Import from other scripts:
    from resolve_athlete import resolve   # (add scripts/ to sys.path)

Pure stdlib. Works on Windows, macOS and Linux.
"""

import os
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
ATHLETES = WORKSPACE / "athletes"
MARKER = "athlete-profile.md"


def candidates():
    if not ATHLETES.is_dir():
        return []
    return sorted(p.parent for p in ATHLETES.glob(f"*/{MARKER}"))


def resolve() -> Path:
    env = os.environ.get("COACH_ATHLETE_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if not (p / MARKER).is_file():
            raise SystemExit(f"COACH_ATHLETE_DIR={p} does not contain {MARKER}")
        return p
    found = candidates()
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit(
            f"No athlete found: expected {ATHLETES}/<id>/{MARKER}. "
            "Run scripts/new-athlete.py <id> or set COACH_ATHLETE_DIR."
        )
    names = ", ".join(p.name for p in found)
    raise SystemExit(
        f"Multiple athletes found ({names}); set COACH_ATHLETE_DIR to choose one."
    )


if __name__ == "__main__":
    if "--list" in sys.argv:
        for p in candidates():
            print(p)
    else:
        print(resolve())
