from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_pipeline.config import Settings

try:
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
except ImportError:  # pragma: no cover - exercised via SnowflakeLoadError paths
    snowflake = None
    write_pandas = None


class SnowflakeLoadError(Exception):
    """Raised when loading data to Snowflake fails."""


@dataclass(frozen=True)
class SnowflakeLoadResult:
    database: str
    schema: str
    table: str
    rows_loaded: int

    @property
    def qualified_table(self) -> str:
        return f"{self.database}.{self.schema}.{self.table}"


def _require_snowflake_package() -> None:
    if snowflake is None or write_pandas is None:
        raise SnowflakeLoadError(
            "Snowflake support is not installed. Run: pip install -e '.[snowflake]'"
        )


def _connect(settings: Settings):
    _require_snowflake_package()
    connect_kwargs = {
        "account": settings.snowflake_account,
        "user": settings.snowflake_user,
        "password": settings.snowflake_password,
        "warehouse": settings.snowflake_warehouse,
        "database": settings.snowflake_database,
        "schema": settings.snowflake_schema,
    }
    if settings.snowflake_role:
        connect_kwargs["role"] = settings.snowflake_role

    return snowflake.connector.connect(**connect_kwargs)


def ensure_table(conn, settings: Settings) -> None:
    table = (
        f"{settings.snowflake_database}.{settings.snowflake_schema}.{settings.snowflake_table}"
    )
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        TICKER VARCHAR NOT NULL,
        DATE DATE NOT NULL,
        OPEN FLOAT,
        HIGH FLOAT,
        LOW FLOAT,
        CLOSE FLOAT,
        VOLUME FLOAT,
        VWAP FLOAT,
        TRANSACTIONS NUMBER,
        SOURCE VARCHAR,
        INGESTED_AT VARCHAR
    )
    """
    with conn.cursor() as cursor:
        cursor.execute(ddl)


def load_dataframe_to_snowflake(
    df: pd.DataFrame,
    settings: Settings,
    *,
    conn=None,
) -> SnowflakeLoadResult:
    """Append a validated OHLCV dataframe to Snowflake."""
    settings.require_snowflake_settings()
    _require_snowflake_package()

    if df.empty:
        return SnowflakeLoadResult(
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            table=settings.snowflake_table,
            rows_loaded=0,
        )

    owns_connection = conn is None
    conn = conn or _connect(settings)

    try:
        ensure_table(conn, settings)

        working = df.copy()
        working["date"] = pd.to_datetime(working["date"]).dt.date

        success, _nchunks, nrows, _output = write_pandas(
            conn,
            working,
            settings.snowflake_table,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            auto_create_table=False,
            overwrite=False,
            quote_identifiers=False,
        )
    except Exception as exc:
        raise SnowflakeLoadError(str(exc)) from exc
    finally:
        if owns_connection:
            conn.close()

    if not success:
        raise SnowflakeLoadError(
            f"Failed to load rows into {settings.snowflake_database}."
            f"{settings.snowflake_schema}.{settings.snowflake_table}"
        )

    return SnowflakeLoadResult(
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        table=settings.snowflake_table,
        rows_loaded=nrows,
    )
