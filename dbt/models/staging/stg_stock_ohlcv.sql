with source as (
    select * from {{ source('raw_stock', 'stock_ohlcv') }}
)

select
    upper(TICKER) as ticker,
    DATE as date,
    OPEN as open,
    HIGH as high,
    LOW as low,
    CLOSE as close,
    VOLUME as volume,
    VWAP as vwap,
    TRANSACTIONS as transactions,
    SOURCE as data_source,
    INGESTED_AT as ingested_at
from source
