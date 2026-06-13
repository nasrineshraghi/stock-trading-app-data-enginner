from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


class PolygonExtractError(Exception):
    """Raised when Polygon.io extraction fails."""


@dataclass(frozen=True)
class AggregateBar:
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    transactions: int | None = None


class PolygonClient:
    """Thin wrapper around Polygon.io aggregates (OHLCV bars) endpoint."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.polygon.io",
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PolygonClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_aggregates(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        *,
        multiplier: int = 1,
        timespan: str = "day",
        adjusted: bool = True,
        limit: int = 50000,
    ) -> list[AggregateBar]:
        url = (
            f"{self.base_url}/v2/aggs/ticker/{ticker.upper()}/range/"
            f"{multiplier}/{timespan}/{start_date.isoformat()}/{end_date.isoformat()}"
        )
        params: dict[str, Any] = {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": limit,
            "apiKey": self.api_key,
        }

        response = self._client.get(url, params=params)
        if response.status_code != 200:
            raise PolygonExtractError(
                f"Polygon API error {response.status_code}: {response.text[:500]}"
            )

        payload = response.json()
        status = payload.get("status")
        if status not in {"OK", "DELAYED"}:
            raise PolygonExtractError(
                f"Unexpected Polygon status '{status}': {payload.get('error', payload)}"
            )

        results = payload.get("results") or []
        return [self._parse_bar(item) for item in results]

    @staticmethod
    def _parse_bar(item: dict[str, Any]) -> AggregateBar:
        return AggregateBar(
            timestamp_ms=int(item["t"]),
            open=float(item["o"]),
            high=float(item["h"]),
            low=float(item["l"]),
            close=float(item["c"]),
            volume=float(item["v"]),
            vwap=float(item["vw"]) if "vw" in item else None,
            transactions=int(item["n"]) if "n" in item else None,
        )
