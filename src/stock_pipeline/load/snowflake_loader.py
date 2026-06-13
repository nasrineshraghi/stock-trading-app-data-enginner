from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_pipeline.config import Settings
from stock_pipeline.logging_config import get_logger

logger = get_logger(__name__)

try:
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
except ImportError:  # pragma: no cover - exercised via SnowflakeLoadError paths
    snowflake = None
    write_pandas = None

STAGING_TABLE_SUFFIX = "_STAGING"


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


def _qualified_table(settings: Settings, table_name: str) -> str:
    return f"{settings.snowflake_database}.{settings.snowflake_schema}.{table_name}"


def _table_columns_ddl() -> str:
    return """
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
    """


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


def ensure_table(conn, settings: Settings, *, table_name: str | None = None) -> None:
    table_name = table_name or settings.snowflake_table
    qualified = _qualified_table(settings, table_name)
    ddl = f"CREATE TABLE IF NOT EXISTS {qualified} ({_table_columns_ddl()})"
    with conn.cursor() as cursor:
        cursor.execute(ddl)


def _merge_staging_into_target(conn, settings: Settings) -> None:
    target = _qualified_table(settings, settings.snowflake_table)
    staging = _qualified_table(settings, f"{settings.snowflake_table}{STAGING_TABLE_SUFFIX}")
    merge_sql = f"""
    MERGE INTO {target} AS target
    USING {staging} AS source
    ON target.TICKER = source.TICKER AND target.DATE = source.DATE
    WHEN MATCHED THEN UPDATE SET
        OPEN = source.OPEN,
        HIGH = source.HIGH,
        LOW = source.LOW,
        CLOSE = source.CLOSE,
        VOLUME = source.VOLUME,
        VWAP = source.VWAP,
        TRANSACTIONS = source.TRANSACTIONS,
        SOURCE = source.SOURCE,
        INGESTED_AT = source.INGESTED_AT
    WHEN NOT MATCHED THEN INSERT (
        TICKER, DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, VWAP, TRANSACTIONS, SOURCE, INGESTED_AT
    ) VALUES (
        source.TICKER, source.DATE, source.OPEN, source.HIGH, source.LOW, source.CLOSE,
        source.VOLUME, source.VWAP, source.TRANSACTIONS, source.SOURCE, source.INGESTED_AT
    )
    """
    with conn.cursor() as cursor:
        cursor.execute(merge_sql)
        cursor.execute(f"TRUNCATE TABLE {staging}")


def load_dataframe_to_snowflake(
    df: pd.DataFrame,
    settings: Settings,
    *,
    conn=None,
) -> SnowflakeLoadResult:
    """Upsert a validated OHLCV dataframe into Snowflake on (ticker, date)."""
    settings.require_snowflake_settings()
    _require_snowflake_package()

    if df.empty:
        logger.info("Snowflake upsert skipped: dataframe is empty")
        return SnowflakeLoadResult(
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            table=settings.snowflake_table,
            rows_loaded=0,
        )

    owns_connection = conn is None
    conn = conn or _connect(settings)
    staging_table = f"{settings.snowflake_table}{STAGING_TABLE_SUFFIX}"

    try:
        ensure_table(conn, settings)
        ensure_table(conn, settings, table_name=staging_table)

        working = df.copy()
        working["date"] = pd.to_datetime(working["date"]).dt.date

        success, _nchunks, nrows, _output = write_pandas(
            conn,
            working,
            staging_table,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            auto_create_table=False,
            overwrite=True,
            quote_identifiers=False,
        )
        if not success:
            raise SnowflakeLoadError(
                f"Failed to stage rows in {settings.snowflake_database}."
                f"{settings.snowflake_schema}.{staging_table}"
            )

        _merge_staging_into_target(conn, settings)
    except SnowflakeLoadError:
        raise
    except Exception as exc:
        raise SnowflakeLoadError(str(exc)) from exc
    finally:
        if owns_connection:
            conn.close()

    logger.info(
        "Upserted %s rows into %s",
        nrows,
        _qualified_table(settings, settings.snowflake_table),
    )
    return SnowflakeLoadResult(
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        table=settings.snowflake_table,
        rows_loaded=nrows,
    )
