from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from stock_pipeline.config import Settings, get_settings
from stock_pipeline.extract.polygon import PolygonClient
from stock_pipeline.load.csv_exporter import build_output_path, export_dataframe
from stock_pipeline.load.snowflake_loader import SnowflakeLoadResult, load_dataframe_to_snowflake
from stock_pipeline.quality import assert_ohlcv_quality
from stock_pipeline.transform.normalize import bars_to_dataframe


@dataclass
class PipelineResult:
    ticker: str
    start_date: date
    end_date: date
    row_count: int
    raw_path: Path
    processed_path: Path
    quality_checks: list[str]
    snowflake: SnowflakeLoadResult | None = None


def run_ingestion_pipeline(
    ticker: str,
    start_date: date,
    end_date: date,
    *,
    settings: Settings | None = None,
    client: PolygonClient | None = None,
    load_to_snowflake: bool = False,
) -> PipelineResult:
    settings = settings or get_settings()
    owns_client = client is None
    client = client or PolygonClient(
        api_key=settings.polygon_api_key,
        base_url=settings.polygon_base_url,
    )

    try:
        bars = client.fetch_aggregates(ticker, start_date, end_date)
        df = bars_to_dataframe(ticker, bars)

        raw_path = build_output_path(
            settings.data_dir,
            ticker,
            start_date,
            end_date,
            stage="raw",
        )
        export_dataframe(df, raw_path)

        report = assert_ohlcv_quality(df)

        processed_path = build_output_path(
            settings.data_dir,
            ticker,
            start_date,
            end_date,
            stage="processed",
        )
        export_dataframe(df, processed_path)

        snowflake_result = None
        if load_to_snowflake:
            snowflake_result = load_dataframe_to_snowflake(df, settings)

        return PipelineResult(
            ticker=ticker.upper(),
            start_date=start_date,
            end_date=end_date,
            row_count=report.row_count,
            raw_path=raw_path,
            processed_path=processed_path,
            quality_checks=report.checks_run,
            snowflake=snowflake_result,
        )
    finally:
        if owns_client:
            client.close()


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"])
