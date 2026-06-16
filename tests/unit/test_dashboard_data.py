"""Tests for dashboard data loading helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from stock_pipeline.config import Settings
from stock_pipeline.dashboard.data import (
    add_daily_returns,
    filter_tickers,
    list_tickers,
    load_from_processed_csv,
)


@pytest.fixture
def settings_with_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    processed = tmp_path / "processed"
    processed.mkdir()
    frame = pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL", "MSFT"],
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-02"]),
            "open": [150.0, 151.0, 400.0],
            "high": [152.0, 153.0, 405.0],
            "low": [149.0, 150.0, 398.0],
            "close": [151.0, 152.0, 402.0],
            "volume": [1_000_000.0, 1_100_000.0, 900_000.0],
            "vwap": [150.5, 151.5, 401.0],
            "transactions": [1000, 1100, 900],
            "source": ["polygon.io", "polygon.io", "polygon.io"],
            "ingested_at": ["2024-06-01T00:00:00+00:00"] * 3,
        }
    )
    frame.to_csv(processed / "batch.csv", index=False)

    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return Settings()


def test_add_daily_returns_computes_percent_change() -> None:
    df = pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "close": [100.0, 110.0],
        }
    )
    result = add_daily_returns(df)
    assert pd.isna(result.loc[0, "daily_return_pct"])
    assert result.loc[1, "daily_return_pct"] == pytest.approx(10.0)


def test_load_from_processed_csv(settings_with_csv: Settings) -> None:
    df = load_from_processed_csv(settings_with_csv)
    assert len(df) == 3
    assert set(list_tickers(df)) == {"AAPL", "MSFT"}


def test_filter_tickers(settings_with_csv: Settings) -> None:
    df = load_from_processed_csv(settings_with_csv)
    filtered = filter_tickers(df, ["AAPL"])
    assert len(filtered) == 2
    assert filtered["ticker"].unique().tolist() == ["AAPL"]
