---
name: coach-monthly-summary
description: >
  Generates a compact training summary for a given month from the local activity cache,
  without calling the Garmin API. Use when the user asks "how was my training in January?",
  "summarize February", "coach summary for March", "how did I train last month?", or
  "compare my last 3 months", "how did January go?", "analyse February",
  "monthly summary", "how have I been training this month?", "training summary",
  "how many km did I run last month?", "how many hours did I train in March?".
  Finnish triggers: "miten tammikuu meni?", "analysoi helmikuu",
  "kuukausiyhteenveto", "miten olen treenannut tässä kuussa?",
  "kuinka paljon juoksin viime kuussa?", "vertaa viime kolmea kuukautta".
  Also use when building multi-month analysis — each monthly summary is ~1 KB, so
  6–12 months combine easily into one context window. Prefer this skill over the
  garmin-monthly-summary skill when the activity cache is available, as it avoids
  expensive API calls and includes purpose-tagged training insights.
---

# Coach Monthly Summary

Generate a compact, coach-oriented training summary for a calendar month by reading
from the local activity cache CSV. No Garmin API calls needed for cached months.

## Step 0: Discover workspace

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. All file references below are relative to it.

**Cache file:** `WORKSPACE/activity-cache.csv`
**Athlete profile:** `WORKSPACE/athlete-profile.md` *(single source of truth for biometrics, training history, strengths and development areas — read when contextualising monthly data)*
**Race card:** `WORKSPACE/race-card.md` *(single source of truth for goal race — read when mentioning the target race or assessing preparation progress)*
**Events log:** `WORKSPACE/events-log.md` *(sickness, alcohol, travel, tests, milestones and other disruptions — always read this before writing observations, so volume dips and anomalies are explained by facts rather than guesses)*

---

## Step 1: Load all data sources

**Use the Read tool, not bash** (see CLAUDE.md File reading rule — bash sees a stale Cowork mount).

1. Read `WORKSPACE/activity-cache.csv` with the Read tool. For a single recent month, read the tail using `offset` near end-of-file with `limit: 80` — covers ~40 days. For older months or multi-month analysis, read the full file (default `limit: 2000` covers ~6 years of cache at current rates).
2. Read `WORKSPACE/events-log.md` — filter for entries whose date falls within the requested
   month (or just before it, if an illness spans a month boundary). Note any SICK,
   TRAVEL, ALCOHOL, TEST, MILESTONE, or other disruption events so you can reference them later.
3. Check whether the requested month falls within the cached date range.
4. If the month extends beyond the cache frontier (e.g., requesting the current month
   and the cache is a few days old), run the **activity-cache-updater** skill first
   to sync new activities, then continue.
5. If the month is entirely before the cache start date (before Jan 2025), tell the
   user that data is not available for that period.

---

## Step 2: Filter activities for the month

Extract all rows where `date` falls within the requested month. Group them for analysis.

---

## Step 3: Compute aggregates

Calculate these from the filtered rows:

### Volume
- Total sessions count
- Total distance (sum of `distance_km`)
- Total duration (sum of `duration_min`, express as Xh Xm)
- Total elevation (sum of `elevation_m`)
- Breakdown by modality (e.g., Trail running: X sessions, X km; Road running: X sessions, X km)

### Purpose mix
- Count sessions and total km for each purpose tag:
  Recovery, Aerobic base, Long effort, Very long / Race sim,
  Tempo / Threshold, Interval / VO2max, Strength, Cross-training

### Modifiers
- Count of Hill sessions (where `hill` = True)
- Count of Technical terrain sessions (where `technical_terrain` = True)

### Pace trends (running activities only — Trail running + Road running)
- Average pace for Aerobic base sessions
- Average pace for Long effort sessions
- Average pace for Tempo / Threshold sessions (if any)
- Fastest single session pace

### Weekly pattern
- Group activities by ISO week number
- For each week: session count, total km, total duration

### Longest session
- The activity with the greatest distance_km
- Include name, distance, duration, elevation, purpose tag

### Intensity signals
- Average aerobic_te across all sessions
- Average anaerobic_te across all sessions
- Count of sessions by training_effect_label (group and count)

### Subjective effort (if cache has `rpe` and/or `feel` columns)
- Mean RPE across all sessions with a value
- Distribution: count of very_weak / weak / normal / strong / very_strong from `feel` column
- Flag sessions where prescribed intent was easy but RPE ≥ 8 — a structural grey-zone signal

### Time-of-day distribution
- Count sessions by time_of_day tag (Morning / Daytime / Evening / Night)
- Night sessions are specifically relevant if the race card specifies a night/late-evening start — weight them accordingly

---

## Step 4: Build the summary

Output in this exact format. Keep it tight — the entire summary should be under 1.5 KB
so that 6–12 months fit comfortably in a single context window.

```markdown
## [Month Year] — Coach Summary

**Volume:** X.X km | Xh Xm | X,XXX m elev | X sessions
**Longest:** [name] X.X km / Xh Xm / X m elev

**By modality:**
Trail running: X sessions (X.X km) | Road running: X (X.X km) | [others if present]

**Purpose mix:**
Aerobic base: X (X.X km) | Long effort: X (X.X km) | Tempo: X (X.X km) | Recovery: X | Strength: X | Cross-training: X | [others if present]

**Modifiers:** X Hill | X Technical terrain

**Pace (running):**
Aerobic avg: X:XX/km | Long avg: X:XX/km | Tempo avg: X:XX/km | Fastest: X:XX/km

**Intensity:**
Avg aerobic TE: X.X | Avg anaerobic TE: X.X
Labels: X base, X improving, X highly improving, X recovery, X overreaching

**Subjective effort (if available):**
Avg RPE: X.X | Feel: X strong · X normal · X weak | X easy-day sessions with RPE ≥ 8

**Weekly pattern:**
Wk1: X.X km (X sessions) | Wk2: X.X km (X) | Wk3: X.X km (X) | Wk4: X.X km (X) [| Wk5 if applicable]

**Time of day:** X Morning | X Daytime | X Evening | X Night

**Notable events:** [List any SICK / TRAVEL / ALCOHOL / other log entries from the month, e.g. "6.3–28.3 hengitystieinfektio (22 pv)". Omit this line entirely if the events log has no entries for the month.]

**Key observations:**
- [2-4 concise bullet points from a coaching perspective]
- Where volume or intensity is low, explain using events log facts — don't guess.
- Consider: volume trajectory, intensity balance, long run progression,
  hill/technical exposure, recovery adequacy, night session practice
- Flag anything notable: big volume weeks, missing long runs, intensity spikes,
  good consistency, etc.
```

---

## Step 5: Multi-month mode

When the user requests multiple months (e.g., "last 3 months", "Q1 summary",
"how has my training progressed since October?"):

1. Generate each month's summary individually using Steps 2–4.
2. Present all monthly summaries in chronological order.
3. After the last month, add a **Trend Analysis** section:

```markdown
## Trend Analysis: [Start Month] → [End Month]

**Volume trend:** [increasing / decreasing / stable / periodized]
- Monthly km: X → X → X → X
- Monthly hours: X → X → X → X
- Monthly elevation: X → X → X → X

**Long run progression:** [longest run per month]
- [Month]: X km | [Month]: X km | ...

**Purpose balance shift:**
- [How the purpose mix changed — e.g., "More long efforts in Dec/Jan, base-heavy in Oct/Nov"]

**Intensity trend:**
- Avg aerobic TE: X.X → X.X → X.X
- [Any shift in training effect labels]

**Hill & technical exposure:**
- [Trend in hill/technical sessions — weight this against the race card's elevation and terrain profile]

**Coach notes:**
- [3-5 bullets synthesizing the multi-month trajectory]
- Consider: periodization patterns, race readiness progression,
  injury risk indicators, consistency, specificity for target race
```

---

## Notes

- **No API calls**: This skill reads entirely from the local CSV cache. If the cache
  needs updating, delegate to the activity-cache-updater skill.
- **Pace formatting**: Convert decimal min/km to M:SS format (e.g., 6.75 → 6:45/km).
- **Zero handling**: Omit any category with zero entries rather than showing "0".
- **Rounding**: Keep distances to 1 decimal, durations to whole minutes, elevation to whole meters.
- **Athlete context**: Read the race card and athlete profile to understand what matters most for this athlete. Weight coaching observations accordingly — e.g. night sessions matter more if the race starts at night, hill work matters more on mountain courses, long efforts matter more at ultra distances, technical terrain matters more on rocky/rooty courses.
- **Events context**: Always check the events log before writing observations. A 50% volume drop is very different if it's explained by a 3-week illness vs. an unexplained training gap. Use the log to give the athlete accurate, honest context rather than generic worry.
