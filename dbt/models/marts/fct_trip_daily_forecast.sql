with forecast as (

    select * from {{ ref('stg_forecast_daily') }}

),

trips as (

    select * from {{ ref('dim_trips') }}

),

joined as (

    select
        f.trip_id,
        t.city,
        t.country,
        f.forecast_date,
        f.fetched_at,
        f.days_out,
        f.temp_max_c,
        f.temp_min_c,
        f.precipitation_mm,
        f.precipitation_probability_pct,
        f.windspeed_max_kmh,
        f.weather_code

    from forecast f
    inner join trips t
        on f.trip_id = t.trip_id
    where f.forecast_date between t.start_date and t.end_date

)

select * from joined
