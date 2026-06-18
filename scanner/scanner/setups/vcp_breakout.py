"""
Volatility-contraction breakout (VCP-style).

Hypothesis: a sharp contraction in realized range/Bollinger bandwidth reflects
a supply/demand equilibrium; a volume-confirmed break of the contraction's
upper bound tends to precede a directional expansion.

Objective trigger: Bollinger bandwidth in the bottom quintile of its trailing
distribution, then a close beyond the prior 20-bar high (long) / low (short)
with above-average volume. Stop sits on the other side of the contraction.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction


class VCPBreakout(Setup):
    name = "vcp_breakout"
    hypothesis = ("Low-bandwidth coil + volume-confirmed range break precedes "
                  "volatility expansion in the break direction.")

    @staticmethod
    def default_params() -> dict:
        return {
            "bw_pctile_max": 0.20,
            "vol_ratio_min": 1.5,
            "atr_stop_mult": 1.2,
            "planned_r": 2.5,
            "require_trend": True,   # only break in direction of 200SMA
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(row.get("bb_bw_pctile")) or pd.isna(row.get("hi20_prev")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0 or row["bb_bw_pctile"] > p["bw_pctile_max"]:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"
            vol_ok = row["vol_ratio"] >= p["vol_ratio_min"]

            long_trend = (not p["require_trend"]) or row["close"] > row["sma200"]
            short_trend = (not p["require_trend"]) or row["close"] < row["sma200"]

            if (vol_ok and row["close"] > row["hi20_prev"] and long_trend
                    and Direction.LONG in self.direction_modes):
                entry = float(nxt["open"])
                stop = min(entry - p["atr_stop_mult"] * atr, float(row["lo10_prev"]))
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes="coil break up on volume"))

            if (vol_ok and row["close"] < row["lo20_prev"] and short_trend
                    and Direction.SHORT in self.direction_modes):
                entry = float(nxt["open"])
                stop = max(entry + p["atr_stop_mult"] * atr, float(row["hi20_prev"]))
                if stop - entry <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.SHORT, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.SHORT, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes="coil break down on volume"))
        return signals
