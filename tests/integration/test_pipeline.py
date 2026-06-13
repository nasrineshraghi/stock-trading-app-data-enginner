from datetime import date
from unittest.mock import patch

import httpx

from stock_pipeline.extract.polygon import PolygonClient
from stock_pipeline.pipeline import run_batch_ingestion_pipeline, run_ingestion_pipeline


def test_run_ingestion_pipeline_end_to_end(httpx_mock, polygon_response, test_settings):
    httpx_mock.add_response(json=polygon_response)

    client = PolygonClient(api_key="test-key", client=httpx.Client())
    result = run_ingestion_pipeline(
        "AAPL",
        date(2024, 1, 1),
        date(2024, 1, 31),
        settings=test_settings,
        client=client,
    )

    assert result.row_count == 2
    assert result.ticker == "AAPL"
    assert result.raw_path.exists()
    assert result.processed_path.exists()
    assert "schema:" in result.quality_checks[0]

    client.close()


@patch("stock_pipeline.pipeline.load_dataframe_to_snowflake")
def test_run_ingestion_pipeline_loads_to_snowflake(
    mock_load_snowflake,
    httpx_mock,
    polygon_response,
    test_settings,
):
    from stock_pipeline.load.snowflake_loader import SnowflakeLoadResult

    httpx_mock.add_response(json=polygon_response)
    mock_load_snowflake.return_value = SnowflakeLoadResult(
        database="STOCK_DB",
        schema="RAW",
        table="STOCK_OHLCV",
        rows_loaded=2,
    )

    client = PolygonClient(api_key="test-key", client=httpx.Client())
    result = run_ingestion_pipeline(
        "AAPL",
        date(2024, 1, 1),
        date(2024, 1, 31),
        settings=test_settings,
        client=client,
        load_to_snowflake=True,
    )

    assert result.snowflake is not None
    assert result.snowflake.rows_loaded == 2
    mock_load_snowflake.assert_called_once()

    client.close()


def test_run_batch_ingestion_pipeline_partial_failure(httpx_mock, polygon_response, test_settings):
    httpx_mock.add_response(json=polygon_response)
    httpx_mock.add_response(status_code=404, json={"status": "ERROR", "error": "Not found"})

    batch = run_batch_ingestion_pipeline(
        ["AAPL", "BAD"],
        date(2024, 1, 1),
        date(2024, 1, 31),
        settings=test_settings,
    )

    assert len(batch.results) == 1
    assert batch.results[0].ticker == "AAPL"
    assert len(batch.failures) == 1
    assert batch.failures[0][0] == "BAD"


def test_run_batch_ingestion_pipeline_all_success(httpx_mock, polygon_response, test_settings):
    httpx_mock.add_response(json=polygon_response)
    httpx_mock.add_response(json=polygon_response)

    batch = run_batch_ingestion_pipeline(
        ["AAPL", "MSFT"],
        date(2024, 1, 1),
        date(2024, 1, 31),
        settings=test_settings,
    )

    assert len(batch.results) == 2
    assert batch.failures == []
