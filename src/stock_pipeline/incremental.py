from __future__ import annotations

from datetime import date, timedelta

from stock_pipeline.config import Settings
from stock_pipeline.load.snowflake_loader import (
    get_last_loaded_date as get_last_loaded_date_from_snowflake,
)
from stock_pipeline.logging_config import get_logger

logger = get_logger(__name__)


class IncrementalSkip(Exception):
    """Raised when data is already up to date."""


def resolve_incremental_range(
    ticker: str,
    settings: Settings,
    *,
    end_date: date | None = None,
) -> tuple[date, date]:
    end = end_date or date.today()
    last_date = _get_last_loaded_date(ticker, settings)

    if last_date is None:
        start = end - timedelta(days=settings.incremental_lookback_days)
        logger.info(
            "No prior data for %s; using %s-day lookback from %s",
            ticker.upper(),
            settings.incremental_lookback_days,
            start,
        )
    else:
        start = last_date + timedelta(days=1)
        logger.info("Last loaded date for %s is %s", ticker.upper(), last_date)

    if start > end:
        raise IncrementalSkip(f"{ticker.upper()} is already up to date through {last_date}")

    return start, end


def _get_last_loaded_date(ticker: str, settings: Settings) -> date | None:
    if settings.snowflake_configured:
        return get_last_loaded_date_from_snowflake(ticker, settings)

    return _get_last_loaded_date_from_csv(ticker, settings)


def _get_last_loaded_date_from_csv(ticker: str, settings: Settings) -> date | None:
    processed_dir = settings.processed_dir
    if not processed_dir.exists():
        return None

    prefix = f"{ticker.upper()}_"
    matching = sorted(processed_dir.glob(f"{prefix}*.csv"))
    if not matching:
        return None

    latest_end: date | None = None
    for path in matching:
        stem = path.stem
        if not stem.startswith(prefix):
            continue
        end_part = stem.rsplit("_", 1)[-1]
        try:
            file_end = date.fromisoformat(end_part)
        except ValueError:
            continue
        latest_end = file_end if latest_end is None else max(latest_end, file_end)

    return latest_end
