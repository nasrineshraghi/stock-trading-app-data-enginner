from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column, DataFrameSchema


class DataQualityError(Exception):
    """Raised when dataframe fails quality validation."""


@dataclass
class QualityReport:
    passed: bool
    row_count: int
    checks_run: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


OHLCV_SCHEMA = DataFrameSchema(
    {
        "ticker": Column(str, Check.str_length(min_value=1)),
        "date": Column("datetime64[ns]"),
        "open": Column(float, Check.ge(0)),
        "high": Column(float, Check.ge(0)),
        "low": Column(float, Check.ge(0)),
        "close": Column(float, Check.ge(0)),
        "volume": Column(float, Check.ge(0)),
        "vwap": Column(float, nullable=True, checks=Check.ge(0)),
        "transactions": Column("Int64", nullable=True, checks=Check.ge(0)),
        "source": Column(str, Check.eq("polygon.io")),
        "ingested_at": Column(str, Check.str_length(min_value=1)),
    },
    checks=[
        Check(lambda df: (df["high"] >= df["low"]).all(), error="high must be >= low"),
        Check(lambda df: (df["high"] >= df["open"]).all(), error="high must be >= open"),
        Check(lambda df: (df["high"] >= df["close"]).all(), error="high must be >= close"),
        Check(lambda df: (df["low"] <= df["open"]).all(), error="low must be <= open"),
        Check(lambda df: (df["low"] <= df["close"]).all(), error="low must be <= close"),
        Check(lambda df: df["date"].is_unique, error="dates must be unique per extract"),
    ],
    coerce=True,
    strict=True,
    name="ohlcv_schema",
)


def validate_ohlcv(df: pd.DataFrame) -> QualityReport:
    """Run Pandera schema + business-rule checks on OHLCV data."""
    checks = [
        "schema: ticker, date, ohlcv columns",
        "rule: high >= low/open/close",
        "rule: low <= open/close",
        "rule: unique dates",
    ]

    if df.empty:
        return QualityReport(passed=True, row_count=0, checks_run=checks)

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])

    try:
        OHLCV_SCHEMA.validate(working, lazy=True)
    except pa.errors.SchemaErrors as exc:
        messages = [str(err) for err in exc.failure_cases["check"].tolist()]
        return QualityReport(
            passed=False,
            row_count=len(df),
            checks_run=checks,
            errors=messages or [str(exc)],
        )

    return QualityReport(passed=True, row_count=len(df), checks_run=checks)


def assert_ohlcv_quality(df: pd.DataFrame) -> QualityReport:
    report = validate_ohlcv(df)
    if not report.passed:
        raise DataQualityError("; ".join(report.errors))
    return report
