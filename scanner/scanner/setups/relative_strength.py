"""
Relative-strength breakout versus benchmark (SPY) / sector ETF.

Hypothesis: names making new relative-strength highs against the broad market
tend to attract continued institutional flow (documented cross-sectional
momentum). The RS line breaking out is required IN ADDITION to a price
breakout, so the edge is the relative behavior, not price alone — the placebo
test (price breakout WITHOUT RS confirmation) checks exactly this.

Requires a benchmark series in context["benchmark"].
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from . import base
from .base import Setup, Signal, Direction
from .. import indicators as ind


class RelativeStrengthBreakout(Setup):
    name = "relative_strength_breakout"
    hypothesis = ("New relative-strength highs vs SPY plus a price breakout "
                  "capture cross-sectional momentum / institutional rotation.")

    @staticmethod
    def default_params() -> dict:
        return {
            "rs_lookback": 60,
            "price_lookback": 20,
            "atr_stop_mult": 1.5,
            "planned_r": 3.0,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        if not context or "benchmark" not in context:
            return []  # cannot compute RS without benchmark; disclosed as limitation
        bench = context["benchmark"]["close"].reindex(df.index).ffill()
        rs = df["close"] / (bench + 1e-12)
        rs_high_prev = ind.rolling_high_prev(rs, p["rs_lookback"])

        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(rs_high_prev.iloc[i]) or pd.isna(row.get("hi20_prev")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"
            rs_break = rs.iloc[i] > rs_high_prev.iloc[i]
            price_break = row["close"] > row["hi20_prev"]
            if rs_break and price_break and Direction.LONG in self.direction_modes:
                entry = float(nxt["open"])
                stop = entry - p["atr_stop_mult"] * atr
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes="RS-line new high + price breakout",
                    meta={"rs_confirmed": True}))
        return signals
