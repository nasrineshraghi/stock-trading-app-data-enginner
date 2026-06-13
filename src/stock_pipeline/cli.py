from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from stock_pipeline.extract.polygon import PolygonExtractError
from stock_pipeline.pipeline import load_csv, run_ingestion_pipeline
from stock_pipeline.quality import validate_ohlcv

app = typer.Typer(
    name="stock-ingest",
    help="Extract stock OHLCV data from Polygon.io, validate quality, and save to CSV.",
)


@app.command()
def ingest(
    ticker: str = typer.Argument(..., help="Stock ticker symbol, e.g. AAPL"),
    start: str = typer.Option(..., "--start", help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="End date YYYY-MM-DD"),
) -> None:
    """Extract, validate, and export OHLCV bars to CSV."""
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise typer.BadParameter("Dates must be YYYY-MM-DD (e.g. 2024-01-02)") from exc
    if start_date > end_date:
        raise typer.BadParameter("--start must be on or before --end")

    try:
        result = run_ingestion_pipeline(ticker, start_date, end_date)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except PolygonExtractError as exc:
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
    typer.echo(f"Ingested {result.row_count} rows for {result.ticker}")
    typer.echo(f"Raw CSV:        {result.raw_path}")
    typer.echo(f"Processed CSV:  {result.processed_path}")
    typer.echo(f"Quality checks: {', '.join(result.quality_checks)}")


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
