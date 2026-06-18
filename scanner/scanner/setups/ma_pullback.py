"""
Pullback to the 10-day or 20-day moving average in a strong trend.

Hypothesis: in a strong, established trend, a shallow pullback that tags a
short moving average (10 or 20 day) and holds is a lower-risk continuation
entry than chasing extension. Distinct from `trend_pullback` (which keys off
the EMA20 + RSI cooling): this family keys purely off a touch-and-hold of a
configurable simple MA inside an ADX-confirmed trend, so the two can be
compared as separate, objective variants.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction
from .. import indicators as ind


class MAPullback(Setup):
    name = "ma_pullback"
    hypothesis = ("Touch-and-hold of the 10/20-day MA within an ADX-confirmed "
                  "trend is a continuation entry, not a reversal.")

    @staticmethod
    def default_params() -> dict:
        return {
            "ma_len": 20,           # 10 or 20
            "adx_min": 20.0,
            "atr_stop_mult": 1.5,
            "planned_r": 2.0,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        ma = ind.sma(df["close"], int(p["ma_len"]))
        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(row.get("sma200")) or pd.isna(ma.iloc[i]) or pd.isna(row.get("adx14")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"
            m = float(ma.iloc[i])

            uptrend = (row["close"] > row["sma50"] > row["sma200"]
                       and row["adx14"] >= p["adx_min"])
            dntrend = (row["close"] < row["sma50"] < row["sma200"]
                       and row["adx14"] >= p["adx_min"])

            if uptrend and Direction.LONG in self.direction_modes:
                # tagged the MA from above and closed back above it
                if row["low"] <= m <= row["close"]:
                    entry = float(nxt["open"])
                    stop = entry - p["atr_stop_mult"] * atr
                    if entry - stop <= 0:
                        continue
                    target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                    signals.append(Signal(
                        symbol, Direction.LONG, self.name, ts, entry, stop, target,
                        planned_r_multiple=p["planned_r"], time_stop_bars=10,
                        hypothesis=self.hypothesis, regime_at_signal=str(reg),
                        notes=f"hold of {int(p['ma_len'])}d MA in uptrend"))

            if dntrend and Direction.SHORT in self.direction_modes:
                if row["high"] >= m >= row["close"]:
                    entry = float(nxt["open"])
                    stop = entry + p["atr_stop_mult"] * atr
                    if stop - entry <= 0:
                        continue
                    target = self._planned_target(entry, stop, Direction.SHORT, p["planned_r"])
                    signals.append(Signal(
                        symbol, Direction.SHORT, self.name, ts, entry, stop, target,
                        planned_r_multiple=p["planned_r"], time_stop_bars=10,
                        hypothesis=self.hypothesis, regime_at_signal=str(reg),
                        notes=f"rejection at {int(p['ma_len'])}d MA in downtrend"))
        return signals
