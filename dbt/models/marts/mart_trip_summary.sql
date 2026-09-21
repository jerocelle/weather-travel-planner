with forecast as (

    select * from {{ ref('fct_trip_daily_forecast') }}

),

-- for each trip day, keep only the most recently fetched forecast
latest_per_day as (

    select
        *,
        row_number() over (
            partition by trip_id, forecast_date
            order by fetched_at desc
        ) as rn

    from forecast

),

deduped as (

    select * from latest_per_day where rn = 1

),

trips as (

    select * from {{ ref('dim_trips') }}

),

summary as (

    select
        d.trip_id,
        t.city,
        t.country,
        t.start_date,
        t.end_date,
        t.trip_length_days,
        count(*) as forecast_days_available,
        round(avg(d.temp_max_c), 1) as avg_temp_max_c,
        round(avg(d.temp_min_c), 1) as avg_temp_min_c,
        round(avg(d.precipitation_probability_pct), 1) as avg_precipitation_probability_pct,
        round(max(d.precipitation_probability_pct), 1) as max_precipitation_probability_pct,
        round(sum(d.precipitation_mm), 1) as total_precipitation_mm,
        round(max(d.windspeed_max_kmh), 1) as max_windspeed_kmh,
        avg(d.precipitation_probability_pct) >= 40 as pack_an_umbrella

    from deduped d
    inner join trips t on d.trip_id = t.trip_id
    group by 1, 2, 3, 4, 5, 6

)

select * from summary
