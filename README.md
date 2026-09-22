# Weather Travel Planner

A small analytics-engineering pipeline that pulls daily weather forecasts for
upcoming trips (Open-Meteo API), lands and models the data with dbt, tracks
how forecasts drift as trips approach (dbt snapshots), and orchestrates the
whole thing with Airflow. Runs entirely free and local (DuckDB + Docker
Compose), with a config-only path to GCP (BigQuery + Composer/GCE).

## Current trips (`ingestion/config/trips.yaml`)

| Trip | City | Country | Dates |
|---|---|---|---|
| taipei_2026_09 | Taipei | Taiwan | 2026-09-19 – 2026-09-24 |
| new_taipei_2026_09 | New Taipei | Taiwan | 2026-09-19 – 2026-09-24 |
| cavite_2026_09 | Cavite | Philippines | 2026-09-24 – 2026-09-28 |
| cebu_2026_09 | Cebu | Philippines | 2026-09-28 – 2026-10-09 |

Add trips by editing `ingestion/config/trips.yaml` **and** `dbt/seeds/trips.csv`
(kept in sync by hand — `ingestion/geocode.py <city> --country <country>` will
look up lat/lon for a new one).

## How it fits together

```
ingestion/fetch_forecast.py   -> lands raw Open-Meteo JSON to data/raw/forecast/
ingestion/load_to_warehouse.py -> parses raw JSON into raw.forecast_daily (DuckDB)
dbt run                        -> stg_forecast_daily -> dim_trips / fct_trip_daily_forecast -> mart_trip_summary
dbt snapshot                   -> forecast_snapshot (type-2 history of forecast drift)
dbt test                       -> schema + custom tests, source freshness
```

The forecast API only covers ~15 days ahead, so `fetch_forecast.py` clips each
trip's date window to what's actually fetchable "today" and skips trips
outside that horizon — it's meant to run daily via Airflow so the window
slides forward automatically as each trip approaches.

## Run it locally (no Docker)

Needs **Python 3.11 or 3.12** — dbt-core's dependency stack (as of dbt-core
1.8.x) doesn't yet support 3.13+. If your default `python3` is newer, use
[uv](https://docs.astral.sh/uv/) to grab an isolated 3.11 without touching
your system Python: `uv venv --python 3.11 .venv`.

```bash
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv --python 3.11 .venv
pip install -r requirements.txt                       # or: uv pip install -r requirements.txt

# from the project root:
python -m ingestion.fetch_forecast
python -m ingestion.load_to_warehouse

cd dbt
dbt seed
dbt run
dbt snapshot
dbt test
dbt docs generate && dbt docs serve
```

Run the pipeline daily (or at least until trip dates fall inside the 15-day
forecast horizon) to build up snapshot history worth analyzing.

## Tests

```bash
pytest ingestion/tests -v
```

Tests mock all HTTP calls — no network or API key needed.

## Run it with Airflow (Docker Compose)

```bash
cp .env.example .env   # set AIRFLOW_UID (Linux: `id -u`), optionally SLACK_WEBHOOK_URL
docker compose up airflow-init
docker compose up
```

Airflow UI: http://localhost:8080 (default admin/admin, from `.env`).
The `weather_pipeline` DAG runs `fetch_forecast -> load_to_warehouse -> dbt run -> dbt test` daily.

## Moving to GCP

The dbt models never reference the warehouse directly (`source()`/`ref()`
only), so moving to GCP is a config change, not a rewrite:

1. Point ingestion's raw landing at a GCS bucket instead of local disk, and
   load `raw.forecast_daily` into BigQuery instead of DuckDB.
2. Fill in `GCP_PROJECT_ID` / `GCP_KEYFILE_PATH` in `.env` and run
   `dbt run --target prod` (see `dbt/profiles.yml`).
3. Run Airflow either on Cloud Composer (managed, has a real cost) or as the
   same Docker Compose stack on a small GCE VM (cheaper).

## dbt Developer-path concepts demonstrated

- Sources with freshness checks (`dbt/models/staging/_sources.yml`)
- Staging (views) vs marts (tables) layering
- Snapshots for type-2 drift tracking (`dbt/snapshots/forecast_snapshot.sql`)
- Schema tests: `not_null`, `unique`, `accepted_values`, `relationships`
- A custom singular test (`dbt/tests/assert_temp_max_gte_min.sql`)
- An exposure documenting a downstream dashboard consumer
