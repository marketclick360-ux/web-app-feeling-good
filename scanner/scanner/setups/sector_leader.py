"""
Sector-leader continuation.

Hypothesis: a stock that is leading its own sector (relative strength vs the
sector ETF making new highs) while that sector is itself in an uptrend tends to
continue when it breaks to a new short-term high — money rotates toward the
leaders of leading groups.

Requires the stock's sector ETF close series in context["sector_close"][symbol].
If unavailable, the family returns nothing and that is disclosed as a limitation
(the relative-strength-vs-sector edge cannot be evaluated without sector data).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction
from .. import indicators as ind


class SectorLeaderContinuation(Setup):
    name = "sector_leader_continuation"
    hypothesis = ("Leaders of leading sectors continue: RS-vs-sector new high + "
                  "sector ETF uptrend + price breakout.")
    direction_modes = (Direction.LONG,)  # leadership continuation is long-biased

    @staticmethod
    def default_params() -> dict:
        return {
            "rs_lookback": 40,
            "breakout_lookback": 10,
            "atr_stop_mult": 1.5,
            "planned_r": 2.5,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        sector_close = None
        if context and "sector_close" in context:
            sector_close = context["sector_close"].get(symbol.upper())
        if sector_close is None:
            return []

        sec = sector_close.reindex(df.index).ffill()
        sec_sma200 = ind.sma(sec, 200)
        rs = df["close"] / (sec + 1e-12)
        rs_high_prev = ind.rolling_high_prev(rs, p["rs_lookback"])
        brk_high_prev = ind.rolling_high_prev(df["high"], p["breakout_lookback"])

        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(rs_high_prev.iloc[i]) or pd.isna(sec_sma200.iloc[i]) \
                    or pd.isna(brk_high_prev.iloc[i]) or pd.isna(row.get("sma50")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"

            sector_up = sec.iloc[i] > sec_sma200.iloc[i]
            rs_leader = rs.iloc[i] > rs_high_prev.iloc[i]
            price_break = row["close"] > brk_high_prev.iloc[i]
            stock_up = row["close"] > row["sma50"]

            if sector_up and rs_leader and price_break and stock_up:
                entry = float(nxt["open"])
                stop = entry - p["atr_stop_mult"] * atr
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes="RS-vs-sector new high + sector uptrend + breakout",
                    meta={"rs_vs_sector": True}))
        return signals
