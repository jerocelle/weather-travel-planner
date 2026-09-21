with trips as (

    select * from {{ ref('trips') }}

),

renamed as (

    select
        trip_id,
        city,
        country,
        cast(lat as double) as lat,
        cast(lon as double) as lon,
        cast(start_date as date) as start_date,
        cast(end_date as date) as end_date,
        date_diff('day', cast(start_date as date), cast(end_date as date)) + 1 as trip_length_days

    from trips

)

select * from renamed
