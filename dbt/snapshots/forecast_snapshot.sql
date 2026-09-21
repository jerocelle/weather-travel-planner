{% snapshot forecast_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key="trip_id || '-' || forecast_date",
        strategy='timestamp',
        updated_at='fetched_at',
    )
}}

-- Type-2 tracking of how the forecast for a given trip day changes as fetch
-- runs accumulate. Answers: how much does a 7-day-out forecast drift by the
-- time the trip actually arrives?
select
    trip_id,
    city,
    country,
    forecast_date,
    fetched_at,
    days_out,
    temp_max_c,
    temp_min_c,
    precipitation_mm,
    precipitation_probability_pct,
    windspeed_max_kmh,
    weather_code
from {{ ref('stg_forecast_daily') }}

{% endsnapshot %}
