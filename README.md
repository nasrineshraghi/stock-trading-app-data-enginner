# Stock Data Pipeline

[![CI](https://github.com/nasrineshraghi/stock-trading-app-data-enginner/actions/workflows/ci.yml/badge.svg)](https://github.com/nasrineshraghi/stock-trading-app-data-enginner/actions/workflows/ci.yml)

Extract daily OHLCV stock bars from [Polygon.io](https://polygon.io), validate data quality, and save to CSV — with tests and CI/CD baked in.

## Architecture

```
Polygon.io API  →  Extract  →  Transform  →  Quality Checks  →  CSV (raw + processed)
```

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Extract | `stock_pipeline.extract.polygon` | Fetch aggregates from Polygon `/v2/aggs` |
| Transform | `stock_pipeline.transform.normalize` | Normalize to canonical OHLCV schema |
| Quality | `stock_pipeline.quality` | Pandera schema + OHLC business rules |
| Load | `stock_pipeline.load.csv_exporter` | Write versioned CSV files |
| Orchestration | `stock_pipeline.pipeline` | End-to-end ingestion workflow |

## Quick start

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Configure your API key

```bash
cp .env.example .env
# Edit .env and set POLYGON_API_KEY=your_key_here
```

### 3. Run ingestion

```bash
stock-ingest ingest AAPL --start 2024-01-01 --end 2024-01-31
```

Output files:

- `data/raw/AAPL_2024-01-01_2024-01-31.csv` — raw extract
- `data/processed/AAPL_2024-01-01_2024-01-31.csv` — quality-validated output

### 4. Validate an existing CSV

```bash
stock-ingest validate data/processed/AAPL_2024-01-01_2024-01-31.csv
```

## Data quality framework

Every ingestion run validates:

- **Schema**: required columns, types, non-null constraints
- **Bounds**: prices and volume ≥ 0
- **OHLC logic**: `high ≥ open/close/low`, `low ≤ open/close`
- **Uniqueness**: one row per date per extract

Failed checks block the processed CSV from being written and raise `DataQualityError`.

## Development

### Run tests locally before changes

From the project folder:

```bash
source .venv/bin/activate
```

If you haven't set up the environment yet:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Before you commit, run the same checks as CI:

```bash
make lint          # ruff — must pass with no errors
make test          # pytest with coverage (≥80% required in CI)
```

Or run them directly:

```bash
ruff check src tests
pytest tests/ --cov=stock_pipeline --cov-report=term-missing
```

Quick test run (no coverage report):

```bash
pytest tests/ -q
```

Typical workflow: edit code → `make lint` → `make test` → commit → push.

```bash
make ingest TICKER=AAPL START=2024-01-01 END=2024-01-31
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR:

1. **Lint** — `ruff check`
2. **Test** — unit + integration tests on Python 3.11 and 3.12
3. **Pipeline dry-run** — validates a sample CSV through the quality framework and CLI

To enable CI, push this repo to GitHub. Add `POLYGON_API_KEY` as a repository secret if you want live API smoke tests later.

## CSV schema

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

## Version control

- Source code and tests are tracked in git
- Generated CSVs in `data/raw/` and `data/processed/` are gitignored
- Directory structure is preserved via `.gitkeep`

## Next steps

- Add more tickers via a batch config file
- Schedule daily ingestion (cron / Airflow / GitHub Actions scheduled workflow)
- Store outputs in S3 or a data warehouse
- Add Great Expectations dashboards for quality reporting
