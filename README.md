# Stock Data Pipeline

[![CI](https://github.com/nasrineshraghi/stock-trading-app-data-enginner/actions/workflows/ci.yml/badge.svg)](https://github.com/nasrineshraghi/stock-trading-app-data-enginner/actions/workflows/ci.yml)

Extract daily OHLCV stock bars from [Polygon.io](https://polygon.io), validate data quality, save to CSV, and optionally load into Snowflake — with tests and CI/CD baked in.

**Practice guide:** see [docs/LEVEL1.md](docs/LEVEL1.md) for step-by-step production-ready exercises (logging, batch ingest, Snowflake upsert, CI quality gates).

## Architecture

```
Polygon.io API  →  Extract  →  Transform  →  Quality Checks  →  CSV (raw + processed)  →  Snowflake (optional)
```

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Extract | `stock_pipeline.extract.polygon` | Fetch aggregates from Polygon `/v2/aggs` |
| Transform | `stock_pipeline.transform.normalize` | Normalize to canonical OHLCV schema |
| Quality | `stock_pipeline.quality` | Pandera schema + OHLC business rules |
| Load | `stock_pipeline.load.csv_exporter` | Write versioned CSV files |
| Load | `stock_pipeline.load.snowflake_loader` | Upsert validated rows to Snowflake |
| Orchestration | `stock_pipeline.pipeline` | End-to-end ingestion workflow |
| CLI | `stock_pipeline.cli` | `stock-ingest ingest` and `stock-ingest validate` |

## API reference

This pipeline uses the Polygon.io aggregates (OHLCV bars) REST API. For endpoint details, parameters, and response formats, see the [Massive Stocks REST API documentation](https://massive.com/docs/rest/stocks/overview).

The client calls:

```
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
```

## Quick start

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

For Snowflake loading, also install:

```bash
pip install -e ".[snowflake]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
POLYGON_API_KEY=your_key_here
```

**Important:** put real secrets in `.env` only (gitignored). Keep `.env.example` as placeholders.

If your password contains `#` or other special characters, wrap it in quotes:

```bash
SNOWFLAKE_PASSWORD="your#password"
```

### 3. Run ingestion (CSV)

Use dates within your Polygon plan window (free tier is typically ~2 years of history):

```bash
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-05
```

Output files:

- `data/raw/AAPL_2025-06-01_2025-06-05.csv` — normalized extract
- `data/processed/AAPL_2025-06-01_2025-06-05.csv` — quality-validated output

Success output:

```
Ingested 3 rows for AAPL
Raw CSV:        data/raw/AAPL_2025-06-01_2025-06-05.csv
Processed CSV:  data/processed/AAPL_2025-06-01_2025-06-05.csv
Quality checks: schema: ticker, date, ohlcv columns, ...
```

### 4. Validate an existing CSV

```bash
stock-ingest validate data/processed/AAPL_2025-06-01_2025-06-05.csv
```

### 5. Load into Snowflake (optional)

Add Snowflake settings to `.env`:

```bash
SNOWFLAKE_ACCOUNT=your_org-your_account
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=STOCK_DB
SNOWFLAKE_SCHEMA=RAW_DATA_STOCK
SNOWFLAKE_TABLE=STOCK_OHLCV
```

Create objects in Snowflake (run once):

```sql
CREATE DATABASE IF NOT EXISTS STOCK_DB;
CREATE SCHEMA IF NOT EXISTS STOCK_DB.RAW_DATA_STOCK;

CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

GRANT USAGE ON WAREHOUSE COMPUTE_WH TO USER your_username;
GRANT USAGE ON DATABASE STOCK_DB TO USER your_username;
GRANT USAGE ON SCHEMA STOCK_DB.RAW_DATA_STOCK TO USER your_username;
GRANT CREATE TABLE ON SCHEMA STOCK_DB.RAW_DATA_STOCK TO USER your_username;
GRANT INSERT ON ALL TABLES IN SCHEMA STOCK_DB.RAW_DATA_STOCK TO USER your_username;
```

Run ingest with the Snowflake flag:

```bash
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-05 --snowflake
```

Verify in Snowflake:

```sql
SELECT * FROM STOCK_DB.RAW_DATA_STOCK.STOCK_OHLCV ORDER BY DATE;
```

The table `STOCK_OHLCV` is created automatically on first load if it does not exist.

## Data cleaning pipeline

In one pass, the pipeline:

1. **Parses** Polygon API responses into typed bar objects
2. **Standardizes** to a fixed OHLCV schema (`bars_to_dataframe`)
3. **Deduplicates** by `ticker + date` (keeps last row)
4. **Validates** OHLC business rules (Pandera)
5. **Writes** raw and processed CSV files
6. **Loads** to Snowflake when `--snowflake` is used (append)

Failed quality checks raise `DataQualityError` and block the processed CSV.

## Data quality framework

Every ingestion run validates:

- **Schema**: required columns, types, non-null constraints
- **Bounds**: prices and volume ≥ 0
- **OHLC logic**: `high ≥ open/close/low`, `low ≤ open/close`
- **Uniqueness**: one row per date per extract

## Development

### Run tests locally before changes

```bash
source .venv/bin/activate
make lint
make test
```

Or run directly:

```bash
python -m ruff check src tests
python -m pytest tests/ --cov=stock_pipeline --cov-report=term-missing
```

Quick test run:

```bash
python -m pytest tests/ -q
```

Typical workflow: edit code → `make lint` → `make test` → commit → push.

Makefile shortcuts:

```bash
make install
make lint
make test
make ingest TICKER=AAPL START=2025-06-01 END=2025-06-05
make validate FILE=data/processed/AAPL_2025-06-01_2025-06-05.csv
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR:

1. **Lint** — `ruff check`
2. **Test** — unit + integration tests on Python 3.11 and 3.12
3. **Pipeline dry-run** — validates a sample CSV through the quality framework and CLI

Uses `actions/checkout@v6` and `actions/setup-python@v6` (Node.js 24 compatible).

CI does **not** require `POLYGON_API_KEY` or Snowflake credentials — tests use mocks.

## CSV / Snowflake schema

| Column | Type | Description |
|--------|------|-------------|
| ticker | string | Symbol (e.g. AAPL) |
| date | date | Trading date (UTC) |
| open, high, low, close | float | OHLC prices |
| volume | float | Share volume |
| vwap | float | Volume-weighted average price |
| transactions | int | Number of transactions |
| source | string | Always `polygon.io` |
| ingested_at | string | ISO timestamp of extraction |

## Project layout

```
src/stock_pipeline/
├── cli.py                 # CLI entry point
├── config.py              # .env settings (Polygon + Snowflake)
├── pipeline.py            # Orchestrates extract → transform → quality → load
├── extract/polygon.py     # Polygon API client
├── transform/normalize.py # bars_to_dataframe()
├── quality/__init__.py    # Pandera OHLCV validation
└── load/
    ├── csv_exporter.py    # CSV output
    └── snowflake_loader.py # Snowflake append load

tests/
├── unit/                  # Module-level tests
├── integration/           # End-to-end pipeline tests
└── fixtures/              # Sample Polygon API JSON
```

## Version control

- Source code and tests are tracked in git
- `.env` and generated CSVs are gitignored
- Directory structure is preserved via `.gitkeep`

## Next steps

- Add batch ingestion for multiple tickers
- Schedule daily ingestion (cron / Airflow / GitHub Actions scheduled workflow)
- Upsert into Snowflake to avoid duplicate dates on re-runs
- Add Great Expectations dashboards for quality reporting
