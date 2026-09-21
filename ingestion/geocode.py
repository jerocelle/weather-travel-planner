"""Look up latitude/longitude for a city via the Open-Meteo Geocoding API.

trips.yaml already carries hand-checked coordinates, so this module is a
standalone utility for adding new trips rather than something the daily
pipeline depends on.
"""
from __future__ import annotations

import argparse
from typing import Optional

import requests

from ingestion.common import retry_with_backoff

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


class GeocodeError(Exception):
    """Raised when a city cannot be resolved to coordinates."""


@retry_with_backoff(max_attempts=3, retriable_exceptions=(requests.RequestException,))
def _get(params: dict) -> dict:
    response = requests.get(GEOCODING_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def geocode_city(city: str, country: Optional[str] = None) -> dict:
    """Resolve a city name to coordinates.

    Returns a dict with keys: name, country, lat, lon.
    Raises GeocodeError if no match is found.
    """
    payload = _get({"name": city, "count": 10, "language": "en", "format": "json"})
    results = payload.get("results") or []

    if country:
        results = [r for r in results if r.get("country", "").lower() == country.lower()] or results

    if not results:
        raise GeocodeError(f"No geocoding match for city={city!r} country={country!r}")

    best = results[0]
    return {
        "name": best["name"],
        "country": best.get("country", ""),
        "lat": best["latitude"],
        "lon": best["longitude"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode a city via Open-Meteo.")
    parser.add_argument("city", help="City name, e.g. 'Taipei'")
    parser.add_argument("--country", help="Country name to disambiguate matches", default=None)
    args = parser.parse_args()

    result = geocode_city(args.city, args.country)
    print(f"{result['name']}, {result['country']}: lat={result['lat']}, lon={result['lon']}")


if __name__ == "__main__":
    main()
