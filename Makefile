.PHONY: install lint test ingest validate clean

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check src tests

test:
	pytest tests/ --cov=stock_pipeline --cov-report=term-missing

ingest:
	stock-ingest ingest $(TICKER) --start $(START) --end $(END)

validate:
	stock-ingest validate $(FILE)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/
