---
name: garmin-mcp
description: >
  Reference document for Garmin MCP usage in this coaching system. Read this before
  making Garmin MCP tool calls — it maps use cases to the right tools, documents
  response field names, and captures known quirks. Not a workflow skill — use it
  as a lookup when writing or debugging other skills.
---

# Garmin MCP Reference

Kattava hakuteos Garmin MCP -käytölle tässä coaching-järjestelmässä. Muut skillit
lukevat tätä dokumenttia ennen Garmin-kutsujen tekemistä.

**MCP-serverin käynnistys** (tarvittaessa manuaalisesti PowerShellissä):
```
cmd /c uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp
```
Token-hallinta: `~/.garminconnect` (garth-kirjasto). Uusiminen:
```
uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth
```

---

## Domain 1: Recovery & Health — päivittäinen palautumisdata

### `get_sleep_summary` ⭐ kevyin unidata
```
params: { date: "YYYY-MM-DD" }
```
Palauttaa ~350 B. **Käytä aina tätä** `get_sleep_data`:n sijaan (joka palauttaa ~200 KB aikaseriadataa).

Keskeisiä kenttiä:
```json
{
  "sleep_hours": 8.32,
  "sleep_score": 87,
  "sleep_score_qualifier": "GOOD",
  "avg_overnight_hrv": 42.0,
  "deep_sleep_seconds": 3780,
  "light_sleep_seconds": 19740,
  "rem_sleep_seconds": 6420,
  "awake_seconds": 420,
  "awake_count": 0,
  "avg_sleep_stress": 16.0,
  "deep_sleep_percent": 12.6,
  "light_sleep_percent": 65.9,
  "rem_sleep_percent": 21.4
}
```

### `get_body_battery`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Palauttaa listan päivistä:
```json
[{
  "date": "2026-05-16",
  "charged": 70,
  "drained": 0,
  "body_battery_level": "HIGH",   // HIGH / MEDIUM / LOW
  "current_feedback": null,
  "events": []
}]
```
Tulkinta: `charged` = yön aikana ladattu, `drained` = kulunut tähän asti tänään.

### `get_rhr_day`
```
params: { date: "YYYY-MM-DD" }
```
Palauttaa leposykkeen. Kentät:
```json
{
  "allMetrics": {
    "metricsMap": {
      "WELLNESS_RESTING_HEART_RATE": [
        { "value": 52.0, "calendarDate": "2026-05-16" }
      ]
    }
  }
}
```
Poimi: `allMetrics.metricsMap.WELLNESS_RESTING_HEART_RATE[0].value`

### `get_training_readiness`
```
params: { date: "YYYY-MM-DD" }
```
Palauttaa listan (yleensä 1 alkio):
```json
[{
  "date": "2026-05-16",
  "score": 84,
  "level": "HIGH",                        // HIGH / MODERATE / LOW
  "feedback": "WELL_RECOVERED",
  "context": "AFTER_WAKEUP_RESET",
  "sleep_score": 87,
  "sleep_factor_percent": 84,
  "sleep_factor_feedback": "GOOD",
  "recovery_time_hours": 0.0,
  "recovery_factor_percent": 99,
  "hrv_factor_percent": 96,
  "hrv_factor_feedback": "GOOD",
  "hrv_weekly_avg": 38,
  "training_load_factor_percent": 100,
  "training_load_feedback": "VERY_GOOD",
  "stress_history_factor_percent": 70,
  "stress_history_feedback": "GOOD",
  "sleep_history_factor_percent": 81,
  "acute_load": 404
}]
```

### `get_training_status`
```
params: { date: "YYYY-MM-DD" }
```
```json
{
  "date": "2026-05-16",
  "training_status_feedback": "PRODUCTIVE_3",   // ks. alla
  "sport": "RUNNING",
  "acute_load": 404,
  "chronic_load": 548,
  "load_ratio": 0.74,
  "acwr_status": "LOW",          // LOW / OPTIMAL / HIGH / VERY_HIGH
  "acwr_percent": 29,
  "training_balance_feedback": "AEROBIC_HIGH_SHORTAGE",   // ks. alla
  "vo2_max": 46.0,
  "vo2_max_precise": 46.2,
  "monthly_load_aerobic_low": 1586.7,
  "monthly_load_aerobic_high": 440.6,
  "monthly_load_anaerobic": 173.8
}
```

**training_status_feedback -arvot:**
`PEAKING` / `MAINTAINING` / `RECOVERY` / `DETRAINING` / `PRODUCTIVE_1/2/3` / `UNPRODUCTIVE` / `STRAINED` / `OVERREACHING`
- `RECOVERY` = tarkoituksellinen palautuminen (ok)
- `DETRAINING` = kuorma laskenut liian alas (varoitus)

**training_balance_feedback -arvot:**
- `AEROBIC_HIGH_SHORTAGE` = Z3–Z4-työn (tempo/kynnys) vaje — ei pitkä helppo lenkki
- `AEROBIC_LOW_SHORTAGE` = Z1–Z2-pohjatyön vaje
- `ANAEROBIC_SHORTAGE` = anaerobisen työn vaje
- `BALANCED` = tasapaino ok

### `get_hrv_data`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Palauttaa HRV-trendin useammalta päivältä. Käytä kun tarvitaan historiaa — yksittäinen öinen HRV löytyy myös `get_sleep_summary`:sta (`avg_overnight_hrv`).

### `get_stress_data`
```
params: { date: "YYYY-MM-DD" }
```
⚠️ Palauttaa ~35 KB aikaseriadataa. Käytä vain jos stressitaso on relevantti — muulloin ohita.

---

## Domain 2: Aktiviteettien haku ja analyysi

### `get_activities_by_date` ⭐ ensivaiheen haku
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Palauttaa kaikki aktiviteetit aikaväliltä yhdellä kutsulla — ei sivutusta.

Keskeisiä kenttiä per aktiviteetti:
```
activityId          (number — TÄRKEÄ: käytä aina number-tyyppiä, ei string)
activityName
startTimeLocal      "2026-05-13T20:14:12"
distance            metreissä → jaa 1000:lla km:ksi
duration            sekunteissa → jaa 60:lla minuuteiksi
activityType.typeKey   esim. "trail_running", "running", "strength_training"
averageHR
maxHR
calories
trainingEffectLabel    "AEROBIC_BASE" / "TEMPO" / "VO2MAX" / "ANAEROBIC_CAPACITY" / "RECOVERY"
aerobicTrainingEffect
anaerobicTrainingEffect
directWorkoutRpe    (kokonaisluku tai null — Garminin oma RPE-arvo)
directWorkoutFeel   (numerokooodi tai null → muunna: 1=very_weak, 2=weak, 3=normal, 4=strong, 5=very_strong)
```

⚠️ **Nousudataa ei ole tässä kutsusta** — käytä `get_activity_splits` per aktiviteetti.

### `get_activity`
```
params: { activity_id: 12345678 }   // number, ei string
```
Yksittäisen aktiviteetin täydet tiedot. Käytä kun tarvitaan `directWorkoutRpe` / `directWorkoutFeel` tai muita kenttä joita `get_activities_by_date` ei palauta.

### `get_activity_splits` ⭐ nousun lähde
```
params: { activity_id: 12345678 }   // number
```
Palauttaa lap-tason datan. Summaa `elevation_gain_meters` kaikista lapeista → aktiviteetin kokonaisnousu.
Huom: `get_activities_by_date` ei sisällä nousujenmetrejä — `get_activity_splits` on ainoa luotettava lähde.

### `get_activity_typed_splits`
```
params: { activity_id: 12345678 }   // number
```
Erottaa intervallilenkin lämmitin / työosuus / jäähdyttely -osioihin. Käytä intervallien analysoinnissa — koko lenkin keskinopeus/keskeisyöke on harhaanjohtava kun se sisältää lämmittelyn ja jäähdyttelyn.

### `get_activity_split_summaries`
```
params: { activity_id: 12345678 }
```
Vaihtoehto `get_activity_typed_splits`:lle — antaa yhteenvedon split-tyypeistä. Käytä kun tarvitaan vain yhteenveto eikä jokainen yksittäinen intervalli.

---

## Domain 3: Training Load & Trends

### `get_training_load_trend`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Palauttaa kuormitustrendin useammalle päivälle — acute load, chronic load, load ratio. Käytä viikon tai kuukauden kuormituskuvan hakemiseen.

### `get_training_readiness` + `get_training_status`
Ks. Domain 1 yllä — molemmat sisältävät training load -tietoa.

---

## Domain 4: Harjoitusten luonti ja aikataulutus

### `upload_workout` / `create_walk_run_workout` / `create_strength_workout`
Harjoituksen luonti Garmin Connectiin. Käytä `upload_workout` kun harjoituksessa on useita vaiheita (lämmittely, toistot, jäähdyttely).

**⚠️ Kriittiset säännöt harjoituksia luodessa:**

1. **Käytä absoluuttisia bpm-arvoja** — ei Garminin zonenumeroita (`workoutTargetTypeId: 4`, kentät `targetValueOne` / `targetValueTwo`). Garminin sisäiset zonit ovat %HRmax-pohjaisia eivätkä vastaa LTHR-pohjaisia rajoja.

2. **Etuliite `[Coach]` aina** jotta coach-harjoitukset tunnistetaan. Esim. `[Coach] Mäkitoistot 5x4 min Z4`.

3. **Z1/Z1–Z2-juoksuissa yksi vaihe** — koko juoksu on helppo, ei erillistä lämmittelyä/jäähdyttelyä.

4. **Intervalliharjoituksissa (mäkitoistot, track)** lämmittely, palautukset ja jäähdyttely ovat lap-näppäinpohjaisia (`conditionType: PRESS_LAP`) — vain aktiiviset toistot ovat aikasidonnaisia. Syy: maastossa aikarajojen noudattaminen on käytännössä mahdotonta.

5. **Tempo/kynnysharjoituksissa** kolme aikasidonnaista vaihetta: lämmittely (10 min, no target) + pääosuus (HR target) + jäähdyttely (10 min, no target).

**HR-kohdearvot Tommin vyöhykkeille** (lue aina athlete-profile.md:stä, älä hardkoodaa):

| Zone | targetValueOne | targetValueTwo |
|------|---------------|----------------|
| Z1 | 100 | 124 |
| Z1–Z2 | 100 | 141 |
| Z3 | 142 | 148 |
| Z4 | 150 | 158 |
| Z5 | 160 | 175 |

**Sport type:**
- Maantiejuoksu: `sportTypeId: 1, sportTypeKey: "running"`
- Polkujuoksu: `sportTypeId: 1, sportTypeKey: "trail_running"`
- Voimaharjoittelu: `sportTypeId: 5, sportTypeKey: "strength_training"`

### `schedule_workout`
```
params: { workout_id: 12345, date: "YYYY-MM-DD" }
```
Aikatauluttaa harjoituksen Garmin-kalenteriin. Aina `upload_workout`:n jälkeen.
**Tee vasta hyväksynnän jälkeen** — älä aikatauluta ennen kuin käyttäjä on hyväksynyt suunnitelman.

### `get_scheduled_workouts`
```
params: { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }
```
Palauttaa kalenteriin aikataulutetut harjoitukset. Tarkista `completed`-kenttä ennen poistoa.

### `delete_workout`
```
params: { workout_id: 12345 }
```
⚠️ **Älä koskaan poista `completed = true` -harjoitusta.** Se on treenihistoriaa.

---

## Use-case cookbook

### Päivittäinen readiness-tarkistus
Tee rinnakkain (tämä järjestys seuraa daily-readiness skilliä):
1. `get_sleep_summary` (date: tänään) — HRV, unipisteet
2. `get_training_readiness` (date: tänään) — readiness-pisteet
3. `get_training_status` (date: tänään) — training status, ACWR
4. `get_body_battery` (start+end: tänään) — body battery
5. `get_rhr_day` (date: tänään) — leposyke

### Activity cache -päivitys
1. `get_activities_by_date` (start: viimeisin päivämäärä cachessa + 1, end: tänään)
2. Per uusi aktiviteetti: `get_activity_splits` (activity_id: number) → nousu
3. Tarvittaessa `get_activity` per aktiviteetti → RPE / feel

### Intervalli-analyysi (älä käytä koko lenkin keskilukuja)
1. `get_activity_typed_splits` → poimi vain "INTERVAL"-tyyppiset osuudet
2. Koko lenkin avg_hr / pace on harhaanjohtava — relevantti data on intervallivaihe itsessään

### Harjoituksen luonti ja aikataulutus (training-plan skillissä)
1. Rakenna workout-objekti (ks. Domain 4 säännöt)
2. `upload_workout` → saat `workout_id`
3. `schedule_workout` (workout_id, date)
4. Toista per sessio

### Vanhojen [Coach]-harjoitusten siivous ennen uutta suunnitelmaa
1. `get_scheduled_workouts` (koko uuden suunnitelman aikaväli)
2. Suodata: nimi alkaa `[Coach]` JA `completed = false`
3. `delete_workout` per poistuva harjoitus

---

## Tunnetut quirkit

| # | Ongelma | Ratkaisu |
|---|---------|----------|
| 1 | `activity_id` täytyy olla `number`, ei `string` | Muunna aina: `int(activity_id)` tai `Number(activityId)` |
| 2 | `get_sleep_data` palauttaa ~200 KB aikaseriadataa | Käytä aina `get_sleep_summary` (~350 B) |
| 3 | Garminin HR-zonit API:ssa käyttävät %HRmax-rajoja (88/106/123/141/157 bpm) | Käytä absoluuttisia bpm-arvoja athlete-profile.md:stä |
| 4 | `get_activity_hr_in_timezones` käyttää samoja %HRmax-rajoja | Laske oma jakauma LTHR-rajoilla `get_activity_splits`:n datasta |
| 5 | Nousudata puuttuu `get_activities_by_date`:sta | Hae aina `get_activity_splits` per aktiviteetti nousun laskemiseen |
| 6 | `training_balance_feedback: AEROBIC_HIGH_SHORTAGE` = Z3–Z4-vaje | Pitkä helppo lenkki ei korjaa tätä — tarvitaan tempo/kynnys/intervalliharjoitus |
| 7 | `RECOVERY` training status ≠ `DETRAINING` | Recovery = tarkoituksellinen palautuminen (ok). Detraining = kuorma laskenut liian alas (varoitus). |
| 8 | `vo2_max` vs `vo2_max_precise` | Käytä `vo2_max_precise` tarkempaan analyysiin. Mutta athlete-profile.md:n lab-confirmed arvo (44) yliajaa molemmat Garminin estimaatit. |

---

## Tulevaisuus: skriptispesifikaatio

*Täytetään vaihe 2:ssa, kun siirrytään MCP:stä suoraan API-kutsuihin.*

Garmin käyttää OAuth2-autentikointia (garth-kirjasto hoitaa token-hallinnan). Keskeisiä REST-endpointteja:
- Aktiviteetit: `GET /activitylist-service/activities/search/activities`
- Yksittäinen aktiviteetti: `GET /activity-service/activity/{activityId}`
- Splits: `GET /activity-service/activity/{activityId}/splits`
- Sleep: `GET /wellness-service/wellness/dailySleepData/{date}`
- HRV: `GET /hrv-service/hrv/{date}`
- Training readiness: `GET /metrics-service/metrics/trainingReadiness/{date}`
