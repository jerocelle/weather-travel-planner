from __future__ import annotations

import json
from datetime import date

import duckdb

from ingestion.load_to_warehouse import load_rows, parse_raw_file, run

RAW_RECORD = {
    "trip_id": "cebu_2026_11",
    "city": "Cebu",
    "country": "Philippines",
    "lat": 10.3157,
    "lon": 123.8854,
    "fetched_at": "2026-11-20T06:00:00+00:00",
    "response": {
        "daily": {
            "time": ["2026-11-23", "2026-11-24"],
            "temperature_2m_max": [30.5, 30.1],
            "temperature_2m_min": [24.2, 24.0],
            "precipitation_sum": [1.0, 0.0],
            "precipitation_probability_max": [30, 5],
            "windspeed_10m_max": [10.0, 9.5],
            "weathercode": [3, 0],
        }
    },
}


def test_parse_raw_file_flattens_one_row_per_day(tmp_path):
    path = tmp_path / "cebu.json"
    path.write_text(json.dumps(RAW_RECORD))

    rows = parse_raw_file(path)

    assert len(rows) == 2
    assert rows[0]["trip_id"] == "cebu_2026_11"
    assert rows[0]["forecast_date"] == "2026-11-23"
    assert rows[0]["temperature_2m_max"] == 30.5
    assert rows[1]["forecast_date"] == "2026-11-24"


def test_load_rows_inserts_into_duckdb():
    con = duckdb.connect(":memory:")
    rows = [
        {
            "trip_id": "cebu_2026_11", "city": "Cebu", "country": "Philippines",
            "lat": 10.3157, "lon": 123.8854, "forecast_date": "2026-11-23",
            "fetched_at": "2026-11-20T06:00:00+00:00", "temperature_2m_max": 30.5,
            "temperature_2m_min": 24.2, "precipitation_sum": 1.0,
            "precipitation_probability_max": 30, "windspeed_10m_max": 10.0, "weathercode": 3,
        }
    ]

    inserted = load_rows(con, rows)

    assert inserted == 1
    result = con.execute("SELECT trip_id, forecast_date FROM raw.forecast_daily").fetchall()
    assert result == [("cebu_2026_11", date(2026, 11, 23))]


def test_run_loads_and_archives_raw_files(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "cebu_2026_11__20261120T060000Z.json").write_text(json.dumps(RAW_RECORD))

    db_path = tmp_path / "warehouse.duckdb"
    total_rows = run(raw_dir=raw_dir, db_path=db_path)

    assert total_rows == 2
    assert not list(raw_dir.glob("*.json"))  # moved into processed/
    assert (raw_dir / "processed" / "cebu_2026_11__20261120T060000Z.json").exists()

    con = duckdb.connect(str(db_path))
    count = con.execute("SELECT count(*) FROM raw.forecast_daily").fetchone()[0]
    con.close()
    assert count == 2
