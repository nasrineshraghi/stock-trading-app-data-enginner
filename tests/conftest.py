import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from stock_pipeline.config import Settings


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def polygon_response(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "polygon_aggs_response.json").read_text())


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ticker": ["AAPL", "AAPL"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "open": [150.0, 151.0],
            "high": [152.0, 153.0],
            "low": [149.5, 150.5],
            "close": [151.0, 152.5],
            "volume": [1_000_000.0, 1_100_000.0],
            "vwap": [150.25, 151.75],
            "transactions": [50_000, 52_000],
            "source": ["polygon.io", "polygon.io"],
            "ingested_at": ["2024-06-01T00:00:00+00:00", "2024-06-01T00:00:00+00:00"],
        }
    )


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        polygon_api_key="test-key",
        polygon_base_url="https://api.polygon.io",
        data_dir=tmp_path / "data",
    )


@pytest.fixture
def date_range() -> tuple[date, date]:
    return date(2024, 1, 1), date(2024, 1, 31)
