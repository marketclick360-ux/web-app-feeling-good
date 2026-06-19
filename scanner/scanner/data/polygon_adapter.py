"""
Polygon.io adapter (recommended primary source for rigorous validation).

Why Polygon for this project:
  * Adjusted OHLCV at daily and intraday resolutions (1m -> aggregated).
  * Survivorship-bias-free: delisted tickers remain queryable, so an
    as-of universe can be rebuilt without look-ahead.
  * Splits and dividends endpoints for corporate-action handling.

Requires `pip install requests` and an API key:
    export POLYGON_API_KEY=...

This adapter requests ADJUSTED bars (adjusted=true) so prices already account
for splits/dividends. It caches responses on disk to keep backtests
reproducible and to avoid hammering the rate limit.

NOTE: network calls are intentionally isolated here. The rest of the package
never imports `requests`, so the scanner runs fully offline with the CSV or
synthetic adapters.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional

import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS

_RES_TO_POLY = {
    "1d": (1, "day"),
    "1h": (1, "hour"),
    "15m": (15, "minute"),
}
_BASE = "https://api.polygon.io"


class PolygonAdapter(DataAdapter):
    name = "polygon"

    def __init__(self, api_key: Optional[str] = None, cache_dir: str = ".polygon_cache",
                 max_retries: int = 4, pause: float = 0.25):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "POLYGON_API_KEY not set. Export it or pass api_key=. "
                "Alternatively use the csv or synthetic adapter (no key needed)."
            )
        self.cache_dir = cache_dir
        self.max_retries = max_retries
        self.pause = pause
        os.makedirs(cache_dir, exist_ok=True)

    # -- low level ---------------------------------------------------------
    def _get(self, url: str, params: dict) -> dict:
        import requests  # local import keeps the dependency optional

        params = {**params, "apiKey": self.api_key}
        backoff = self.pause
        for attempt in range(self.max_retries):
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:  # rate limited
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Polygon request failed after retries: {url}")

    def _cache_path(self, symbol, resolution, start, end) -> str:
        key = f"{symbol}_{resolution}_{start.date()}_{end.date()}.json"
        return os.path.join(self.cache_dir, key.replace("/", "_"))

    # -- public ------------------------------------------------------------
    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        if resolution not in _RES_TO_POLY:
            raise ValueError(f"unsupported resolution {resolution}")
        mult, span = _RES_TO_POLY[resolution]
        cache = self._cache_path(symbol, resolution, start, end)

        if os.path.exists(cache):
            with open(cache) as fh:
                payload = json.load(fh)
        else:
            url = (f"{_BASE}/v2/aggs/ticker/{symbol.upper()}/range/{mult}/{span}/"
                   f"{start.date()}/{end.date()}")
            payload = self._get(url, {"adjusted": "true", "sort": "asc", "limit": 50000})
            with open(cache, "w") as fh:
                json.dump(payload, fh)
            time.sleep(self.pause)

        results = payload.get("results", []) or []
        if not results:
            empty = pd.DataFrame(columns=OHLCV_COLUMNS,
                                 index=pd.DatetimeIndex([], tz="UTC"))
            return BarsResult(symbol, resolution, empty)

        df = pd.DataFrame(results)
        df["ts"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                                "c": "close", "v": "volume"})
        df = df.set_index("ts").sort_index()[OHLCV_COLUMNS]
        df = df.loc[(df.index >= start) & (df.index <= end)]
        if as_of is not None:
            df = df.loc[df.index <= as_of]
        return BarsResult(symbol, resolution, df.copy())

    def is_tradable(self, symbol, as_of=None) -> bool:
        try:
            info = self._get(f"{_BASE}/v3/reference/tickers/{symbol.upper()}", {})
        except Exception:
            return False
        res = info.get("results", {})
        if not res:
            return False
        if as_of is not None and res.get("delisted_utc"):
            return as_of < pd.Timestamp(res["delisted_utc"])
        return bool(res.get("active", True))
