"""
Yahoo Finance adapter (free, no API key, no signup) via the `yfinance` library.

Why this exists: stooq throttles bursts and some Massive plans don't include
data access. Yahoo is the lowest-friction reliable free daily source — no key,
no OAuth, and it handles many tickers per run without the stooq rate-limit wall.

ADJUSTMENT: uses auto-adjusted OHLCV (split- & dividend-adjusted). NOT
survivorship-bias-free (no delisted tickers). Daily bars only here.

Requires:  pip install yfinance
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS


class YahooAdapter(DataAdapter):
    name = "yahoo"
    adjustment = "Yahoo auto-adjusted daily (split & dividend)"
    survivorship_free = False

    def __init__(self, cache_dir: str = ".yahoo_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._mem = {}   # per-run in-memory cache: symbol -> full history frame

    def _full_history(self, symbol: str) -> pd.DataFrame:
        sym = symbol.upper()
        if sym in self._mem:
            return self._mem[sym]
        # disk cache, refreshed if older than ~1 day
        cache = os.path.join(self.cache_dir, f"{sym}.csv")
        fresh = (os.path.exists(cache)
                 and (pd.Timestamp.now() - pd.Timestamp(os.path.getmtime(cache), unit="s")
                      < pd.Timedelta(days=1)))
        if fresh:
            df = pd.read_csv(cache, index_col=0, parse_dates=True)
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            self._mem[sym] = df
            return df

        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "Yahoo source needs the yfinance library. Install it once:\n"
                "  python3 -m pip install yfinance") from exc

        hist = yf.Ticker(sym).history(period="max", auto_adjust=True)
        if hist is None or hist.empty:
            df = pd.DataFrame(columns=OHLCV_COLUMNS,
                              index=pd.DatetimeIndex([], tz="UTC"))
            self._mem[sym] = df
            return df
        hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                    "Close": "close", "Volume": "volume"})
        idx = pd.to_datetime(hist.index, utc=True)
        df = pd.DataFrame({c: hist[c].to_numpy() for c in OHLCV_COLUMNS}, index=idx)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        try:
            df.to_csv(cache)
        except OSError:
            pass
        self._mem[sym] = df
        return df

    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        if resolution != "1d":
            return BarsResult(symbol, resolution,
                              pd.DataFrame(columns=OHLCV_COLUMNS,
                                           index=pd.DatetimeIndex([], tz="UTC")))
        df = self._full_history(symbol)
        if not df.empty:
            df = df.loc[(df.index >= start) & (df.index <= end)]
            if as_of is not None:
                df = df.loc[df.index <= as_of]
        return BarsResult(symbol, resolution, df.copy())

    def is_tradable(self, symbol, as_of=None) -> bool:
        try:
            return len(self._full_history(symbol)) > 0
        except Exception:
            return False
