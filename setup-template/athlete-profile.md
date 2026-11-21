# Athlete Profile: [YOUR NAME]
> Stable background card for coaching use. Does not include current training load or recent metrics — pull those separately from Garmin.

---

## Athlete Config
> Machine-readable thresholds used by coaching skills. Skills read values from this block rather than hardcoding them.
> **Units note:** all `*_pace_min_km` values are **decimal minutes per km** (5.50 = 5:30/km), not M.SS.

```
name:                   [YOUR NAME]
max_hr_bpm:             [bpm]
lthr_bpm:               [bpm]
resting_hr_bpm_range:   [X–Y]
hrv_baseline_ms_range:  [X–Y]
hr_zone_z1_max:         [bpm]
hr_zone_z2_range:       [X–Y]
hr_zone_z3_range:       [X–Y]
hr_zone_z4_range:       [X–Y]
hr_zone_z5_range:       [X–Y]
aerobic_threshold_pace_min_km:    [decimal min/km]
anaerobic_threshold_pace_min_km:  [decimal min/km]
aerobic_baseline_pace_min_km:     [decimal min/km, easy flat pace]
long_effort_baseline_pace_min_km: [decimal min/km]
hill_modifier_threshold_m_per_km: 40
technical_terrain_multiplier:     1.25
vo2max_ml_kg_min:       [value]
typical_weekly_km:      [km]
long_run_threshold_km:  15
long_run_threshold_min: 90
very_long_threshold_km: 30
very_long_threshold_min: 180
```

---

## Identity

- **Name:** [Full name]
- **Sex:** [Male / Female]
- **Born:** [Year or approximate age]
- **Location:** [City, Country]
- **Sport:** [Primary sport(s)]
- **Coaching history:** [Self-coached / previously coached / etc.]
- **Injury history:** [Significant injuries or none]

---

## Biometrics (stable baselines)

- **Height:** [cm]
- **Race-season weight:** [kg]
- **Max HR:** [bpm] *(source: Garmin settings / field test / estimated)*
- **Lactate threshold HR:** [bpm] *(source: Garmin auto-detected / field test)*
- **Resting HR:** [bpm]
- **HRV:** [ms weekly average, stable baseline]
- **HR zones (LTHR-based):** Z1 ≤[X] / Z2 [X]–[X] / Z3 [X]–[X] / Z4 [X]–[X] / Z5 [X]–[X] bpm

---

## Annual Training Volume (recent baseline)

| Year | Distance | Time on feet | Elevation gain | Sessions/week (avg) |
|------|----------|-------------|----------------|----------------------|
| [Year] | [km] | [h] | [m] | [N] |

**Training availability:** [X–Y hours per week]
**Typical weekly running volume:** [~X km]

---

## Activity Mix (typical year)

- [Sport 1]: ~[X]%
- [Sport 2]: ~[X]%
- [Other]: ...

---

## Race History

| Year | Race | Distance | Time | Finish position / percentile |
|------|------|----------|------|-------------------------------|
| [Year] | [Race name] | [km] | [h:mm] | [X%] |

---

## Fitness Baselines

| Metric | Peak (race season) | Off-season |
|--------|-------------------|------------|
| Garmin Endurance Score | [X] | [X] |
| Garmin Hill Score | [X] | [X] |

---

## Seasonal Training Pattern

- **[Month range]:** [Description]
- **[Month range]:** [Description]

---

## Athlete Strengths

- [Strength 1]
- [Strength 2]

---

## Development Areas

- [Area 1]
- [Area 2]

---

## Current Goal (Year)

**Race:** [Race name] — [distance], [date]
**Athlete's goal:** *"[Quote from athlete]"*
