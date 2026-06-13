from datetime import date
from unittest.mock import patch

import pytest

from stock_pipeline.config import Settings
from stock_pipeline.incremental import IncrementalSkip, resolve_incremental_range


@pytest.fixture
def incremental_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path / "data",
        incremental_lookback_days=30,
        snowflake_account="xy12345.us-east-1",
        snowflake_user="pipeline_user",
        snowflake_password="secret",
        snowflake_warehouse="COMPUTE_WH",
        snowflake_database="STOCK_DB",
        snowflake_schema="RAW",
        snowflake_table="STOCK_OHLCV",
    )


@patch("stock_pipeline.incremental.get_last_loaded_date_from_snowflake")
def test_resolve_incremental_range_uses_day_after_last_load(mock_last_date, incremental_settings):
    mock_last_date.return_value = date(2025, 6, 5)

    start, end = resolve_incremental_range(
        "AAPL",
        incremental_settings,
        end_date=date(2025, 6, 10),
    )

    assert start == date(2025, 6, 6)
    assert end == date(2025, 6, 10)


@patch("stock_pipeline.incremental.get_last_loaded_date_from_snowflake")
def test_resolve_incremental_range_uses_lookback_when_empty(mock_last_date, incremental_settings):
    mock_last_date.return_value = None

    start, end = resolve_incremental_range(
        "AAPL",
        incremental_settings,
        end_date=date(2025, 6, 10),
    )

    assert start == date(2025, 5, 11)
    assert end == date(2025, 6, 10)


@patch("stock_pipeline.incremental.get_last_loaded_date_from_snowflake")
def test_resolve_incremental_range_skips_when_up_to_date(mock_last_date, incremental_settings):
    mock_last_date.return_value = date(2025, 6, 10)

    with pytest.raises(IncrementalSkip, match="already up to date"):
        resolve_incremental_range("AAPL", incremental_settings, end_date=date(2025, 6, 10))


def test_get_last_loaded_date_from_csv(tmp_path):
    settings = Settings(
        _env_file=None,
        polygon_api_key="test-key",
        data_dir=tmp_path / "data",
    )
    processed = settings.processed_dir
    processed.mkdir(parents=True)
    (processed / "AAPL_2024-01-01_2024-01-31.csv").write_text("ticker,date\n", encoding="utf-8")
    (processed / "AAPL_2024-02-01_2024-02-15.csv").write_text("ticker,date\n", encoding="utf-8")

    from stock_pipeline.incremental import _get_last_loaded_date_from_csv

    assert _get_last_loaded_date_from_csv("AAPL", settings) == date(2024, 2, 15)
