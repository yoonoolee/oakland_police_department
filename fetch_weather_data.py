"""
Fetches hourly historical weather for Oakland from Open-Meteo's free archive
API (no key required) and caches it locally, so we don't hit the API again
for every modeling iteration.

Covers 2024-01-01 through the end of the harmonized calls data (2026-06-30),
matching the 2024+ training window decision for the demand model.
"""

import urllib.request
import urllib.parse
import json
import pandas as pd

LAT, LON = 37.8044, -122.2712  # Oakland, CA
START_DATE = "2024-01-01"
END_DATE = "2026-06-30"
OUTPUT = "../Data/Our Data/weather_oakland_2024_2026.parquet"

HOURLY_VARS = ["temperature_2m", "precipitation"]


def main():
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": ",".join(HOURLY_VARS),
        "timezone": "America/Los_Angeles",
    }
    url = "https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(params)
    print("Fetching:", url)
    with urllib.request.urlopen(url, timeout=60) as resp:
        payload = json.load(resp)

    hourly = payload["hourly"]
    df = pd.DataFrame({
        "hour": pd.to_datetime(hourly["time"]),
        "temp_c": hourly["temperature_2m"],
        "precip_mm": hourly["precipitation"],
    })
    print(f"Fetched {len(df):,} hourly rows, {df['hour'].min()} to {df['hour'].max()}")
    print(df.describe().round(2))

    df.to_parquet(OUTPUT, index=False)
    print(f"\nSaved {OUTPUT}")


if __name__ == "__main__":
    main()
