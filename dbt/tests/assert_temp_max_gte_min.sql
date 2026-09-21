-- Custom test: a day's max temperature should never be below its min temperature.
-- Fails (returns rows) if the API ever returns an inconsistent reading.

select
    trip_id,
    forecast_date,
    fetched_at,
    temp_max_c,
    temp_min_c
from {{ ref('stg_forecast_daily') }}
where temp_max_c < temp_min_c
