"""
oura-fetch.py — Hakee päivän Oura-datan suoraan Oura API v2:sta.

Korvaa Docker-pohjaisen Oura MCP -serverin. Tallentaa tuloksen
oura-today.json tiedostoon tässä kansiossa.

Käyttö:
  python oura-fetch.py              # hakee tämän päivän datan
  python oura-fetch.py 2026-05-15   # hakee tietyn päivän datan

Token: luetaan ~/mcps/oura.env tiedostosta (suositeltu, toimii Mac + Windows)
       Fallback: oura.env tässä kansiossa (workspace-juuri)
       Muoto: OURA_API_TOKEN=token_tähän
"""

import json
import sys
from datetime import date, datetime
from pathlib import Path

import requests

# --- Polut ---
SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "oura-today.json"

# Token-tiedosto: ~/mcps/oura.env (suositeltu) tai ./oura.env (fallback)
_mcps_token = Path.home() / "mcps" / "oura.env"
_local_token = SCRIPT_DIR / "oura.env"
TOKEN_FILE = _mcps_token if _mcps_token.exists() else _local_token

# --- Oura API ---
API_BASE = "https://api.ouraring.com/v2/usercollection"


def load_token() -> str:
    """Lukee OURA_API_TOKEN oura.env tiedostosta."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"Token-tiedostoa ei löydy. Luo jompikumpi:\n"
            f"  {_mcps_token}  (suositeltu)\n"
            f"  {_local_token}  (fallback)\n"
            "Lisää tiedostoon rivi: OURA_API_TOKEN=token_tähän"
        )
    for line in TOKEN_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("OURA_API_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if token:
                return token
    raise ValueError(f"OURA_API_TOKEN ei löydy tiedostosta {TOKEN_FILE}")


def fetch(endpoint: str, token: str, params: dict) -> dict:
    """Tekee yhden GET-pyynnön Oura API:hin."""
    url = f"{API_BASE}/{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def extract_readiness(data: dict, target_date: str) -> dict | None:
    """Poimii readiness-datan päivälle target_date."""
    items = data.get("data", [])
    for item in items:
        if item.get("day") == target_date:
            return {
                "score": item.get("score"),
                "temperature_deviation": item.get("temperature_deviation"),
                "temperature_trend_deviation": item.get("temperature_trend_deviation"),
                "contributors": item.get("contributors", {}),
            }
    return None


def extract_sleep(data: dict, target_date: str) -> dict | None:
    """Poimii sleep-datan päivälle target_date."""
    items = data.get("data", [])
    for item in items:
        if item.get("day") == target_date:
            return {
                "score": item.get("score"),
                "contributors": item.get("contributors", {}),
            }
    return None


def main():
    # Päivämäärä: argumentista tai tänään
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        try:
            date.fromisoformat(target_date)
        except ValueError:
            print(f"Virheellinen päivämäärä: {target_date}. Käytä muotoa YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = date.today().isoformat()

    print(f"Haetaan Oura-data päivälle {target_date}...")

    # Token
    try:
        token = load_token()
    except (FileNotFoundError, ValueError) as e:
        print(f"Virhe: {e}")
        sys.exit(1)

    params = {"start_date": target_date, "end_date": target_date}

    # Hae molemmat endpointit
    errors = []

    try:
        readiness_raw = fetch("daily_readiness", token, params)
        readiness = extract_readiness(readiness_raw, target_date)
    except requests.HTTPError as e:
        print(f"Readiness-haku epäonnistui: {e}")
        readiness = None
        errors.append(str(e))
    except requests.RequestException as e:
        print(f"Verkkovirhe (readiness): {e}")
        readiness = None
        errors.append(str(e))

    try:
        sleep_raw = fetch("daily_sleep", token, params)
        sleep = extract_sleep(sleep_raw, target_date)
    except requests.HTTPError as e:
        print(f"Sleep-haku epäonnistui: {e}")
        sleep = None
        errors.append(str(e))
    except requests.RequestException as e:
        print(f"Verkkovirhe (sleep): {e}")
        sleep = None
        errors.append(str(e))

    # Rakenna output
    output = {
        "date": target_date,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "readiness": readiness,
        "sleep": sleep,
    }

    if errors:
        output["errors"] = errors

    # Tallenna
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Tallennettu: {OUTPUT_FILE}")

    # Yhteenveto
    if readiness:
        score = readiness.get("score", "?")
        temp = readiness.get("temperature_deviation")
        temp_str = f"{temp:+.2f}°C" if temp is not None else "ei saatavilla"
        print(f"  Readiness: {score}/100 | Lämpö: {temp_str}")
    else:
        print(f"  Readiness: ei dataa päivälle {target_date} (rengas ei ehkä synkronoinut vielä)")

    if sleep:
        score = sleep.get("score", "?")
        print(f"  Sleep:     {score}/100")
    else:
        print(f"  Sleep: ei dataa päivälle {target_date}")


if __name__ == "__main__":
    main()
