from unittest.mock import MagicMock, patch

import pytest

from stock_pipeline.config import Settings
from stock_pipeline.load.snowflake_loader import (
    SnowflakeLoadError,
    load_dataframe_to_snowflake,
)


@pytest.fixture
def snowflake_settings(tmp_path) -> Settings:
    return Settings(
        polygon_api_key="test-key",
        data_dir=tmp_path / "data",
        snowflake_account="xy12345.us-east-1",
        snowflake_user="pipeline_user",
        snowflake_password="secret",
        snowflake_warehouse="COMPUTE_WH",
        snowflake_database="STOCK_DB",
        snowflake_schema="RAW",
        snowflake_table="STOCK_OHLCV",
    )


@patch("stock_pipeline.load.snowflake_loader.write_pandas")
@patch("stock_pipeline.load.snowflake_loader._connect")
@patch("stock_pipeline.load.snowflake_loader.snowflake")
def test_load_dataframe_to_snowflake(
    _mock_snowflake_module, mock_connect, mock_write_pandas, sample_ohlcv_df, snowflake_settings
):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_write_pandas.return_value = (True, 1, 2, [])

    result = load_dataframe_to_snowflake(sample_ohlcv_df, snowflake_settings)

    assert result.rows_loaded == 2
    assert result.qualified_table == "STOCK_DB.RAW.STOCK_OHLCV"
    mock_connect.assert_called_once()
    mock_write_pandas.assert_called_once()
    mock_conn.close.assert_called_once()


def test_load_dataframe_to_snowflake_requires_config(sample_ohlcv_df, test_settings):
    with pytest.raises(RuntimeError, match="Snowflake is not fully configured"):
        load_dataframe_to_snowflake(sample_ohlcv_df, test_settings)


@patch("stock_pipeline.load.snowflake_loader.write_pandas")
@patch("stock_pipeline.load.snowflake_loader._connect")
@patch("stock_pipeline.load.snowflake_loader.snowflake")
def test_load_dataframe_to_snowflake_wraps_write_errors(
    _mock_snowflake_module, mock_connect, mock_write_pandas, sample_ohlcv_df, snowflake_settings
):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    mock_write_pandas.side_effect = Exception("network down")

    with pytest.raises(SnowflakeLoadError, match="network down"):
        load_dataframe_to_snowflake(sample_ohlcv_df, snowflake_settings)

    mock_conn.close.assert_called_once()
