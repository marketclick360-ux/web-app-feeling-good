"""
Trend-continuation pullback.

Hypothesis: in an established uptrend, temporary pullbacks toward a rising
moving average are absorbed by trend-following demand, giving a favorable
asymmetric entry when the pullback stalls. Symmetric logic for downtrends.

All conditions are objective and evaluated on the CLOSED bar; entry is placed
for the next bar's open.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction


class TrendPullback(Setup):
    name = "trend_pullback"
    hypothesis = ("Pullbacks to a rising/falling 20EMA within a confirmed "
                  "ADX trend are continuation entries, not reversals.")

    @staticmethod
    def default_params() -> dict:
        return {
            "adx_min": 20.0,
            "rsi_long_max": 45.0,   # pullback must cool momentum
            "rsi_short_min": 55.0,
            "atr_stop_mult": 1.5,
            "planned_r": 3.0,
            "pullback_atr": 0.5,    # low must come within 0.5 ATR of EMA20
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        signals = []
        # iterate to second-to-last row; entry is the NEXT bar -> never the last
        for i in range(1, len(df) - 1):
            row = df.iloc[i]
            if pd.isna(row.get("sma200")) or pd.isna(row.get("adx14")):
                continue
            nxt = df.iloc[i + 1]
            ts = df.index[i]
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue

            uptrend = (row["close"] > row["sma50"] > row["sma200"]
                       and row["adx14"] >= p["adx_min"])
            dntrend = (row["close"] < row["sma50"] < row["sma200"]
                       and row["adx14"] >= p["adx_min"])

            # LONG: pullback near rising EMA20, momentum cooled, close reclaims EMA20
            if uptrend and Direction.LONG in self.direction_modes:
                near_ema = (row["low"] - row["ema20"]) <= p["pullback_atr"] * atr
                if (near_ema and row["close"] >= row["ema20"]
                        and row["rsi14"] <= p["rsi_long_max"]):
                    entry = float(nxt["open"])
                    stop = entry - p["atr_stop_mult"] * atr
                    if entry - stop <= 0:
                        continue
                    target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                    signals.append(Signal(
                        symbol, Direction.LONG, self.name, ts, entry, stop, target,
                        planned_r_multiple=p["planned_r"], time_stop_bars=10,
                        hypothesis=self.hypothesis, regime_at_signal=str(reg),
                        notes="pullback-to-EMA20 in ADX uptrend"))

            if dntrend and Direction.SHORT in self.direction_modes:
                near_ema = (row["ema20"] - row["high"]) <= p["pullback_atr"] * atr
                if (near_ema and row["close"] <= row["ema20"]
                        and row["rsi14"] >= p["rsi_short_min"]):
                    entry = float(nxt["open"])
                    stop = entry + p["atr_stop_mult"] * atr
                    if stop - entry <= 0:
                        continue
                    target = self._planned_target(entry, stop, Direction.SHORT, p["planned_r"])
                    signals.append(Signal(
                        symbol, Direction.SHORT, self.name, ts, entry, stop, target,
                        planned_r_multiple=p["planned_r"], time_stop_bars=10,
                        hypothesis=self.hypothesis, regime_at_signal=str(reg),
                        notes="rally-to-EMA20 in ADX downtrend"))
        return signals
