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

## Step 0: Resolve athlete directory

Resolve **ATHLETE_DIR** as defined in `CLAUDE.md` → "Athlete directory": `$COACH_ATHLETE_DIR` if set, otherwise Glob `athletes/*/athlete-profile.md` (exactly one match → its directory; several → ask which athlete). Do not use bash `find`.

All file references below are relative to **ATHLETE_DIR**.

**Cache file:** `ATHLETE_DIR/activity-cache.csv`
**Athlete profile:** `ATHLETE_DIR/athlete-profile.md` *(single source of truth for biometrics, training history, strengths and development areas — read when contextualising monthly data)*
**Race card:** `ATHLETE_DIR/race-card.md` *(single source of truth for goal race — read when mentioning the target race or assessing preparation progress)*
**Events log:** `ATHLETE_DIR/events-log.md` *(sickness, alcohol, travel, tests, milestones and other disruptions — always read this before writing observations, so volume dips and anomalies are explained by facts rather than guesses)*

---

## Step 1: Sync and check coverage

1. If the month extends beyond the cache frontier (e.g. the current month and the cache is a few days
   old), apply the **Activity cache sync rule** in `CLAUDE.md` (run **activity-cache-updater** if new
   activities exist). In the Telegram chat run skip the sync, as the prompt says.
2. If the month is entirely before the cache start (before Jan 2025), tell the user the data is not
   available for that period.

## Step 2: Compute the aggregates (script)

Do **not** compute aggregates by hand. Run `python3 scripts/monthly_summary.py [YYYY-MM ...]` (from the
workspace root, `python3` on Linux; no argument = current month, several months = oldest first). It is
the single place where the aggregates are defined, in every environment (SSH, Cowork, Telegram), so its
docstring is the authority for the exact definitions. For each month it prints:
- **Volume:** sessions, running km (Trail + Road), all-modality km, hours, elevation, breakdown by modality
- **Purpose mix:** sessions and km per purpose tag; **Modifiers:** Hill and Technical terrain counts
- **Pace (Road running only):** aerobic base, long, tempo averages (total time / total distance) and fastest session (>= 2 km). **Trail running** (activity type the athlete picks whenever the route leaves roads/built paths) is never given as pace - trail paces are not comparable (terrain, wet rock) - but as sessions, time, ascent and avg HR; time at a HR zone is the proper trail measure (see Notes)
- **Longest session** (name, distance, duration, elevation, purpose, date)
- **Intensity:** average aerobic / anaerobic TE and training-effect label counts
- **Subjective effort:** mean RPE, feel distribution, easy-day sessions with RPE >= 8
- **Weekly pattern:** ISO-week running km, duration and sessions (`*` = week reaches outside the month)
- **Time of day** and the **events-log** entries of the month (routine training lines omitted)

The last line says how far the cache reaches; keep a staleness caveat in the answer if it says recent days
may be missing.

## Step 3: Check the events log before interpreting

The script prints the month's events-log entries. Read `ATHLETE_DIR/events-log.md` with the Read tool only
if an illness or trip spans a month boundary or the printed lines are not enough. Explain volume dips and
anomalies with these facts rather than guesses.

---

## Step 4: Build the summary

Use the script's numbers only (never recompute) and lay them out in this format. Keep it tight — the entire summary should be under 1.5 KB
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

1. Run the script once with all months (Step 2) and lay out each month with Step 4.
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

## Chat mode (Telegram, headless runs)

Used when the telegram-poll prompt sends you here. The computation is the same as in every other
environment (Step 2, `scripts/monthly_summary.py`); chat differs only in three ways: no sync (the daily
sync keeps the cache current), a plain-text reply of max ~250 words instead of the Step 4 template, and
no free shell (the script is one of three fixed commands). Do not read the cache or compute anything
yourself.

1. Run the script as in Step 2. If its last line says the cache is stale, keep that caveat; do not call
   Garmin just for a summary.
2. Write the reply in the athlete's language, in this order and only with numbers the script printed:
   running km, sessions and hours (add elevation) · longest session · purpose mix · road aerobic/long pace and trail time + avg HR ·
   weekly running km as a short series · RPE/feel if present · one or two observations. The first line
   says if the month is still in progress.
3. Explain dips and spikes with the **Events log** lines first (illness, travel, tests); never guess a
   cause the log does not support. Apply the load and rest reasoning rule of CLAUDE.md: quote the numbers,
   and say whether a reason is program structure or physiology.
4. Several months: one line per month (run km, hours, elevation, longest) and then one or two sentences
   of trend. Skip categories with zero entries.

## Notes

- **No API calls**: This skill reads entirely from the local CSV cache (`scripts/monthly_summary.py` does the reading and computing in every environment). If the cache
  needs updating, delegate to the activity-cache-updater skill.
- **Pace vs trail:** never compare or average trail paces, and never mix trail and road in one pace figure. For trail say time (and avg HR, ascent); time-in-zone per trail run is not in the cache yet (it needs per-second HR via `scripts/hr_zones.py` on one activity).
- **Pace formatting**: Convert decimal min/km to M:SS format (e.g., 6.75 → 6:45/km).
- **Zero handling**: Omit any category with zero entries rather than showing "0".
- **Rounding**: Keep distances to 1 decimal, durations to whole minutes, elevation to whole meters.
- **Athlete context**: Read the race card and athlete profile to understand what matters most for this athlete. Weight coaching observations accordingly — e.g. night sessions matter more if the race starts at night, hill work matters more on mountain courses, long efforts matter more at ultra distances, technical terrain matters more on rocky/rooty courses.
- **Events context**: Always check the events log before writing observations. A 50% volume drop is very different if it's explained by a 3-week illness vs. an unexplained training gap. Use the log to give the athlete accurate, honest context rather than generic worry.
