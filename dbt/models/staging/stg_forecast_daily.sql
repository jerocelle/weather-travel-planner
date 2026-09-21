with source as (

    select * from {{ source('raw', 'forecast_daily') }}

),

renamed as (

    select
        trip_id,
        city,
        country,
        cast(lat as double) as lat,
        cast(lon as double) as lon,
        cast(forecast_date as date) as forecast_date,
        cast(fetched_at as timestamp) as fetched_at,
        cast(temperature_2m_max as double) as temp_max_c,
        cast(temperature_2m_min as double) as temp_min_c,
        cast(precipitation_sum as double) as precipitation_mm,
        cast(precipitation_probability_max as double) as precipitation_probability_pct,
        cast(windspeed_10m_max as double) as windspeed_max_kmh,
        cast(weathercode as integer) as weather_code,
        -- how many days before the forecast_date this row was fetched;
        -- 0 = fetched the day of, higher = fetched further out
        date_diff('day', cast(fetched_at as date), cast(forecast_date as date)) as days_out

    from source

)

select * from renamed
