#!/usr/bin/env python3
"""
new-athlete.py
──────────────
Scaffolds athletes/<id>/ from setup-template/ for a new athlete.

Usage:
    python scripts/new-athlete.py <id>

<id> must be lowercase letters, digits, '-' or '_'. Refuses to overwrite an existing athlete.
Pure stdlib.
"""

import re
import shutil
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
TEMPLATE = WORKSPACE / "setup-template"
ATHLETES = WORKSPACE / "athletes"



def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", sys.argv[1]):
        raise SystemExit("Usage: new-athlete.py <id>   (lowercase letters, digits, - or _)")
    dest = ATHLETES / sys.argv[1]
    if dest.exists():
        raise SystemExit(f"{dest} already exists; refusing to overwrite.")
    shutil.copytree(TEMPLATE, dest)
    (dest / "arkisto").mkdir()
    (dest / "reference").mkdir()
    print(f"Created {dest}")
    print("Next: fill in athlete-profile.md and race-card.md, then build the activity cache")
    print("(see activity-cache-updater/SKILL.md). Cache files are created on first sync.")


if __name__ == "__main__":
    main()
