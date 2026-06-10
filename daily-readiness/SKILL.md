---
name: daily-readiness
description: >
  Assesses the athlete's current training readiness and physical condition by combining
  live Garmin health data (sleep, HRV, Body Battery, resting HR, training readiness score)
  AND Oura Ring data (body temperature deviation, readiness score) with recent training
  load from the local activity cache AND the events log (illness, travel, disruptions).
  Use whenever the user asks about how they're feeling today, whether they should train,
  what kind of session makes sense, how recovered they are, or what their current condition
  is. Triggers include: "how am I today?", "am I ready to train?", "what should I do
  today?", "how recovered am I?", "show me my readiness", "should I do a hard session?",
  "how tired am I?", "what's my training status?", "daily check-in". Finnish
  triggers: "miltä näyttää päivän kunto", "pitäisikö levätä", "mitä tänään?",
  "miten olen palautunut", "olenko valmis treenaamaan". Prefer this skill
  over raw Garmin or Oura tool calls whenever the goal
  is a coaching-oriented readiness assessment rather than raw data lookup.
---

# Daily Readiness Assessment

Produce a concise, coaching-oriented snapshot of today's readiness by combining
overnight recovery signals from Garmin and Oura with recent training load from the
activity cache and any recent events (illness, travel, disruptions) from the events log.
The goal is one clear answer: what kind of session (if any) makes sense today?

## Step -1: Discover workspace

```bash
find /sessions -maxdepth 4 -name 'athlete-profile.md' 2>/dev/null | head -1
```

Use the containing directory as **WORKSPACE**. All file references below are relative to it.

**Cache file:** `WORKSPACE/activity-cache.csv`
**Events log:** `WORKSPACE/events-log.md`
**Athlete profile:** `WORKSPACE/athlete-profile.md` *(single source of truth for biometrics, HR zones, training history — the thresholds in Step 5 are derived from this file)*
**Race card:** `WORKSPACE/race-card.md` *(single source of truth for race date, start time, course details, and target splits)*

---

## Step 0: Check data freshness before fetching

Run a quick freshness check **before fetching any data** so the user can sync devices first if data is missing.

### 0a: Oura
Call `mcp__oura__oura_daily_summary` with `{"date": "YYYY-MM-DD"}` (today).
- Returns data → Oura OK
- Returns error or empty → **Oura data missing** (ring not synced)

### 0b: Garmin live data
Call `mcp__garmin__get_sleep_summary` with `{"date": "YYYY-MM-DD"}` (today). Lightweight call (~350 B) to check if Garmin is synced.
- Returns data → Garmin OK
- Returns empty or error → **Garmin data missing** (watch not synced)

### 0c: Activity cache
Follow the **Activity cache sync rule in CLAUDE.md** (the single source of truth for cache freshness):
1. Read `WORKSPACE/activity-cache.csv` (tail only, `offset` near end-of-file, `limit: 20`) to find the most recent cached `date`.
2. Call `mcp__garmin__get_activities_by_date` from the day **after** that date through today. This catches both stale caches and a planned workout completed earlier today.
3. New activities returned → run the **activity-cache-updater** skill now, then continue. Nothing returned → cache confirmed current.
4. Skip the Garmin call only if the cache was already synced earlier in this same session.

### 0d: Decision logic

**If Oura and Garmin are OK** (cache was handled automatically in 0c): continue directly to Step 1 with no prompt.

**If Oura or Garmin data is missing:** tell the user what is missing and ask how to proceed. Example:

> Before the readiness analysis, I noticed:
> - **Oura**: no data for today — ring not synced
> - **Garmin**: not synced
>
> Do you want to sync first (close Cowork, sync, come back) or continue now with available data?

Wait for the user's response before continuing.
- "Sync first" → wait, user returns and restarts
- "Continue now" / "go ahead" → proceed to Step 1, note which data was missing in the readiness card

---

## Step 1: Fetch all data in parallel

> 📖 **Garmin tool parameters, response shapes, and quirks:** read `garmin-mcp/SKILL.md`. Key points: use `get_sleep_summary` (not `get_sleep_data`), and `activity_id` is always a number type.

Call these tools simultaneously, and also read both local files:

1. **`mcp__garmin__get_body_battery`** with `{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}` (today)
   - Extracts: Body Battery charged/drained, current level, overnight feedback

2. **`mcp__garmin__get_training_readiness`** with `{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}` (today)
   - Extracts: Training Readiness score (0–100) and contributing factors

3. **`mcp__garmin__get_training_status`** with `{"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}` (today)
   - Extracts: Training Status label (Productive, Maintaining, Recovery, Detraining, etc.)

4. **`mcp__garmin__get_sleep_summary`** — already fetched in Step 0b; reuse that result, do not call again.
   - Extracts: `sleep_hours`, `sleep_score`, `avg_overnight_hrv`, `deep_sleep_seconds`, `light_sleep_seconds`, `rem_sleep_seconds`, `awake_seconds`
   - Lightweight (~350 bytes). Use this instead of `get_sleep_data` (which returns ~200 KB of time-series data and should be avoided).

4b. **`mcp__garmin__get_rhr_day`** with `{"date": "YYYY-MM-DD"}` (today)
   - Extracts: resting heart rate (bpm)

5. **`mcp__garmin__get_stress_data`** with `{"date": "YYYY-MM-DD"}` (today) *(optional)*
   - Extracts: stress level if available

6. **`mcp__oura__oura_daily_summary`** — already called in Step 0a; reuse that result, do not call again.
   - Extracts: `readiness.score`, `readiness.contributors.body_temperature`, `readiness.temperature_deviation`, `readiness.temperature_trend_deviation`, `sleep.score`
   - If the call failed in Step 0a, skip Oura fields in the output card.

7. **Read `WORKSPACE/activity-cache.csv` using the Read tool** — recent training history. Read only the tail (e.g., last ~50 rows) by using a large `offset` — this gives 14+ days of context at low token cost. Never read this file via bash (`cat`/`tail`/`head`) because the Cowork mount may be stale.
8. **Read `WORKSPACE/events-log.md`** — illness, travel, and other disruptions
9. **Read `WORKSPACE/current-plan.md`** — extract the entry for today's date to show what session is planned. If the file is missing or today's date is not within the plan period, skip silently.

If Oura tools are unavailable or return errors, continue without them — Garmin data is sufficient.

---

## Step 2: Check the events log

Before interpreting any numbers, scan the events log for entries in the last 14 days.
The log explains things the watch can't — illness, alcohol, poor sleep from stress, travel — and these change how to read the biometric data.

**Illness interpretation:**
- An active SICK entry (no CLEARED follow-up) means training is likely suspended or very limited. HRV and Body Battery will often look suppressed because the body is fighting infection — don't attribute this to overtraining.
- **Post-illness HRV lag:** Even after feeling better, HRV typically stays 10–20% below baseline for 3–7 days as the immune system finishes its work. If there's a recent SICK entry and HRV is below baseline, this lag is the likely explanation — not fatigue from training. Treat the first 2–3 days back with extra caution even if subjective energy feels OK.
- If there's a CLEARED entry, note how many days ago the illness resolved and apply appropriate caution.

**Other disruptions:**
- TRAVEL, STRESS, ALCOHOL, POOR_SLEEP entries similarly explain anomalous readings. Mention them in the output if they're within the last 7 days and likely still affecting recovery.

**If the events log is empty or has no recent entries**, proceed normally with biometric data as the primary signal.

---

## Step 3: Interpret Oura body temperature

Oura measures skin temperature from the finger during sleep and calculates deviation from the personal baseline. This is one of the most sensitive early-warning signals for illness — it often rises before subjective symptoms appear and normalises as recovery completes.

**Temperature deviation (temperature_deviation field, in °C):**
- < 0.5°C → normal, no concern
- 0.5–1.0°C → mildly elevated — worth noting, possible early illness or late recovery
- 1.0–2.0°C → clearly elevated — consistent with active illness or immune response
- > 2.0°C → high — active fever territory, do not train

**Body temperature contributor score (0–100):**
- This is Oura's own scoring of the temperature signal. Found at `readiness.contributors.body_temperature` in oura-today.json. Scores < 50 flag a concern.

**Cross-referencing with events log:**
- If there's an active SICK entry AND temperature is elevated, reinforce the illness signal.
- If temperature has recently normalised (< 0.5°C) after days of elevation, this is a concrete sign of recovery — more reliable than subjective feeling alone. Note how many days since it normalised.
- If temperature is elevated but there's no events log entry, flag it and suggest the user note it.

---

## Step 4: Compute training load from the cache

From the CSV, extract the last 14 days of activities (by date). Calculate:

- **Last 7 days:** session count, total distance (km), total elevation (m), total duration (min)
- **Last 14 days:** same, for context on cumulative load
- **Last hard session:** the most recent activity with purpose = Interval / VO2max, Tempo / Threshold, or Very long / Race sim. Note how many days ago it was and what it was.
- **Consecutive training days:** how many days in a row (ending today or yesterday) that qualify as a *training day*. A day qualifies if it has at least one session where `training_effect_label ≠ RECOVERY` **or** `modality = Gym / strength`. Casual walks, short swims, and other light activity that Garmin labels RECOVERY do not count — they are treated as rest for streak purposes. This prevents overcounting fatigue accumulation on genuinely easy days.
- **Last rest day:** the most recent date where all logged sessions had `training_effect_label = RECOVERY` and modality was not `Gym / strength` — or where no sessions were logged at all.

### Subjective effort signal (RPE / feel)
If the cache contains `rpe` and/or `feel` columns (Garmin's post-activity subjective effort), compute:
- **RPE trend:** mean RPE of the last 3 running sessions that have a value. If this mean ≥ 8 while prescribed effort was easy/base, that is a fatigue flag worth mentioning.
- **Feel trend:** count of "weak" / "very weak" feel labels in the last 7 days. Two or more in a row of low-feel ratings on easy days is a caution signal even when biometrics look OK.
- If neither column has recent values, skip this check silently — it is additive context, not required.

---

## Step 5: Evaluate all readiness signals

### Body temperature (Oura)
See Step 3 thresholds. Temperature is especially valuable during and after illness — treat it as a primary signal when elevated.

### HRV context (Garmin)
Read `hrv_baseline_ms_range` from the Athlete Config block in `athlete-profile.md`. Let the low and high of that range be `H_low` and `H_high`. Interpret:
- > `H_high` → above baseline (positive signal)
- `H_low`–`H_high` → within normal range
- < `H_low` (by up to ~10%) → below baseline (caution signal)
- < `H_low` × 0.85 → significantly suppressed (flag)

*If a recent illness or elevated temperature explains suppressed HRV, note this — don't conflate illness-HRV with training fatigue.*

### Resting HR context (Garmin)
Read `resting_hr_bpm_range` from the Athlete Config block in `athlete-profile.md`. Let the low and high be `R_low` and `R_high`. Interpret:
- ≤ `R_low` + 2 → well recovered
- `R_low` + 3 to `R_high` + 2 → normal range
- > `R_high` + 2 → elevated (caution)
- > `R_high` + 7 → significantly elevated (flag)

### Body Battery (Garmin)
- 75–100 → well charged
- 50–74 → adequate
- 25–49 → low
- < 25 → very depleted

### Training Readiness (Garmin score 0–100)
- 73–100 → Ready (green)
- 40–72 → Moderate (yellow)
- 0–39 → Low (red)

### Oura Readiness score (0–100)
- 85–100 → Optimal
- 70–84 → Good
- 60–69 → Fair
- < 60 → Pay attention

When Garmin and Oura readiness scores diverge significantly, use the lower one as the anchor and briefly note the discrepancy.

### Training load context
- Last hard session ≥ 2 days ago + low cumulative load → good for quality
- Last hard session < 2 days ago OR high consecutive training days → favour easy/rest
- 7-day distance > 110% of `typical_weekly_km` (from athlete-profile.md Athlete Config) → elevated load, flag recovery

---

## Step 6: Synthesise a readiness verdict

Combine all signals into one of three overall states:

- 🟢 **Ready** — Recovery signals are good, training load allows it. Green light for the planned session.
- 🟡 **Moderate** — Mixed signals. OK to train but adjust intensity down or shorten.
- 🔴 **Low** — Clear recovery deficit. Recommend rest or very easy movement only.

Use the worst signal as the anchor. A single very bad signal (Body Battery < 25, temperature > 1.5°C, HRV < `H_low` × 0.85) is enough to pull the verdict to 🔴 Low even if other signals look OK.

**Illness context overrides:** If there's an active or very recent SICK entry, or temperature deviation > 0.5°C, the verdict should lean at least 🟡 Moderate even if other biometric numbers look OK. If biometrics are also poor, go 🔴 Low regardless of Garmin's score.

---

## Step 7: Output the readiness card

Keep this tight — 200–350 words max. The athlete reads this in 30 seconds.

```
## Readiness: [🟢 Ready / 🟡 Moderate / 🔴 Low]

**Recovery signals (last night)**
- Sleep: Xh Xm | Score: X | HRV: X ms ([above/within/below] baseline) | RHR: X bpm
- Body Battery: X → X (charged overnight by X points)
- Stress: [low/moderate/high if available]
- Garmin Readiness: X/100 | Training Status: [label]
- Oura Readiness: X/100 | Body temp: [+X.X°C / normal] *(omit if Oura unavailable)*

**Recent events** *(include only if there are relevant entries in the last 14 days)*
- [e.g. "Sick Mar 6–8 (upper respiratory). Temp normalised Mar 12. Post-illness HRV lag expected."]

**Recent training load**
- Last 7 days: X sessions · X km · X m elev · Xh Xm
- Last hard session: [name] X days ago ([purpose tag])
- [X consecutive training days / Last rest day: X days ago]

**Today's plan**
[Session from current-plan.md for today's date. If it's a rest day, say so explicitly. If the plan file is missing or today is outside the plan period, omit this line.]

**Today's recommendation**
[1–3 sentences. Be specific. Reference the planned session — e.g. confirm it's appropriate given readiness, or suggest modifying it. Mention temperature context when relevant — e.g., "Oura temperature is back to normal (+0.18°C) after peaking at +2.6°C during illness — a reliable sign recovery is complete." or "Temperature is still +0.9°C above baseline, which suggests the immune system is still active — stick to rest even if you feel OK." Mention the race context when relevant — check the race card for accurate dates and details.]
```

---

## Notes

- If the Oura MCP call fails or returns no data, omit the Oura row from the card entirely — no need to flag the absence.
- If the cache file isn't found or is empty for the recent period, note it and rely on biometric signals only.
- If the events log doesn't exist or is empty, proceed with biometric data only.
- If sleep data shows a nap or fragmented sleep, mention it — total hours can be misleading.
- Garmin Training Status labels to interpret: Peaking, Maintaining, Recovery, Detraining, Productive, Unproductive, Strained, Overreaching. "Recovery" and "Detraining" mean different things — Recovery is intentional, Detraining means load has dropped too far.
- If the race card specifies a night start, check the cache for recent night sessions — if the count is low and the race is approaching, flag night-run opportunities when the user is asking late in the day.
- The events log format is: `DATE  TYPE  Notes` — types include SICK, CLEARED, TRAVEL, STRESS, ALCOHOL, POOR_SLEEP, and similar plain-English labels.
- Oura temperature_deviation is measured in °C relative to the personal baseline established over 60+ nights. It is distinct from absolute body temperature.
