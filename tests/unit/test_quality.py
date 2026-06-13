import pandas as pd
import pytest

from stock_pipeline.quality import DataQualityError, assert_ohlcv_quality, validate_ohlcv


def test_validate_ohlcv_passes(sample_ohlcv_df):
    report = validate_ohlcv(sample_ohlcv_df)
    assert report.passed
    assert report.row_count == 2
    assert len(report.checks_run) >= 3


def test_validate_ohlcv_empty_passes():
    report = validate_ohlcv(pd.DataFrame())
    assert report.passed
    assert report.row_count == 0


def test_validate_ohlcv_fails_high_below_low(sample_ohlcv_df):
    bad = sample_ohlcv_df.copy()
    bad.loc[0, "high"] = 100.0
    bad.loc[0, "low"] = 200.0

    report = validate_ohlcv(bad)
    assert not report.passed
    assert report.errors


def test_assert_ohlcv_quality_raises(sample_ohlcv_df):
    bad = sample_ohlcv_df.copy()
    bad.loc[0, "volume"] = -1.0

    with pytest.raises(DataQualityError):
        assert_ohlcv_quality(bad)
