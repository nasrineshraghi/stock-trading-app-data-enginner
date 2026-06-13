from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from stock_pipeline.config import Settings, get_settings
from stock_pipeline.extract.polygon import PolygonClient, PolygonExtractError
from stock_pipeline.load.csv_exporter import build_output_path, export_dataframe
from stock_pipeline.load.snowflake_loader import (
    SnowflakeLoadError,
    SnowflakeLoadResult,
    load_dataframe_to_snowflake,
)
from stock_pipeline.logging_config import get_logger
from stock_pipeline.quality import DataQualityError, assert_ohlcv_quality
from stock_pipeline.transform.normalize import bars_to_dataframe

logger = get_logger(__name__)


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


@dataclass
class BatchPipelineResult:
    results: list[PipelineResult]
    failures: list[tuple[str, str]]


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
        logger.info("Extracting %s from %s to %s", ticker.upper(), start_date, end_date)
        bars = client.fetch_aggregates(ticker, start_date, end_date)
        logger.info("Extracted %s bars for %s", len(bars), ticker.upper())

        df = bars_to_dataframe(ticker, bars)
        logger.info("Normalized to %s rows for %s", len(df), ticker.upper())

        raw_path = build_output_path(
            settings.data_dir,
            ticker,
            start_date,
            end_date,
            stage="raw",
        )
        export_dataframe(df, raw_path)
        logger.info("Wrote raw CSV: %s", raw_path)

        report = assert_ohlcv_quality(df)
        logger.info("Quality checks passed for %s (%s rows)", ticker.upper(), report.row_count)

        processed_path = build_output_path(
            settings.data_dir,
            ticker,
            start_date,
            end_date,
            stage="processed",
        )
        export_dataframe(df, processed_path)
        logger.info("Wrote processed CSV: %s", processed_path)

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


def run_batch_ingestion_pipeline(
    tickers: list[str],
    start_date: date,
    end_date: date,
    *,
    settings: Settings | None = None,
    load_to_snowflake: bool = False,
) -> BatchPipelineResult:
    settings = settings or get_settings()
    results: list[PipelineResult] = []
    failures: list[tuple[str, str]] = []

    client = PolygonClient(
        api_key=settings.polygon_api_key,
        base_url=settings.polygon_base_url,
    )
    try:
        for ticker in tickers:
            symbol = ticker.strip().upper()
            if not symbol:
                continue
            try:
                results.append(
                    run_ingestion_pipeline(
                        symbol,
                        start_date,
                        end_date,
                        settings=settings,
                        client=client,
                        load_to_snowflake=load_to_snowflake,
                    )
                )
            except (PolygonExtractError, DataQualityError, SnowflakeLoadError, RuntimeError) as exc:
                logger.error("Ingestion failed for %s: %s", symbol, exc)
                failures.append((symbol, str(exc)))
    finally:
        client.close()

    logger.info("Batch complete: %s succeeded, %s failed", len(results), len(failures))
    return BatchPipelineResult(results=results, failures=failures)


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"])
