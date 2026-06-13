from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


def build_output_path(
    output_dir: Path,
    ticker: str,
    start_date: date,
    end_date: date,
    *,
    stage: str = "processed",
) -> Path:
    filename = f"{ticker.upper()}_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    return output_dir / stage / filename


def export_dataframe(df: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path
