from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from stock_pipeline.extract.polygon import AggregateBar


def bars_to_dataframe(ticker: str, bars: list[AggregateBar]) -> pd.DataFrame:
    """Normalize Polygon aggregate bars into a canonical OHLCV schema."""
    if not bars:
        return pd.DataFrame(
            columns=[
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
        )

    rows = []
    ingested_at = datetime.now(tz=UTC).isoformat()
    for bar in bars:
        rows.append(
            {
                "ticker": ticker.upper(),
                "date": datetime.fromtimestamp(bar.timestamp_ms / 1000, tz=UTC).date(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "vwap": bar.vwap,
                "transactions": bar.transactions,
                "source": "polygon.io",
                "ingested_at": ingested_at,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("date").drop_duplicates(subset=["ticker", "date"], keep="last")
    return df.reset_index(drop=True)
