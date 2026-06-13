# Level 1 — Production-Ready Practice Guide

This guide walks through five improvements that turn the stock pipeline from a learning project into something closer to a real data job. Do them **in order**.

---

## Overview

| Step | Skill you practice | Time estimate |
|------|-------------------|---------------|
| 1. Snowflake end-to-end | Cloud warehouse load + verification | 1–2 hours |
| 2. Structured logging | Operability, debugging production runs | 30 min |
| 3. Multi-ticker ingest | Batch processing, partial failures | 1 hour |
| 4. Snowflake upsert | Idempotent loads (no duplicates) | 1 hour |
| 5. Quality gate in CI | Fail fast when data is bad | 30 min |

---

## Step 1 — Run Snowflake end-to-end

**Goal:** Prove data flows from Polygon → Python → Snowflake table.

### 1.1 Prerequisites checklist

- [ ] `.env` has Polygon key and all `SNOWFLAKE_*` variables
- [ ] `pip install -e ".[snowflake]"` completed
- [ ] Snowflake database, schema, warehouse exist
- [ ] Your user has `USAGE`, `CREATE TABLE`, `INSERT` grants

### 1.2 Create Snowflake objects (run once)

```sql
CREATE DATABASE IF NOT EXISTS STOCK_DB;
CREATE SCHEMA IF NOT EXISTS STOCK_DB.RAW_DATA_STOCK;

CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;
```

Replace `your_username` with your Snowflake user:

```sql
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO USER your_username;
GRANT USAGE ON DATABASE STOCK_DB TO USER your_username;
GRANT USAGE ON SCHEMA STOCK_DB.RAW_DATA_STOCK TO USER your_username;
GRANT CREATE TABLE ON SCHEMA STOCK_DB.RAW_DATA_STOCK TO USER your_username;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA STOCK_DB.RAW_DATA_STOCK TO USER your_username;
```

### 1.3 Run ingest with Snowflake

```bash
source .venv/bin/activate
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-05 --snowflake -v
```

The `-v` flag turns on verbose logging (see Step 2).

**Success output includes:**

```
Snowflake table: STOCK_DB.RAW_DATA_STOCK.STOCK_OHLCV (N rows loaded)
```

### 1.4 Verify in Snowflake

```sql
SELECT TICKER, DATE, OPEN, HIGH, LOW, CLOSE, VOLUME
FROM STOCK_DB.RAW_DATA_STOCK.STOCK_OHLCV
ORDER BY DATE;
```

### 1.5 Acceptance criteria

- [ ] Row count in Snowflake matches terminal output
- [ ] OHLC values look reasonable (high ≥ low, etc.)
- [ ] Re-running the same command does **not** duplicate rows (after Step 4 upsert)

### 1.6 If it fails

| Error | What to check |
|-------|----------------|
| Account not found | `SNOWFLAKE_ACCOUNT` format (`ORG-ACCOUNT`) |
| Warehouse suspended | Run a query in Snowflake UI to wake it |
| Insufficient privileges | Re-run `GRANT` statements |
| Package missing | `pip install -e ".[snowflake]"` |

---

## Step 2 — Structured logging

**Goal:** See what the pipeline did at each stage, not just final echo lines.

### 2.1 What was added

Logging uses Python's standard `logging` module with this format:

```
2026-06-13 15:30:00 | INFO | stock_pipeline.pipeline | Extracted 3 bars for AAPL
```

Key log points:

| Stage | Log message |
|-------|-------------|
| Extract | `Extracted N bars for TICKER` |
| Transform | `Normalized to N rows for TICKER` |
| Raw CSV | `Wrote raw CSV: path` |
| Quality | `Quality checks passed for TICKER (N rows)` |
| Processed CSV | `Wrote processed CSV: path` |
| Snowflake | `Upserted N rows into DB.SCHEMA.TABLE` |
| Batch | `Batch complete: X succeeded, Y failed` |

### 2.2 Try it

```bash
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-05 -v
```

Without `-v`, you still get INFO logs. With `-v`, you get DEBUG detail (API URLs, etc.).

### 2.3 Practice exercise

1. Run with `-v` and identify **5 log lines** matching the table above
2. Break quality on purpose: edit a processed CSV so `high < low`, run `stock-ingest validate` — see FAIL output
3. **Interview prep:** explain why logs go to stderr, not stdout

### 2.4 Acceptance criteria

- [ ] You can trace extract → transform → quality → load from logs alone
- [ ] Failed runs log the error before exiting

---

## Step 3 — Multi-ticker ingest

**Goal:** Ingest many symbols in one run, like a nightly batch job.

### 3.1 Option A — multiple tickers on CLI

```bash
stock-ingest ingest AAPL MSFT GOOG --start 2025-06-01 --end 2025-06-05
```

With Snowflake:

```bash
stock-ingest ingest AAPL MSFT GOOG --start 2025-06-01 --end 2025-06-05 --snowflake
```

### 3.2 Option B — tickers file

```bash
cp config/tickers.example.txt config/tickers.txt
# edit config/tickers.txt
stock-ingest ingest-batch config/tickers.txt --start 2025-06-01 --end 2025-06-05 --snowflake
```

### 3.3 How it behaves (production pattern)

- One shared API client for all tickers (efficient)
- If **one** ticker fails, others still run
- Exit code `1` if **any** ticker failed
- Summary printed at the end

### 3.4 Practice exercise

1. Ingest 3 tickers to CSV only — confirm 3 file pairs in `data/raw/` and `data/processed/`
2. Ingest 3 tickers with `--snowflake` — confirm 3× rows (or merged rows) in Snowflake
3. Add a fake ticker `FAKE123` to your file — observe partial failure handling

### 3.5 Acceptance criteria

- [ ] 3 tickers produce 3 processed CSVs
- [ ] Batch summary shows succeeded + failed counts
- [ ] One bad ticker does not stop the whole batch

---

## Step 4 — Snowflake upsert (no duplicates)

**Goal:** Re-running the same ingest **updates** existing rows instead of duplicating.

### 4.1 What changed

Loads now use **MERGE** on `(TICKER, DATE)`:

1. Write batch to a staging table (`STOCK_OHLCV_STAGING`)
2. `MERGE INTO STOCK_OHLCV` — update if exists, insert if new
3. Truncate staging

### 4.2 Practice exercise

```bash
# First run
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-05 --snowflake

# Check count
# In Snowflake: SELECT COUNT(*) FROM STOCK_DB.RAW_DATA_STOCK.STOCK_OHLCV;

# Second run (same dates)
stock-ingest ingest AAPL --start 2025-06-01 --end 2025-06-05 --snowflake

# Count should be THE SAME, not doubled
```

### 4.3 Acceptance criteria

- [ ] Row count stable after second identical run
- [ ] Logs say `Upserted` not just `Appended`
- [ ] You can explain MERGE vs INSERT to someone else

---

## Step 5 — Quality gate in CI

**Goal:** Automated check that **bad data is rejected** — not only that good data passes.

### 5.1 What CI now does

On every push/PR, in addition to tests:

1. **Good sample** — must pass validation
2. **Bad sample** (high < low) — must **fail** validation

If someone breaks the quality rules, CI catches it.

### 5.2 Run the same check locally

```bash
make test
make lint
```

Or manually:

```python
from stock_pipeline.quality import validate_ohlcv
import pandas as pd

bad = pd.DataFrame({
    "ticker": ["AAPL"],
    "date": pd.to_datetime(["2024-01-02"]),
    "open": [150.0], "high": [140.0], "low": [149.0], "close": [151.0],
    "volume": [1_000_000.0], "vwap": [150.0], "transactions": [1000],
    "source": ["polygon.io"], "ingested_at": ["2024-06-01T00:00:00+00:00"],
})
assert not validate_ohlcv(bad).passed
print("Quality gate works")
```

### 5.3 Acceptance criteria

- [ ] GitHub Actions green on `main`
- [ ] You understand CI as an automated "data contract enforcer"

---

## Level 1 complete — what you can say in an interview

> "I built a Python ELT pipeline that ingests stock OHLCV from a REST API, validates with Pandera business rules, writes raw and processed CSVs, upserts into Snowflake on ticker+date, supports multi-ticker batch runs with structured logging, and has CI that rejects invalid data."

---

## What's next (Level 2 preview)

- dbt models on top of `STOCK_OHLCV`
- Incremental loads (only new dates since last run)
- Scheduled GitHub Actions cron
- Docker packaging

See the main [README](../README.md) for setup reference.
