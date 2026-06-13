from datetime import UTC, datetime

from stock_pipeline.extract.polygon import AggregateBar
from stock_pipeline.transform.normalize import bars_to_dataframe


def test_bars_to_dataframe_maps_fields():
    bars = [
        AggregateBar(
            timestamp_ms=1704067200000,
            open=150.0,
            high=152.0,
            low=149.5,
            close=151.0,
            volume=1_000_000.0,
            vwap=150.25,
            transactions=50_000,
        )
    ]

    df = bars_to_dataframe("aapl", bars)

    assert len(df) == 1
    assert df.loc[0, "ticker"] == "AAPL"
    assert df.loc[0, "date"] == datetime(2024, 1, 1, tzinfo=UTC).date()
    assert df.loc[0, "source"] == "polygon.io"
    assert df.loc[0, "open"] == 150.0


def test_bars_to_dataframe_empty():
    df = bars_to_dataframe("AAPL", [])
    assert df.empty
    assert list(df.columns) == [
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transactions",
        "source",
        "ingested_at",
    ]


def test_bars_to_dataframe_deduplicates_dates():
    bars = [
        AggregateBar(1704067200000, 150.0, 152.0, 149.5, 151.0, 1_000_000.0),
        AggregateBar(1704067200000, 150.5, 152.5, 149.0, 151.5, 1_050_000.0),
    ]

    df = bars_to_dataframe("AAPL", bars)
    assert len(df) == 1
    assert df.loc[0, "close"] == 151.5
