"""Daily pipeline: fetch forecasts -> load to warehouse -> dbt run -> dbt test.

Posts a Slack alert on any task failure if SLACK_WEBHOOK_URL is set.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.fetch_forecast import run as fetch_forecast_run  # noqa: E402
from ingestion.load_to_warehouse import run as load_to_warehouse_run  # noqa: E402

DBT_PROJECT_DIR = str(PROJECT_ROOT / "dbt")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


def notify_failure(context: dict) -> None:
    if not SLACK_WEBHOOK_URL:
        return

    import requests

    task_id = context["task_instance"].task_id
    dag_id = context["task_instance"].dag_id
    run_id = context["run_id"]
    message = f":x: `{dag_id}.{task_id}` failed (run_id={run_id})"
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    except requests.RequestException:
        pass  # an alert failure shouldn't compound the original task failure


default_args = {
    "owner": "weather-travel-planner",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="weather_pipeline",
    description="Fetch trip-city forecasts, load to warehouse, run dbt.",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["weather-travel-planner"],
) as dag:

    fetch_forecast = PythonOperator(
        task_id="fetch_forecast",
        python_callable=fetch_forecast_run,
        # fetch_forecast_run returns a list[Path], which isn't JSON-serializable
        # for XCom, and load_to_warehouse doesn't need it anyway (it globs the
        # raw dir itself).
        do_xcom_push=False,
    )

    load_to_warehouse = PythonOperator(
        task_id="load_to_warehouse",
        python_callable=load_to_warehouse_run,
        do_xcom_push=False,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --profiles-dir {DBT_PROJECT_DIR}",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test --profiles-dir {DBT_PROJECT_DIR}",
    )

    fetch_forecast >> load_to_warehouse >> dbt_run >> dbt_test
