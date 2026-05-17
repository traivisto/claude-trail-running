---
name: quick-lookup
description: >
  Answers factual lookup questions from local workspace files — NO live Garmin/Oura
  API calls, NO coaching judgment. Use this skill for any question that is a data
  retrieval or factual lookup rather than a coaching analysis. Triggers include:
  "how many km did I run last week?", "how many runs in April?", "what's my longest
  run?", "what time does the race start?", "what's the cutoff at Peurakaltio?",
  "what's in my drop bag?", "when do I take caffeine?", "what's in my events log?",
  "any upcoming travel or disruptions?", "what phase am I in?", "when does the taper
  start?", "what's my target pace for the race?", "how many elevation metres last
  month?". Also use for any Finnish-language equivalents: "montako km viime viikolla?",
  "milloin kilpailu alkaa?", "mitä dropbagiin?". Do NOT use for coaching judgment
  questions (readiness, should I train, am I on track) — those need dedicated skills.
---

# Quick Lookup

Answer factual questions from local workspace files without making any API calls.
The goal is a fast, direct answer — one or two sentences, a number, or a short table.

## Step 0: Discover workspace

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. All file references below are relative to it.

**Workspace files:**
- `WORKSPACE/activity-cache.csv` — training history (distance, HR, purpose, tags)
- `WORKSPACE/race-card.md` — race logistics (start time, cutoffs, splits, course)
- `WORKSPACE/race-day-guide.md` — nutrition, heat management, drop bag, checklists
- `WORKSPACE/events-log.md` — upcoming disruptions, illness, travel, tests, milestones
- `WORKSPACE/training-program.md` — current phase, milestones, program structure

---

## Step 0: Classify the question

Before doing anything else, decide which category this question falls into:

**A — Local file lookup** → proceed with this skill.
Examples: distance totals, run counts, race facts, nutrition timing, drop bag contents, events log, phase status, cutoff times.

**B — Requires live data or coaching judgment** → stop and tell the user which skill to use:
- "How am I today / should I train / am I recovered?" → **daily-readiness**
- "Is my training on track / program audit?" → **program-health-check**
- "How was my training in [month]?" → **coach-monthly-summary**
- "Make me a training plan" → **training-plan**

Be decisive. If the question is genuinely ambiguous (could be A or B), lean toward A and answer from local files, but note the limitation.

---

## Step 2: Route to the right file

Match the question to the right source:

| Question type | File to read |
|---|---|
| Weekly/monthly km, run counts, elevation, pace, HR, purpose tags | `activity-cache.csv` |
| Race start time, cutoffs, aid stations, target splits, course segments | `race-card.md` |
| Nutrition plan, caffeine timing, heat management, drop bag, pre-race checklist | `race-day-guide.md` |
| Upcoming illness, travel, disruptions | `events-log.md` |
| Current phase, milestones, taper start, program structure | `training-program.md` |

For some questions, one file is enough. For others (e.g. "when does the taper start relative to the race?") two files may be needed — read both.

---

## Step 3: Answer

### Cache questions (distance, counts, elevation, etc.)

For any aggregation over the cache, use a short Python script rather than trying to compute in your head. This avoids errors on multi-week or multi-month sums.

**Important — file access pattern:** Bash sees a stale Cowork mount (see CLAUDE.md File reading rule). Do **not** read `activity-cache.csv` directly from bash. Instead:

1. **Read the cache via the Read tool** (Windows-direct, always fresh). For recent-window questions read only the tail using `offset` near end-of-file with `limit: 100`; for arbitrary historical questions read the full file.
2. **Pipe the content into Python via stdin** for aggregation:

```bash
python3 << 'PY'
import sys, csv, io
from datetime import datetime, timedelta
# Paste the CSV content read via the Read tool here as a here-doc:
csv_text = """[paste Read output here, header + relevant rows]"""
rows = list(csv.DictReader(io.StringIO(csv_text)))

today = datetime.today()
week_ago = today - timedelta(days=7)
recent = [r for r in rows if datetime.strptime(r['date'], '%m/%d/%Y') >= week_ago]
total_km = sum(float(r['distance_km']) for r in recent if r['distance_km'])
print(f"Runs: {len(recent)}, Total km: {total_km:.1f}")
PY
```

Alternative pattern: if computation is simple enough (counting, summing a few values), do it directly from the Read-tool output without going through Python.

Adapt the filter and aggregation for whatever is asked (month, phase, activity type, etc.). The `date` field format is `M/D/YYYY`. Key fields: `distance_km`, `duration_min`, `elevation_m`, `purpose`, `modality`, `avg_hr`.

### File lookup questions

Read only the relevant section of the file — don't load the whole thing if a specific section answers the question. Quote or paraphrase the relevant part directly.

---

## Step 4: Format the answer

Keep it short. The whole point of this skill is speed.

- A single number or fact: one sentence.
- A comparison or small table: render it inline, no preamble.
- A list (e.g. drop bag contents): bullet list, no intro paragraph.

Don't add coaching commentary unless the user asked for it. If something looks worth flagging (e.g. volume is notably low), one brief parenthetical is fine — but don't turn a lookup into a coaching session.
