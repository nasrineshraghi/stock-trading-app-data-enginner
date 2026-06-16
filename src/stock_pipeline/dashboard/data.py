from __future__ import annotations

import pandas as pd

from stock_pipeline.config import Settings
from stock_pipeline.load.snowflake_loader import (
    SnowflakeLoadError,
    _connect,
    _require_snowflake_package,
)

MARTS_SCHEMA = "MARTS"
MARTS_TABLE = "FCT_STOCK_DAILY_RETURNS"

MART_COLUMNS = [
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "transactions",
    "daily_return_pct",
]


def add_daily_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Compute daily_return_pct when loading from CSV (no dbt mart)."""
    if df.empty:
        return df.copy()

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["ticker", "date"])
    prev_close = working.groupby("ticker", sort=False)["close"].shift(1)
    working["daily_return_pct"] = (working["close"] - prev_close) / prev_close * 100
    working.loc[prev_close.isna() | (prev_close == 0), "daily_return_pct"] = None
    return working


def _normalize_mart_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=MART_COLUMNS)

    working = df.copy()
    working.columns = [str(col).lower() for col in working.columns]
    working["date"] = pd.to_datetime(working["date"])
    working["ticker"] = working["ticker"].str.upper()
    return working.sort_values(["ticker", "date"]).reset_index(drop=True)


def load_mart_from_snowflake(settings: Settings, ticker: str | None = None) -> pd.DataFrame:
    """Load rows from the dbt mart in Snowflake."""
    settings.require_snowflake_settings()
    _require_snowflake_package()

    database = settings.snowflake_database
    qualified = f"{database}.{MARTS_SCHEMA}.{MARTS_TABLE}"
    sql = f"""
        SELECT
            ticker,
            date,
            open,
            high,
            low,
            close,
            volume,
            vwap,
            transactions,
            daily_return_pct
        FROM {qualified}
    """
    params: tuple[str, ...] = ()
    if ticker:
        sql += " WHERE ticker = %s"
        params = (ticker.upper(),)
    sql += " ORDER BY ticker, date"

    conn = _connect(settings)
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            df = cursor.fetch_pandas_all()
    finally:
        conn.close()

    return _normalize_mart_frame(df)


def load_from_processed_csv(settings: Settings) -> pd.DataFrame:
    """Load all processed CSV files and compute daily returns."""
    processed_dir = settings.processed_dir
    if not processed_dir.exists():
        return pd.DataFrame(columns=MART_COLUMNS)

    frames: list[pd.DataFrame] = []
    for path in sorted(processed_dir.glob("*.csv")):
        frame = pd.read_csv(path, parse_dates=["date"])
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=MART_COLUMNS)

    combined = pd.concat(frames, ignore_index=True)
    combined["ticker"] = combined["ticker"].str.upper()
    combined = combined.drop_duplicates(subset=["ticker", "date"], keep="last")
    with_returns = add_daily_returns(combined)
    return with_returns[MART_COLUMNS].sort_values(["ticker", "date"]).reset_index(drop=True)


def load_dashboard_data(settings: Settings, source: str = "auto") -> tuple[pd.DataFrame, str]:
    """
    Load mart-shaped data for the dashboard.

    source: auto | snowflake | csv
    """
    if source == "csv":
        df = load_from_processed_csv(settings)
        if df.empty:
            raise RuntimeError(
                "No processed CSV files found. Run stock-ingest first or use Snowflake."
            )
        return df, "Processed CSV"

    if source == "snowflake" or (source == "auto" and settings.snowflake_configured):
        try:
            df = load_mart_from_snowflake(settings)
            if not df.empty or source == "snowflake":
                if df.empty and source == "snowflake":
                    raise RuntimeError(
                        f"No rows in {settings.snowflake_database}.{MARTS_SCHEMA}.{MARTS_TABLE}. "
                        "Run make dbt-run after loading raw data."
                    )
                return df, "Snowflake mart"
        except (SnowflakeLoadError, RuntimeError):
            if source == "snowflake":
                raise

    df = load_from_processed_csv(settings)
    if not df.empty:
        return df, "Processed CSV"

    raise RuntimeError(
        "No dashboard data found. Run ingest + dbt, or create processed CSV files."
    )


def list_tickers(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return []
    return sorted(df["ticker"].unique().tolist())


def filter_tickers(df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return df.iloc[0:0]
    selected = {ticker.upper() for ticker in tickers}
    return df[df["ticker"].isin(selected)].copy()
