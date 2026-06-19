"""
Data adapter contract.

Every adapter returns a pandas DataFrame indexed by timezone-aware timestamp
(UTC) with columns: open, high, low, close, volume. Prices MUST be
split- and dividend-adjusted ("adjusted OHLCV"). Volume is split-adjusted.

Design rules that protect against look-ahead / leakage:
  * Bars are right-labeled and represent CLOSED periods only. A bar with
    timestamp t covers the interval ending at t and is only "knowable" at t.
  * Adapters must never return a forming (incomplete) bar for the current
    period. `as_of` lets callers pin the latest knowable bar for backtests.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
VALID_RESOLUTIONS = {"1d", "1h", "15m"}


@dataclass
class BarsResult:
    """OHLCV bars for a single symbol at a single resolution."""

    symbol: str
    resolution: str
    df: pd.DataFrame  # index: tz-aware UTC timestamps; cols: OHLCV_COLUMNS

    def __post_init__(self) -> None:
        missing = [c for c in OHLCV_COLUMNS if c not in self.df.columns]
        if missing:
            raise ValueError(f"{self.symbol}: missing columns {missing}")
        if not self.df.index.is_monotonic_increasing:
            raise ValueError(f"{self.symbol}: bar index must be sorted ascending")
        if self.df.index.has_duplicates:
            raise ValueError(f"{self.symbol}: duplicate timestamps present")


class DataAdapter(ABC):
    """Base class for all market-data sources."""

    name: str = "abstract"
    #: True if delisted tickers / point-in-time constituents are available
    #: (survivorship-bias-free); False if not; None if unknown.
    survivorship_free = None

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        resolution: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        as_of: Optional[pd.Timestamp] = None,
    ) -> BarsResult:
        """Return adjusted OHLCV bars in [start, end].

        If `as_of` is provided, no bar with timestamp > as_of is returned
        (this is the primary defense against look-ahead in backtests).
        """

    @abstractmethod
    def is_tradable(self, symbol: str, as_of: Optional[pd.Timestamp] = None) -> bool:
        """True if the symbol existed and was tradable at `as_of` (delisting aware)."""

    def adv_dollar(self, symbol: str, as_of: pd.Timestamp, window: int = 20) -> float:
        """Average daily dollar volume over the trailing `window` daily bars."""
        bars = self.get_bars(
            symbol,
            "1d",
            start=as_of - pd.Timedelta(days=window * 3 + 10),
            end=as_of,
            as_of=as_of,
        ).df
        if bars.empty:
            return 0.0
        tail = bars.tail(window)
        return float((tail["close"] * tail["volume"]).mean())
