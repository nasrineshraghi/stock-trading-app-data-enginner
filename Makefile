.PHONY: install lint test ingest validate clean dbt-run dbt-test dbt-parse

install:
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check src tests

test:
	python -m pytest tests/ --cov=stock_pipeline --cov-report=term-missing

ingest:
	stock-ingest ingest $(TICKER) --start $(START) --end $(END)

ingest-batch:
	stock-ingest ingest-batch config/tickers.txt --start $(START) --end $(END)

validate:
	stock-ingest validate $(FILE)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/

DBT_DIR=dbt

dbt-run:
	cd $(DBT_DIR) && dbt run --profiles-dir .

dbt-test:
	cd $(DBT_DIR) && dbt test --profiles-dir .

dbt-parse:
	cd $(DBT_DIR) && dbt parse --profiles-dir .
