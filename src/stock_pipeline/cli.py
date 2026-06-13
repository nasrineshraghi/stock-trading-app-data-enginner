from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from stock_pipeline.extract.polygon import PolygonExtractError
from stock_pipeline.load.snowflake_loader import SnowflakeLoadError
from stock_pipeline.logging_config import setup_logging
from stock_pipeline.pipeline import (
    load_csv,
    run_batch_ingestion_pipeline,
    run_ingestion_pipeline,
)
from stock_pipeline.quality import validate_ohlcv

app = typer.Typer(
    name="stock-ingest",
    help="Extract stock OHLCV data from Polygon.io, validate quality, and save to CSV.",
)


def _parse_dates(start: str, end: str) -> tuple[date, date]:
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise typer.BadParameter("Dates must be YYYY-MM-DD (e.g. 2024-01-02)") from exc
    if start_date > end_date:
        raise typer.BadParameter("--start must be on or before --end")
    return start_date, end_date


def _load_tickers_file(path: Path) -> list[str]:
    if not path.exists():
        raise typer.BadParameter(f"Tickers file not found: {path}")
    tickers = [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not tickers:
        raise typer.BadParameter(f"No tickers found in {path}")
    return tickers


def _print_result(result) -> None:
    typer.echo(f"Ingested {result.row_count} rows for {result.ticker}")
    typer.echo(f"Raw CSV:        {result.raw_path}")
    typer.echo(f"Processed CSV:  {result.processed_path}")
    typer.echo(f"Quality checks: {', '.join(result.quality_checks)}")
    if result.snowflake is not None:
        typer.echo(
            f"Snowflake table: {result.snowflake.qualified_table} "
            f"({result.snowflake.rows_loaded} rows upserted)"
        )


def _print_batch_summary(batch_result) -> None:
    typer.echo("")
    succeeded = len(batch_result.results)
    failed = len(batch_result.failures)
    typer.echo(f"Batch summary: {succeeded} succeeded, {failed} failed")
    for result in batch_result.results:
        typer.echo(f"  OK  {result.ticker}: {result.row_count} rows")
    for ticker, message in batch_result.failures:
        typer.echo(f"  FAIL {ticker}: {message}", err=True)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging (place before command: stock-ingest -v ingest ...)",
    ),
) -> None:
    setup_logging(verbose=verbose)


@app.command()
def ingest(
    tickers: list[str] = typer.Argument(..., help="One or more ticker symbols, e.g. AAPL MSFT"),
    start: str = typer.Option(..., "--start", help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="End date YYYY-MM-DD"),
    snowflake: bool = typer.Option(
        False,
        "--snowflake",
        help="Upsert validated rows into Snowflake after CSV export",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Extract, validate, and export OHLCV bars to CSV."""
    setup_logging(verbose=verbose)
    start_date, end_date = _parse_dates(start, end)

    if len(tickers) == 1:
        try:
            result = run_ingestion_pipeline(
                tickers[0],
                start_date,
                end_date,
                load_to_snowflake=snowflake,
            )
        except RuntimeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        except SnowflakeLoadError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        except PolygonExtractError as exc:
            _handle_polygon_error(exc)
        _print_result(result)
        return

    batch_result = _run_batch(tickers, start_date, end_date, snowflake=snowflake)
    _print_batch_summary(batch_result)
    if batch_result.failures:
        raise typer.Exit(1)


@app.command("ingest-batch")
def ingest_batch(
    tickers_file: Path = typer.Argument(..., help="Path to tickers file (one symbol per line)"),
    start: str = typer.Option(..., "--start", help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="End date YYYY-MM-DD"),
    snowflake: bool = typer.Option(
        False,
        "--snowflake",
        help="Upsert validated rows into Snowflake after CSV export",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Ingest multiple tickers listed in a file."""
    setup_logging(verbose=verbose)
    start_date, end_date = _parse_dates(start, end)
    tickers = _load_tickers_file(tickers_file)
    batch_result = _run_batch(tickers, start_date, end_date, snowflake=snowflake)
    _print_batch_summary(batch_result)
    if batch_result.failures:
        raise typer.Exit(1)


def _run_batch(tickers: list[str], start_date: date, end_date: date, *, snowflake: bool):
    try:
        return run_batch_ingestion_pipeline(
            tickers,
            start_date,
            end_date,
            load_to_snowflake=snowflake,
        )
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


def _handle_polygon_error(exc: PolygonExtractError) -> None:
    message = str(exc)
    if "NOT_AUTHORIZED" in message or "403" in message:
        typer.echo(
            "Polygon rejected this date range for your plan (403 NOT_AUTHORIZED).\n"
            "Free plans typically include ~2 years of history — try more recent dates,\n"
            "e.g. --start 2025-06-01 --end 2025-06-05",
            err=True,
        )
    else:
        typer.echo(message, err=True)
    raise typer.Exit(1) from exc


@app.command("validate")
def validate_csv(
    path: Path = typer.Argument(..., help="CSV file to validate"),
) -> None:
    """Run data quality checks on an existing CSV file."""
    df = load_csv(path)
    report = validate_ohlcv(df)
    if report.passed:
        typer.echo(f"PASS — {report.row_count} rows, checks: {', '.join(report.checks_run)}")
        raise typer.Exit(0)
    typer.echo(f"FAIL — {report.row_count} rows")
    for error in report.errors:
        typer.echo(f"  - {error}")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
