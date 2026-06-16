# Streamlit dashboard

Interactive charts for OHLCV prices, daily returns, and volume — backed by your **dbt mart** in Snowflake or local processed CSVs.

## Install

```bash
pip install -e ".[dashboard,snowflake]"
```

## Run

```bash
make dashboard
# or:
streamlit run src/stock_pipeline/dashboard/app.py
```

Opens in the browser (default `http://localhost:8501`).

## Data sources

| Mode | Reads from |
|------|------------|
| **Auto** (default) | Snowflake `MARTS.FCT_STOCK_DAILY_RETURNS`, falls back to `data/processed/*.csv` |
| **Snowflake** | Mart only (requires `.env` Snowflake vars + `make dbt-run`) |
| **CSV** | Processed CSV files only |

Use **Refresh data** in the sidebar after a new ingest or dbt run.

## Prerequisites

**Snowflake path (recommended):**

```bash
stock-ingest ingest-batch config/tickers.example.txt --incremental --snowflake
make dbt-run
make dashboard
```

**CSV-only path:**

```bash
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-10
make dashboard
```

Select **Processed CSV only** in the sidebar if Snowflake is not configured.

## What you see

- **Prices** — closing price over time (multi-ticker)
- **Candlestick** — OHLC for one ticker
- **Returns** — daily `%` change from dbt (or computed from CSV)
- **Volume** — share volume by day
- **Table** — full mart-shaped data

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty mart | Run `make dbt-run` after raw data exists in Snowflake |
| Snowflake auth error | Check `.env` matches `dbt/profiles.yml` credentials |
| No CSV files | Run `stock-ingest ingest ...` first |
| `streamlit: command not found` | `pip install -e ".[dashboard]"` |
