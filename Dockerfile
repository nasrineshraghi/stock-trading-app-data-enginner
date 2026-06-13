FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[snowflake]"

ENV DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1

RUN mkdir -p /app/data/raw /app/data/processed

ENTRYPOINT ["stock-ingest"]
CMD ["--help"]
