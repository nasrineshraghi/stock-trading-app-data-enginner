"""Tests for dashboard data loading helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stock_pipeline.config import Settings
from stock_pipeline.dashboard.data import (
    MART_COLUMNS,
    add_daily_returns,
    filter_tickers,
    list_tickers,
    load_dashboard_data,
    load_from_processed_csv,
    load_mart_from_snowflake,
)
from stock_pipeline.load.snowflake_loader import SnowflakeLoadError


@pytest.fixture
def settings_with_csv(tmp_path: Path) -> Settings:
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

    return Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path,
    )


@pytest.fixture
def snowflake_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path / "data",
        snowflake_account="xy12345.us-east-1",
        snowflake_user="pipeline_user",
        snowflake_password="secret",
        snowflake_warehouse="COMPUTE_WH",
        snowflake_database="STOCK_DB",
        snowflake_schema="RAW_DATA_STOCK",
    )


def _mart_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "TICKER": ["AAPL"],
            "DATE": pd.to_datetime(["2024-01-02"]),
            "OPEN": [150.0],
            "HIGH": [152.0],
            "LOW": [149.0],
            "CLOSE": [151.0],
            "VOLUME": [1_000_000.0],
            "VWAP": [150.5],
            "TRANSACTIONS": [1000],
            "DAILY_RETURN_PCT": [None],
        }
    )


def test_add_daily_returns_empty_frame() -> None:
    result = add_daily_returns(pd.DataFrame())
    assert result.empty


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


def test_load_from_processed_csv_missing_dir(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path / "missing",
    )
    df = load_from_processed_csv(settings)
    assert list(df.columns) == MART_COLUMNS
    assert df.empty


def test_filter_tickers(settings_with_csv: Settings) -> None:
    df = load_from_processed_csv(settings_with_csv)
    filtered = filter_tickers(df, ["AAPL"])
    assert len(filtered) == 2
    assert filtered["ticker"].unique().tolist() == ["AAPL"]


def test_filter_tickers_empty_selection(settings_with_csv: Settings) -> None:
    df = load_from_processed_csv(settings_with_csv)
    assert filter_tickers(df, []).empty


def test_list_tickers_empty_frame() -> None:
    assert list_tickers(pd.DataFrame(columns=MART_COLUMNS)) == []


def test_load_dashboard_data_csv_source(settings_with_csv: Settings) -> None:
    df, label = load_dashboard_data(settings_with_csv, source="csv")
    assert label == "Processed CSV"
    assert len(df) == 3


def test_load_dashboard_data_csv_source_raises_when_empty(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path,
    )
    with pytest.raises(RuntimeError, match="No processed CSV files found"):
        load_dashboard_data(settings, source="csv")


def test_load_dashboard_data_auto_falls_back_to_csv(settings_with_csv: Settings) -> None:
    df, label = load_dashboard_data(settings_with_csv, source="auto")
    assert label == "Processed CSV"
    assert not df.empty


def test_load_dashboard_data_raises_when_no_sources(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path,
    )
    with pytest.raises(RuntimeError, match="No dashboard data found"):
        load_dashboard_data(settings, source="auto")


@patch("stock_pipeline.dashboard.data._require_snowflake_package")
@patch("stock_pipeline.dashboard.data._connect")
def test_load_mart_from_snowflake(
    mock_connect: MagicMock,
    _mock_require_pkg: MagicMock,
    snowflake_settings: Settings,
) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetch_pandas_all.return_value = _mart_frame()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cm
    mock_connect.return_value = mock_conn

    df = load_mart_from_snowflake(snowflake_settings, ticker="aapl")

    assert len(df) == 1
    assert df.loc[0, "ticker"] == "AAPL"
    mock_cursor.execute.assert_called_once()
    assert mock_cursor.execute.call_args.args[1] == ("AAPL",)


@patch("stock_pipeline.dashboard.data._require_snowflake_package")
@patch("stock_pipeline.dashboard.data._connect")
def test_load_dashboard_data_snowflake_source(
    mock_connect: MagicMock,
    _mock_require_pkg: MagicMock,
    snowflake_settings: Settings,
) -> None:
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetch_pandas_all.return_value = _mart_frame()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cm
    mock_connect.return_value = mock_conn

    df, label = load_dashboard_data(snowflake_settings, source="snowflake")

    assert label == "Snowflake mart"
    assert len(df) == 1


@patch("stock_pipeline.dashboard.data.load_mart_from_snowflake")
def test_load_dashboard_data_snowflake_empty_raises(
    mock_load_mart: MagicMock,
    snowflake_settings: Settings,
) -> None:
    mock_load_mart.return_value = pd.DataFrame(columns=MART_COLUMNS)

    with pytest.raises(RuntimeError, match="No rows in STOCK_DB.MARTS"):
        load_dashboard_data(snowflake_settings, source="snowflake")


@patch(
    "stock_pipeline.dashboard.data.load_mart_from_snowflake",
    side_effect=SnowflakeLoadError("boom"),
)
def test_load_dashboard_data_snowflake_error_propagates(
    _mock_load_mart: MagicMock,
    snowflake_settings: Settings,
) -> None:
    with pytest.raises(SnowflakeLoadError, match="boom"):
        load_dashboard_data(snowflake_settings, source="snowflake")


@patch(
    "stock_pipeline.dashboard.data.load_mart_from_snowflake",
    side_effect=SnowflakeLoadError("boom"),
)
def test_load_dashboard_data_auto_falls_back_after_snowflake_error(
    _mock_load_mart: MagicMock,
    settings_with_csv: Settings,
) -> None:
    snowflake_settings = settings_with_csv.model_copy(
        update={
            "snowflake_account": "xy12345.us-east-1",
            "snowflake_user": "pipeline_user",
            "snowflake_password": "secret",
            "snowflake_warehouse": "COMPUTE_WH",
            "snowflake_database": "STOCK_DB",
            "snowflake_schema": "RAW_DATA_STOCK",
        }
    )

    df, label = load_dashboard_data(snowflake_settings, source="auto")

    assert label == "Processed CSV"
    assert len(df) == 3
