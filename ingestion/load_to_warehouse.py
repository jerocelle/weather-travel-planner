"""Parse landed raw forecast JSON files and load them into the DuckDB warehouse.

Single responsibility: raw JSON -> raw.forecast_daily rows. No API calls here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

from ingestion.common import DEFAULT_DUCKDB_PATH, DEFAULT_RAW_DIR

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw.forecast_daily (
    trip_id VARCHAR,
    city VARCHAR,
    country VARCHAR,
    lat DOUBLE,
    lon DOUBLE,
    forecast_date DATE,
    fetched_at TIMESTAMP,
    temperature_2m_max DOUBLE,
    temperature_2m_min DOUBLE,
    precipitation_sum DOUBLE,
    precipitation_probability_max DOUBLE,
    windspeed_10m_max DOUBLE,
    weathercode INTEGER
);
"""


def parse_raw_file(path: Path) -> list[dict]:
    """Flatten one landed JSON file (trip metadata + Open-Meteo response) into rows."""
    record = json.loads(path.read_text())
    daily = record["response"]["daily"]

    rows = []
    for i, forecast_date in enumerate(daily["time"]):
        rows.append(
            {
                "trip_id": record["trip_id"],
                "city": record["city"],
                "country": record["country"],
                "lat": record["lat"],
                "lon": record["lon"],
                "forecast_date": forecast_date,
                "fetched_at": record["fetched_at"],
                "temperature_2m_max": daily["temperature_2m_max"][i],
                "temperature_2m_min": daily["temperature_2m_min"][i],
                "precipitation_sum": daily["precipitation_sum"][i],
                "precipitation_probability_max": daily["precipitation_probability_max"][i],
                "windspeed_10m_max": daily["windspeed_10m_max"][i],
                "weathercode": daily["weathercode"][i],
            }
        )
    return rows


def load_rows(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> int:
    """Append parsed rows to raw.forecast_daily, creating the schema/table if needed."""
    if not rows:
        return 0

    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    con.execute(CREATE_TABLE_SQL)
    con.executemany(
        """
        INSERT INTO raw.forecast_daily
        (trip_id, city, country, lat, lon, forecast_date, fetched_at,
         temperature_2m_max, temperature_2m_min, precipitation_sum,
         precipitation_probability_max, windspeed_10m_max, weathercode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["trip_id"], r["city"], r["country"], r["lat"], r["lon"],
                r["forecast_date"], r["fetched_at"], r["temperature_2m_max"],
                r["temperature_2m_min"], r["precipitation_sum"],
                r["precipitation_probability_max"], r["windspeed_10m_max"], r["weathercode"],
            )
            for r in rows
        ],
    )
    return len(rows)


def run(raw_dir: Path = DEFAULT_RAW_DIR, db_path: Path = DEFAULT_DUCKDB_PATH) -> int:
    """Load every unprocessed raw JSON file into DuckDB, then archive it."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    raw_files = sorted(raw_dir.glob("*.json"))

    if not raw_files:
        print("[load] no raw files to load")
        return 0

    processed_dir = raw_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    con = duckdb.connect(str(db_path))
    total_rows = 0
    try:
        for path in raw_files:
            rows = parse_raw_file(path)
            total_rows += load_rows(con, rows)
            path.rename(processed_dir / path.name)
            print(f"[load] {path.name}: {len(rows)} rows")
    finally:
        con.close()

    print(f"[load] done: {total_rows} rows from {len(raw_files)} files")
    return total_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Load landed raw forecast JSON into DuckDB.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DUCKDB_PATH)
    args = parser.parse_args()

    run(raw_dir=args.raw_dir, db_path=args.db)


if __name__ == "__main__":
    main()
