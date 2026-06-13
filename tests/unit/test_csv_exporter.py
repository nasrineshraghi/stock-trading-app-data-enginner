from datetime import date
from pathlib import Path

import pandas as pd

from stock_pipeline.load.csv_exporter import build_output_path, export_dataframe


def test_build_output_path():
    path = build_output_path(Path("/data"), "aapl", date(2024, 1, 1), date(2024, 1, 31))
    assert path == Path("/data/processed/AAPL_2024-01-01_2024-01-31.csv")


def test_export_dataframe_writes_csv(tmp_path, sample_ohlcv_df):
    output = tmp_path / "out" / "test.csv"
    result = export_dataframe(sample_ohlcv_df, output)

    assert result.exists()
    loaded = pd.read_csv(result, parse_dates=["date"])
    assert len(loaded) == 2
    assert loaded.loc[0, "ticker"] == "AAPL"
