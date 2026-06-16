.PHONY: install lint test ingest validate clean dbt-run dbt-test dbt-parse dashboard docker-check docker-build docker-ingest docker-ingest-batch

IMAGE=stock-pipeline

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

dashboard:
	streamlit run src/stock_pipeline/dashboard/app.py

docker-check:
	@command -v docker >/dev/null 2>&1 || { \
		echo "Docker is not installed or not on PATH."; \
		echo "Install Docker Desktop: https://docs.docker.com/desktop/setup/install/mac-install/"; \
		echo "Open Docker Desktop and wait until it is running, then retry."; \
		exit 1; \
	}

docker-build: docker-check
	docker build -t $(IMAGE) .

docker-ingest: docker-check
	docker run --rm --env-file .env -v $(PWD)/data:/app/data $(IMAGE) \
		ingest $(TICKER) --start $(START) --end $(END) $(if $(SNOWFLAKE),--snowflake,)

docker-ingest-batch: docker-check
	docker run --rm --env-file .env -v $(PWD)/data:/app/data $(IMAGE) \
		ingest-batch config/tickers.example.txt --incremental --snowflake
