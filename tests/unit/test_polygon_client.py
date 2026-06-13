from datetime import date

import pytest

from stock_pipeline.extract.polygon import PolygonClient, PolygonExtractError


def test_fetch_aggregates_success(httpx_mock, polygon_response):
    httpx_mock.add_response(json=polygon_response)

    with PolygonClient(api_key="test-key") as client:
        bars = client.fetch_aggregates("AAPL", date(2024, 1, 1), date(2024, 1, 31))

    assert len(bars) == 2
    assert bars[0].open == 150.0
    assert bars[0].close == 151.0
    assert bars[1].volume == 1_100_000.0

    request = httpx_mock.get_requests()[0]
    assert "AAPL" in str(request.url)
    assert request.url.params["apiKey"] == "test-key"


def test_fetch_aggregates_api_error(httpx_mock):
    httpx_mock.add_response(status_code=403, text="Forbidden")

    with PolygonClient(api_key="bad-key") as client:
        with pytest.raises(PolygonExtractError, match="403"):
            client.fetch_aggregates("AAPL", date(2024, 1, 1), date(2024, 1, 31))


def test_fetch_aggregates_unexpected_status(httpx_mock):
    httpx_mock.add_response(json={"status": "ERROR", "error": "Invalid ticker"})

    with PolygonClient(api_key="test-key") as client:
        with pytest.raises(PolygonExtractError, match="Invalid ticker"):
            client.fetch_aggregates("BAD", date(2024, 1, 1), date(2024, 1, 31))


def test_fetch_aggregates_empty_results(httpx_mock):
    httpx_mock.add_response(json={"status": "OK", "results": []})

    with PolygonClient(api_key="test-key") as client:
        bars = client.fetch_aggregates("AAPL", date(2024, 1, 1), date(2024, 1, 31))

    assert bars == []
