"""
Stooq market-data adapter (free, no API key, no OAuth).

Stooq serves adjusted end-of-day OHLCV for U.S. stocks/ETFs as CSV over HTTPS,
which makes it the lowest-friction REAL data source: the only requirement is
that `stooq.com` is on the environment's network egress allowlist. No key, no
token, no browser login.

ADJUSTMENT METHODOLOGY (document in every report): Stooq U.S. daily data is
split- and dividend-adjusted. It is NOT survivorship-bias-free (no delisted
tickers), and intraday history is limited — so this adapter supports DAILY
bars only and survivorship bias must be disclosed as a limitation.
"""
from __future__ import annotations

import io
import os
import time
from typing import Optional

import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS

_URL = "https://stooq.com/q/d/l/"


class StooqAdapter(DataAdapter):
    name = "stooq"
    adjustment = "split- & dividend-adjusted daily (Stooq)"
    survivorship_free = False

    def __init__(self, cache_dir: str = ".stooq_cache", pause: float = 0.3,
                 max_retries: int = 3):
        self.cache_dir = cache_dir
        self.pause = pause
        self.max_retries = max_retries
        self.last_error = None   # "rate_limited" | "no_data" | None
        os.makedirs(cache_dir, exist_ok=True)

    def _stooq_symbol(self, symbol: str) -> str:
        s = symbol.lower()
        return s if "." in s else f"{s}.us"

    def _cache_path(self, symbol: str) -> str:
        return os.path.join(self.cache_dir, f"{symbol.upper()}_1d.csv")

    def _fetch(self, symbol: str) -> pd.DataFrame:
        cache = self._cache_path(symbol)
        # Only trust a cache file that holds REAL data (a valid CSV header).
        # Never read back a previously-cached error/rate-limit page.
        if os.path.exists(cache) and os.path.getsize(cache) > 0:
            cached = open(cache).read()
            if "Date,Open" in cached:
                text = cached
                return self._parse(text)

        import requests
        params = {"s": self._stooq_symbol(symbol), "i": "d"}
        text = ""
        rate_limited = False
        backoff = max(self.pause, 0.5)
        for _ in range(self.max_retries):
            resp = requests.get(_URL, params=params, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0"})
            body = resp.text or ""
            if resp.status_code == 200 and "Date,Open" in body:
                text = body
                break
            # Stooq returns a plain-text notice when it throttles bulk requests.
            if "Exceeded" in body or "limit" in body.lower():
                rate_limited = True
            time.sleep(backoff)
            backoff *= 2
        # Cache ONLY a valid response — never poison the cache with an error page.
        if "Date,Open" in text:
            with open(cache, "w") as fh:
                fh.write(text)
        time.sleep(self.pause)

        if "Date,Open" not in text:
            self.last_error = ("rate_limited" if rate_limited else "no_data")
            return pd.DataFrame(columns=OHLCV_COLUMNS,
                                index=pd.DatetimeIndex([], tz="UTC"))
        return self._parse(text)

    def _parse(self, text: str) -> pd.DataFrame:
        if "Date,Open" not in text:
            return pd.DataFrame(columns=OHLCV_COLUMNS,
                                index=pd.DatetimeIndex([], tz="UTC"))
        df = pd.read_csv(io.StringIO(text))
        df.columns = [c.lower() for c in df.columns]
        df["ts"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("ts").sort_index()
        return df[OHLCV_COLUMNS]

    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        if resolution != "1d":
            # Stooq intraday is unreliable; daily only (disclosed limitation).
            return BarsResult(symbol, resolution,
                              pd.DataFrame(columns=OHLCV_COLUMNS,
                                           index=pd.DatetimeIndex([], tz="UTC")))
        df = self._fetch(symbol)
        df = df.loc[(df.index >= start) & (df.index <= end)]
        if as_of is not None:
            df = df.loc[df.index <= as_of]
        return BarsResult(symbol, resolution, df.copy())

    def is_tradable(self, symbol, as_of=None) -> bool:
        try:
            return len(self._fetch(symbol)) > 0
        except Exception:
            return False
