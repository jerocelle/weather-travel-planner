from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
import requests

from ingestion.common import Trip
from ingestion.fetch_forecast import (
    ForecastFetchError,
    clip_to_forecast_horizon,
    fetch_forecast_for_trip,
    land_raw_forecast,
)

TRIP = Trip(
    trip_id="taipei_2026_11",
    city="Taipei",
    country="Taiwan",
    lat=25.0330,
    lon=121.5654,
    start_date="2026-11-14",
    end_date="2026-11-19",
)

SAMPLE_RESPONSE = {
    "daily": {
        "time": ["2026-11-14", "2026-11-15"],
        "temperature_2m_max": [28.1, 27.6],
        "temperature_2m_min": [22.0, 21.8],
        "precipitation_sum": [0.0, 4.2],
        "precipitation_probability_max": [10, 60],
        "windspeed_10m_max": [12.3, 18.9],
        "weathercode": [1, 61],
    }
}


def test_clip_to_forecast_horizon_within_window():
    today = date(2026, 11, 10)
    window = clip_to_forecast_horizon(TRIP, today)
    assert window == (date(2026, 11, 14), date(2026, 11, 19))


def test_clip_to_forecast_horizon_too_far_in_future_returns_none():
    today = date(2026, 9, 21)  # trip starts ~54 days out, horizon is 15 days
    assert clip_to_forecast_horizon(TRIP, today) is None


def test_clip_to_forecast_horizon_trip_already_over_returns_none():
    today = date(2026, 12, 1)
    assert clip_to_forecast_horizon(TRIP, today) is None


def test_clip_to_forecast_horizon_clips_end_date_to_horizon():
    today = date(2026, 11, 16)
    window = clip_to_forecast_horizon(TRIP, today)
    assert window == (date(2026, 11, 16), date(2026, 11, 19))


def test_fetch_forecast_for_trip_skips_when_outside_horizon(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("should not call the API when outside the forecast horizon")

    monkeypatch.setattr(requests, "get", fail_if_called)
    result = fetch_forecast_for_trip(TRIP, today=date(2026, 9, 21))
    assert result is None


def test_fetch_forecast_for_trip_returns_payload(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return SAMPLE_RESPONSE

    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())
    result = fetch_forecast_for_trip(TRIP, today=date(2026, 11, 10))
    assert result == SAMPLE_RESPONSE


def test_fetch_forecast_for_trip_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return SAMPLE_RESPONSE

    def flaky_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.ConnectionError("temporary network issue")
        return FakeResponse()

    monkeypatch.setattr(requests, "get", flaky_get)
    monkeypatch.setattr("time.sleep", lambda *_: None)  # skip real backoff delay in tests

    result = fetch_forecast_for_trip(TRIP, today=date(2026, 11, 10))
    assert result == SAMPLE_RESPONSE
    assert calls["count"] == 3


def test_fetch_forecast_for_trip_raises_after_exhausting_retries(monkeypatch):
    def always_fails(*args, **kwargs):
        raise requests.ConnectionError("network is down")

    monkeypatch.setattr(requests, "get", always_fails)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    with pytest.raises(ForecastFetchError):
        fetch_forecast_for_trip(TRIP, today=date(2026, 11, 10))


def test_land_raw_forecast_writes_expected_structure(tmp_path):
    fetched_at = datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)
    out_path = land_raw_forecast(TRIP, SAMPLE_RESPONSE, fetched_at, tmp_path)

    assert out_path.exists()
    record = json.loads(out_path.read_text())
    assert record["trip_id"] == "taipei_2026_11"
    assert record["response"] == SAMPLE_RESPONSE
    assert record["fetched_at"] == fetched_at.isoformat()
