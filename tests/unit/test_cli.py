from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from stock_pipeline.cli import app
from stock_pipeline.load.csv_exporter import export_dataframe

runner = CliRunner()


def test_validate_command_passes(sample_ohlcv_df, tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    export_dataframe(sample_ohlcv_df, csv_path)

    result = runner.invoke(app, ["validate", str(csv_path)])

    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_validate_command_fails_on_bad_data(sample_ohlcv_df, tmp_path: Path):
    bad = sample_ohlcv_df.copy()
    bad.loc[0, "volume"] = -1.0
    csv_path = tmp_path / "bad.csv"
    export_dataframe(bad, csv_path)

    result = runner.invoke(app, ["validate", str(csv_path)])

    assert result.exit_code == 1
    assert "FAIL" in result.stdout


def test_ingest_command_invalid_date_range():
    result = runner.invoke(
        app,
        ["ingest", "AAPL", "--start", "2024-02-01", "--end", "2024-01-01"],
    )

    assert result.exit_code != 0


def test_ingest_command_success(httpx_mock, polygon_response, monkeypatch, tmp_path: Path):
    httpx_mock.add_response(json=polygon_response)
    monkeypatch.setenv("POLYGON_API_KEY", "test-key")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    result = runner.invoke(
        app,
        ["ingest", "AAPL", "--start", "2024-01-01", "--end", "2024-01-31"],
    )

    assert result.exit_code == 0
    assert "Ingested 2 rows" in result.stdout
    assert (tmp_path / "data" / "processed" / "AAPL_2024-01-01_2024-01-31.csv").exists()
