"""
Position sizing and portfolio risk controls.

Sizing is fixed-fractional on PLANNED risk (entry-to-stop distance), never on
notional. Risk controls below default to the user-selected MODERATE profile and
can be overridden. The engine consults `RiskController` before opening any
trade so portfolio-level limits (total open risk, sector cap, position count,
daily/weekly loss limits) are enforced, not just per-trade risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd


@dataclass
class RiskConfig:
    # MODERATE defaults (user-selected)
    risk_per_trade_pct: float = 0.01        # 1.0% of equity per trade
    max_total_open_risk_pct: float = 0.06   # 6% aggregate planned open risk
    max_sector_risk_pct: float = 0.08       # 8% correlated exposure per sector
    max_positions: int = 8
    daily_loss_limit_r: float = 3.0         # halt new entries after -3R on the day
    weekly_loss_limit_r: float = 6.0
    # Stressed open risk uses a gap-tail multiplier on planned risk:
    gap_tail_multiplier: float = 1.5
    max_stressed_open_risk_pct: float = 0.09


def shares_for_trade(equity: float, entry: float, stop: float,
                     cfg: RiskConfig) -> int:
    """Whole-share count so that (entry-stop)*shares ≈ risk_per_trade_pct*equity."""
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return 0
    dollar_risk = equity * cfg.risk_per_trade_pct
    return int(dollar_risk // risk_per_share)


@dataclass
class OpenPosition:
    symbol: str
    sector: str
    planned_risk_dollars: float


@dataclass
class RiskController:
    cfg: RiskConfig = field(default_factory=RiskConfig)
    sector_map: Dict[str, str] = field(default_factory=dict)

    _open: Dict[str, OpenPosition] = field(default_factory=dict)
    _day_pnl_r: float = 0.0
    _week_pnl_r: float = 0.0
    _cur_day: object = None
    _cur_week: object = None

    def _sector(self, symbol: str) -> str:
        return self.sector_map.get(symbol.upper(), "UNKNOWN")

    def roll_clock(self, ts: pd.Timestamp):
        day, week = ts.date(), ts.isocalendar()[:2]
        if self._cur_day != day:
            self._cur_day, self._day_pnl_r = day, 0.0
        if self._cur_week != week:
            self._cur_week, self._week_pnl_r = week, 0.0

    def can_open(self, symbol: str, equity: float, planned_risk_dollars: float):
        """Return (allowed: bool, reason: str)."""
        if len(self._open) >= self.cfg.max_positions:
            return False, "max_positions"
        if symbol in self._open:
            return False, "already_open"  # no pyramiding / averaging
        if self._day_pnl_r <= -self.cfg.daily_loss_limit_r:
            return False, "daily_loss_limit"
        if self._week_pnl_r <= -self.cfg.weekly_loss_limit_r:
            return False, "weekly_loss_limit"

        cur_risk = sum(p.planned_risk_dollars for p in self._open.values())
        if (cur_risk + planned_risk_dollars) > self.cfg.max_total_open_risk_pct * equity:
            return False, "max_total_open_risk"
        stressed = (cur_risk + planned_risk_dollars) * self.cfg.gap_tail_multiplier
        if stressed > self.cfg.max_stressed_open_risk_pct * equity:
            return False, "max_stressed_open_risk"

        sec = self._sector(symbol)
        sec_risk = sum(p.planned_risk_dollars for p in self._open.values()
                       if p.sector == sec)
        if (sec_risk + planned_risk_dollars) > self.cfg.max_sector_risk_pct * equity:
            return False, "max_sector_risk"
        return True, "ok"

    def open(self, symbol: str, planned_risk_dollars: float):
        self._open[symbol] = OpenPosition(symbol, self._sector(symbol),
                                          planned_risk_dollars)

    def close(self, symbol: str, realized_r: float):
        self._open.pop(symbol, None)
        self._day_pnl_r += realized_r
        self._week_pnl_r += realized_r
