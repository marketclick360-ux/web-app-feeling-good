"""
Setup contract.

A Setup is a fully objective, codeable trade idea. It must define, with no
subjective interpretation:
  * economic/behavioral hypothesis (why the edge might exist)
  * market-regime filter
  * entry condition + entry timing + order type
  * stop-loss level
  * planned initial target of NO LESS than 3R
  * time stop / invalidation condition
  * direction (long/short)

Setups emit `Signal` objects on CLOSED bars. The backtest engine decides fills
on the NEXT bar (entry timing), so a Setup can never act on the bar it is
evaluating. A Setup returns levels only; position sizing and risk controls are
applied separately by sizing.py.

The "planned target" is the order level placed at entry. The REALIZED winner
may be smaller than 3R when a time stop or trailing exit closes the trade
early — engine/metrics report planned-vs-realized separately so 3R is never
confused with the average winning return.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass
class Signal:
    symbol: str
    direction: Direction
    setup_name: str
    signal_time: pd.Timestamp     # timestamp of the CLOSED bar that triggered
    entry_ref: float              # reference price (e.g. breakout level / next open)
    stop: float                   # initial protective stop
    target: float                 # planned target (>= 3R by construction)
    planned_r_multiple: float     # planned reward / planned risk (>= 3.0)
    entry_order: str = "next_open"  # next_open | stop | limit
    time_stop_bars: int = 10      # max bars in trade (intraday->10d default)
    hypothesis: str = ""
    regime_at_signal: str = ""
    notes: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry_ref - self.stop)

    @property
    def reward_per_share(self) -> float:
        return abs(self.target - self.entry_ref)


class Setup(ABC):
    """Base class for all setup families."""

    name: str = "abstract"
    hypothesis: str = ""
    # Each setup's OBJECTIVE target rule is a reward-to-risk multiple chosen to
    # fit its hypothesis. The HARD design rule is target_r >= 3.0: any setup
    # whose realized planned target is below 3R is rejected before any
    # performance test (validation.MIN_PLANNED_R). Targets are not curve-fit to
    # manufacture a win rate — they are fixed by the setup's structure.
    target_r: float = 3.0
    direction_modes = (Direction.LONG, Direction.SHORT)

    #: parameters exposed for sensitivity analysis (name -> value)
    params: dict = {}

    def __init__(self, **overrides):
        self.params = {**self.default_params(), **overrides}

    @staticmethod
    def default_params() -> dict:
        return {}

    @abstractmethod
    def generate(self, df: pd.DataFrame, regime: pd.Series, symbol: str,
                 context: Optional[dict] = None) -> list:
        """Return a list of Signal objects for the enriched daily frame `df`.

        `df`      : indicator-enriched OHLCV (see indicators.enrich_daily)
        `regime`  : per-bar regime label series aligned to df.index
        `context` : optional dict with shared series, e.g.
                    {"benchmark": <enriched SPY df>, "sector": <enriched ETF df>,
                     "earnings_dates": <DatetimeIndex>}
        Implementations MUST only reference df rows up to and including the
        evaluated bar, and place entries for the NEXT bar.
        """

    # -- shared helpers ----------------------------------------------------
    def _planned_target(self, entry: float, stop: float, direction: Direction,
                        r: Optional[float] = None) -> float:
        r = r if r is not None else self.target_r
        risk = abs(entry - stop)
        return entry + r * risk if direction is Direction.LONG else entry - r * risk

    @staticmethod
    def _near_earnings(ts: pd.Timestamp, context: Optional[dict],
                       window_days: int = 10) -> bool:
        """True if `ts` is within `window_days` calendar days BEFORE an earnings
        date supplied in context. When no earnings calendar is available this
        returns False and the limitation must be disclosed in the report."""
        if not context:
            return False
        dates = context.get("earnings_dates")
        if dates is None or len(dates) == 0:
            return False
        horizon = ts + pd.Timedelta(days=window_days)
        return bool(((dates >= ts) & (dates <= horizon)).any())
