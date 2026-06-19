"""
Accumulation breakout — the OBJECTIVE version of "demand / accumulation."

Hypothesis: a breakout to new highs is more likely to follow through when it is
backed by genuine accumulation — net buying pressure showing up in volume flow,
not just price. This replaces subjective "smart money / supply-demand" chart
reads with measurable volume indicators.

Objective trigger: close breaks the prior 20-bar high, Chaikin Money Flow is
positive (accumulation), On-Balance Volume is rising, and volume expands.
Long-only. Entry next open; ATR stop; 3R target.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction


class AccumulationBreakout(Setup):
    name = "accumulation_breakout"
    hypothesis = ("Breakout confirmed by accumulation (CMF>0, rising OBV, volume "
                  "expansion) — objective supply/demand, not chart-reading.")
    direction_modes = (Direction.LONG,)

    @staticmethod
    def default_params() -> dict:
        return {
            "cmf_min": 0.05,         # net accumulation
            "vol_ratio_min": 1.3,
            "atr_stop_mult": 1.5,
            "planned_r": 3.0,
            "require_trend": True,   # above 200SMA
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(row.get("hi20_prev")) or pd.isna(row.get("cmf20")) \
                    or pd.isna(row.get("obv_slope")) or pd.isna(row.get("atr14")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"

            trend_ok = (not p["require_trend"]) or row["close"] > row["sma200"]
            breakout = row["close"] > row["hi20_prev"]
            accumulation = row["cmf20"] > p["cmf_min"] and row["obv_slope"] > 0
            vol_ok = row["vol_ratio"] >= p["vol_ratio_min"]

            if trend_ok and breakout and accumulation and vol_ok:
                entry = float(nxt["open"])
                stop = entry - p["atr_stop_mult"] * atr
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes=f"breakout + accumulation (CMF {row['cmf20']:.2f})"))
        return signals
