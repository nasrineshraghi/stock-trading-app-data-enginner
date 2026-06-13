# Level 2 — Analytics, automation, and packaging

Level 1 got data **into** Snowflake. Level 2 makes the pipeline **production-shaped**: incremental loads, analytics models, scheduled runs, and a container.

| Block | Topic | Status |
|-------|--------|--------|
| 1 | Incremental loads (`--incremental`) | Done |
| 2 | dbt models on `STOCK_OHLCV` | **You are here** |
| 3 | Scheduled GitHub Actions (cron) | Next |
| 4 | Docker packaging | After cron |

---

## Block 2 — dbt on Snowflake

### Goal

Transform raw `STOCK_OHLCV` (loaded by Python) into **staging** and **mart** tables using [dbt](https://docs.getdbt.com/).

```
RAW_DATA_STOCK.STOCK_OHLCV  →  staging.stg_stock_ohlcv  →  marts.fct_stock_daily_returns
     (Python MERGE)                 (dbt view/table)              (dbt table)
```

### 2.1 Prerequisites

- Level 1 Snowflake load working (`stock-ingest ingest AAPL ... --snowflake`)
- Some rows in `STOCK_DB.RAW_DATA_STOCK.STOCK_OHLCV`
- dbt installed:

```bash
pip install -e ".[dbt,snowflake]"
cp dbt/profiles.yml.example dbt/profiles.yml   # or use --profiles-dir dbt
# Edit dbt/profiles.yml with your Snowflake creds (same as .env)
```

**Python 3.14 + dbt:** If `dbt` crashes with `mashumaro.exceptions.UnserializableField`, upgrade mashumaro:

```bash
pip install "mashumaro>=3.17"
dbt --version   # should print version, not a traceback
```

Alternatively use a **Python 3.12** venv for dbt (dbt’s best-tested runtime):

```bash
python3.12 -m venv .venv-dbt && source .venv-dbt/bin/activate
pip install -e ".[dbt,snowflake]"
```

### 2.2 Project layout

```
dbt/
├── dbt_project.yml
├── profiles.yml.example
├── models/
│   ├── sources.yml
│   ├── staging/
│   │   ├── stg_stock_ohlcv.sql
│   │   └── schema.yml
│   └── marts/
│       ├── fct_stock_daily_returns.sql
│       └── schema.yml
```

dbt writes to schemas **`STAGING`** and **`MARTS`** in the same database as raw data.

### 2.3 Run dbt

From the repo root (loads `.env` if exported, or set Snowflake env vars):

```bash
export $(grep -v '^#' .env | xargs)   # optional: load .env into shell

make dbt-run    # build models
make dbt-test   # run schema tests
```

Or directly:

```bash
cd dbt && dbt run --profiles-dir .
cd dbt && dbt test --profiles-dir .
```

### 2.4 Verify in Snowflake

```sql
SELECT COUNT(*) FROM STOCK_DB.RAW_DATA_STOCK.STOCK_OHLCV;
SELECT COUNT(*) FROM STOCK_DB.STAGING.STG_STOCK_OHLCV;
SELECT * FROM STOCK_DB.STAGING.STG_STOCK_OHLCV LIMIT 10;
SELECT * FROM STOCK_DB.MARTS.FCT_STOCK_DAILY_RETURNS
WHERE ticker = 'AAPL'
ORDER BY date DESC
LIMIT 10;
```

If raw has rows but `STAGING.STG_STOCK_OHLCV` is empty or missing, check you are not querying an old **`STAGING_STAGING`** schema from an earlier dbt run (before `macros/generate_schema_name.sql`). Re-run `make dbt-run` and use `STAGING` / `MARTS` as above.

### 2.5 Acceptance criteria

- [ ] `dbt run` succeeds
- [ ] `dbt test` passes (not_null on ticker, date, close)
- [ ] Mart shows `daily_return_pct` (NULL on first day per ticker, then % change)

---

## Block 3 preview — Scheduled ingest (cron)

Add `.github/workflows/scheduled-ingest.yml` to run nightly:

```yaml
on:
  schedule:
    - cron: "0 6 * * 1-5"   # 6 UTC, Mon–Fri
```

Use GitHub secrets for `POLYGON_API_KEY` and `SNOWFLAKE_*`, run:

```bash
stock-ingest ingest-batch config/tickers.example.txt --incremental --snowflake
```

---

## Block 4 preview — Docker

Wrap the CLI in a slim image, mount `.env` or inject secrets at runtime, use the same entrypoint as local:

```dockerfile
FROM python:3.12-slim
COPY . /app
RUN pip install -e ".[snowflake]"
ENTRYPOINT ["stock-ingest"]
```

---

## Level 2 complete — interview line

> "I built an incremental Python ELT pipeline into Snowflake raw layer, then used dbt for staging and mart models with tests, scheduled it with GitHub Actions, and packaged it in Docker."
