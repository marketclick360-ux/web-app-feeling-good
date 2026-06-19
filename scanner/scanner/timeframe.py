"""
Multi-day candle support (e.g. 2-day candles) without look-ahead or repainting.

Hypothesis being tested: a slower timeframe (2 trading days per candle) reduces
daily noise and may produce cleaner trends/pullbacks for some instruments than
the 1-day chart. This module lets you run the SAME setups and the SAME
validation gates on N-day candles so the evidence — not a hunch — decides.

Honesty guardrails (read before trusting any 2-day result):
  * Picking the timeframe per symbol by "what backtested best" is curve-fitting.
    It doubles the search space and inflates false positives. Choose ONE
    timeframe per run (a pre-registered rule, e.g. run ETFs on 1d and the
    broader stock universe on 2d as SEPARATE runs), and let the gates judge it.
  * Do NOT mix timeframes inside a single run: relative-strength setups compare
    each symbol to the benchmark, so symbol and benchmark must share a timeframe.
    `TimeframeAdapter` therefore applies one timeframe to every symbol it serves.
  * A 2-day candle is a NEW degree of freedom. If you accept a setup only after
    trying 1d AND 2d, count both as trials in the overfitting penalty.

No-look-ahead design:
  * Candles are built from CLOSED daily bars only (the adapter never returns a
    forming day). The most recent group is dropped unless it holds a full N
    closed daily bars, so the latest N-day candle is never a forming one.
  * Grouping is anchored to a fixed epoch by business-day ordinal, so a given
    calendar date ALWAYS lands in the same candle regardless of the requested
    window. Adding tomorrow's bar never re-buckets yesterday's candle
    (no repainting).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .data.base import BarsResult, DataAdapter, OHLCV_COLUMNS

# Fixed anchor so business-day ordinals are stable across runs/windows.
_EPOCH = np.datetime64("2000-01-03")  # a Monday


def resample_bars(df: pd.DataFrame, n_days: int, drop_incomplete: bool = True) -> pd.DataFrame:
    """Aggregate daily OHLCV into N-day candles (no look-ahead, no repainting).

    open=first, high=max, low=min, close=last, volume=sum. The candle is
    right-labeled at its last constituent day (matches the "closed period ends
    at t" contract). Grouping is deterministic per calendar date. When
    ``drop_incomplete`` the trailing group is dropped unless it has a full
    ``n_days`` closed bars, so the latest candle is never still forming.
    """
    if n_days <= 1 or df.empty:
        return df
    idx = df.index
    # Business-day ordinal from a fixed epoch → stable bucket per calendar date.
    days = idx.tz_convert("UTC").normalize().tz_localize(None).values.astype("datetime64[D]")
    ordinal = np.busday_count(_EPOCH, days)
    bucket = ordinal // n_days

    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "volume": "sum"}
    grouped = df.groupby(bucket, sort=True)
    out = grouped.agg(agg)[OHLCV_COLUMNS]
    # Right-label each candle at the last day in its group. Use positional
    # lookup into the original (tz-aware) index so the timezone is preserved
    # (grabbing `.values` would silently drop tz and break later comparisons).
    pos = np.arange(len(df))
    last_pos = pd.Series(pos).groupby(bucket, sort=True).max().to_numpy()
    out.index = df.index[last_pos]
    out.index.name = df.index.name

    if drop_incomplete and len(out):
        last_bucket = bucket[-1]
        if int((bucket == last_bucket).sum()) < n_days:
            out = out.iloc[:-1]
    return out


# Broad set of ETF tickers used to classify "ETF vs single-name stock". Not
# exhaustive; only affects the convenience timeframe-by-class helper, never the
# resampling math.
ETF_TICKERS = {
    "SPY", "SPLG", "VOO", "IVV", "QQQ", "QQQM", "IWM", "DIA", "VTI", "RSP",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLB", "XLU", "XLRE",
    "XLC", "SMH", "SOXX", "XBI", "IBB", "KRE", "ITB", "ARKK",
    "TLT", "IEF", "SHY", "HYG", "LQD", "AGG", "BND", "TIP",
    "GLD", "SLV", "GDX", "DBC", "USO", "UNG",
    "EEM", "EFA", "VEA", "VWO", "VNQ", "IEMG", "IYR",
}


def is_etf(symbol: str) -> bool:
    return symbol.upper() in ETF_TICKERS


class TimeframeAdapter(DataAdapter):
    """Wrap a base adapter and serve every symbol on a single N-day timeframe.

    One timeframe for the whole run keeps benchmark-relative setups coherent.
    To explore "stocks on 2d, ETFs on 1d", do two SEPARATE runs with different
    universes — not one mixed run.
    """

    def __init__(self, base: DataAdapter, n_days: int = 1):
        self.base = base
        self.n_days = int(n_days)
        self.name = f"{getattr(base, 'name', 'adapter')}@{self.n_days}d"
        self.survivorship_free = getattr(base, "survivorship_free", None)

    def get_bars(self, symbol: str, resolution: str, start: pd.Timestamp,
                 end: pd.Timestamp, as_of: Optional[pd.Timestamp] = None) -> BarsResult:
        res = self.base.get_bars(symbol, "1d", start=start, end=end, as_of=as_of)
        if self.n_days <= 1:
            return res
        df = resample_bars(res.df, self.n_days)
        return BarsResult(symbol=symbol, resolution=f"{self.n_days}d", df=df)

    def is_tradable(self, symbol: str, as_of: Optional[pd.Timestamp] = None) -> bool:
        return self.base.is_tradable(symbol, as_of)

    def adv_dollar(self, symbol: str, as_of: pd.Timestamp, window: int = 20) -> float:
        # Liquidity must be judged on raw DAILY volume, not aggregated candles.
        return self.base.adv_dollar(symbol, as_of, window)

    # Pass through anything else the base adapter exposes (e.g. current_status).
    def __getattr__(self, item):
        # Only reached when normal attribute lookup fails; avoid recursing on
        # the wrapped base before __init__ sets it.
        if item == "base":
            raise AttributeError(item)
        return getattr(self.base, item)


def wrap_timeframe(adapter: DataAdapter, n_days: int) -> DataAdapter:
    """Return the adapter unchanged for 1d, else a TimeframeAdapter."""
    if not n_days or int(n_days) <= 1:
        return adapter
    return TimeframeAdapter(adapter, int(n_days))
