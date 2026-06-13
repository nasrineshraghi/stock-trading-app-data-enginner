from datetime import date

import httpx

from stock_pipeline.extract.polygon import PolygonClient
from stock_pipeline.pipeline import run_ingestion_pipeline


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
