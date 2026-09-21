"""Fetch daily weather forecasts for each trip from the Open-Meteo API.

Single responsibility: call the API and land the raw JSON response to disk.
Parsing into the warehouse is handled separately by load_to_warehouse.py.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

from ingestion.common import DEFAULT_CONFIG_PATH, DEFAULT_RAW_DIR, Trip, load_trips, retry_with_backoff

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_HORIZON_DAYS = 15  # Open-Meteo's free forecast API reliably covers ~16 days ahead
DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "windspeed_10m_max",
    "weathercode",
]


class ForecastFetchError(Exception):
    """Raised when the Open-Meteo API call fails after retries are exhausted."""


def clip_to_forecast_horizon(trip: Trip, today: date) -> Optional[tuple[date, date]]:
    """Clip a trip's date window to what the forecast API can actually return.

    Returns None if the trip window doesn't overlap the forecast horizon yet
    (too far in the future) or anymore (already in the past).
    """
    horizon_end = today + timedelta(days=FORECAST_HORIZON_DAYS)
    trip_start = date.fromisoformat(trip.start_date)
    trip_end = date.fromisoformat(trip.end_date)

    window_start = max(trip_start, today)
    window_end = min(trip_end, horizon_end)

    if window_start > window_end:
        return None
    return window_start, window_end


@retry_with_backoff(max_attempts=4, retriable_exceptions=(requests.RequestException,))
def _get(params: dict) -> dict:
    response = requests.get(FORECAST_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_forecast_for_trip(trip: Trip, today: Optional[date] = None) -> Optional[dict]:
    """Fetch the raw forecast payload for a single trip's clipped date window.

    Returns None (fetching nothing) if the trip window doesn't overlap the
    forecast horizon yet.
    """
    today = today or date.today()
    window = clip_to_forecast_horizon(trip, today)
    if window is None:
        return None
    window_start, window_end = window

    params = {
        "latitude": trip.lat,
        "longitude": trip.lon,
        "start_date": window_start.isoformat(),
        "end_date": window_end.isoformat(),
        "daily": ",".join(DAILY_VARIABLES),
        "temperature_unit": "celsius",
        "windspeed_unit": "kmh",
        "precipitation_unit": "mm",
        "timezone": "auto",
    }

    try:
        return _get(params)
    except requests.RequestException as exc:
        raise ForecastFetchError(f"Failed to fetch forecast for {trip.trip_id}: {exc}") from exc


def land_raw_forecast(trip: Trip, payload: dict, fetched_at: datetime, raw_dir: Path) -> Path:
    """Write the raw API response to disk alongside trip metadata."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{trip.trip_id}__{fetched_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path = raw_dir / filename

    record = {
        "trip_id": trip.trip_id,
        "city": trip.city,
        "country": trip.country,
        "lat": trip.lat,
        "lon": trip.lon,
        "fetched_at": fetched_at.isoformat(),
        "response": payload,
    }
    out_path.write_text(json.dumps(record, indent=2))
    return out_path


def run(config_path: Path = DEFAULT_CONFIG_PATH, raw_dir: Path = DEFAULT_RAW_DIR) -> list[Path]:
    trips = load_trips(config_path)
    fetched_at = datetime.now(timezone.utc)
    today = fetched_at.date()

    written_files: list[Path] = []
    for trip in trips:
        payload = fetch_forecast_for_trip(trip, today=today)
        if payload is None:
            print(f"[skip] {trip.trip_id}: outside forecast horizon (today={today})")
            continue
        path = land_raw_forecast(trip, payload, fetched_at, raw_dir)
        written_files.append(path)
        print(f"[ok] {trip.trip_id}: wrote {path.name}")

    return written_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily forecasts for all configured trips.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args()

    run(config_path=args.config, raw_dir=args.raw_dir)


if __name__ == "__main__":
    main()
