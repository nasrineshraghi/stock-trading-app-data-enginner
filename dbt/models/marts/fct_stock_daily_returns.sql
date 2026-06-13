with daily as (
    select * from {{ ref('stg_stock_ohlcv') }}
),

with_previous_close as (
    select
        ticker,
        date,
        open,
        high,
        low,
        close,
        volume,
        vwap,
        transactions,
        data_source,
        ingested_at,
        lag(close) over (
            partition by ticker
            order by date
        ) as prev_close
    from daily
)

select
    ticker,
    date,
    open,
    high,
    low,
    close,
    volume,
    vwap,
    transactions,
    data_source,
    ingested_at,
    case
        when prev_close is null or prev_close = 0 then null
        else (close - prev_close) / prev_close * 100
    end as daily_return_pct
from with_previous_close
