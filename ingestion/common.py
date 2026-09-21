"""Shared helpers for the ingestion layer: config loading, paths, retry/backoff."""
from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "ingestion" / "config" / "trips.yaml"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "forecast"
DEFAULT_DUCKDB_PATH = PROJECT_ROOT / "data" / "warehouse" / "warehouse.duckdb"


@dataclass(frozen=True)
class Trip:
    trip_id: str
    city: str
    country: str
    lat: float
    lon: float
    start_date: str
    end_date: str


def load_trips(config_path: Path = DEFAULT_CONFIG_PATH) -> list[Trip]:
    """Load the hand-maintained trip list from YAML."""
    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    trips = raw.get("trips", []) if raw else []
    return [Trip(**trip) for trip in trips]


def retry_with_backoff(
    max_attempts: int = 4,
    base_delay_seconds: float = 1.0,
    retriable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator that retries a function with exponential backoff.

    Attempt delays: base_delay, base_delay*2, base_delay*4, ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retriable_exceptions as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        break
                    delay = base_delay_seconds * (2 ** (attempt - 1))
                    time.sleep(delay)
            raise last_exception

        return wrapper

    return decorator
