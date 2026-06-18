"""
Trend-aligned mean reversion.

Hypothesis: within a confirmed uptrend, short-term oversold dislocations
(panic flushes) revert because the dominant trend reasserts. Mean reversion is
ONLY taken when the higher-timeframe trend supports it (close above the rising
200SMA), never as a standalone reversal bet.

IMPORTANT HONESTY NOTE: a 3R PLANNED target on a mean-reversion entry is
deliberately demanding. The bounce frequently completes before 3R, so this
family typically relies on the time stop and is expected to show a LOWER
realized win rate at a 3R planned target. The validation layer will likely
flag or reject it — that is the intended, skeptical behavior, not a bug.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction
from .. import indicators as ind


class MeanReversion(Setup):
    name = "mean_reversion"
    hypothesis = ("Oversold flush within a confirmed uptrend reverts toward the "
                  "mean; only taken when higher-timeframe trend supports it.")
    direction_modes = (Direction.LONG,)  # long-only by construction

    @staticmethod
    def default_params() -> dict:
        return {
            "rsi_len": 2,
            "rsi_oversold": 10.0,
            "atr_stop_mult": 2.5,   # wide stop for noise -> small risk-per-share denom
            "planned_r": 1.5,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        rsi_fast = ind.rsi(df["close"], p["rsi_len"])
        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(row.get("sma200")) or pd.isna(rsi_fast.iloc[i]):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"
            uptrend = row["close"] > row["sma200"] and row["sma200"] > df["sma200"].iloc[i - 1]
            oversold = rsi_fast.iloc[i] <= p["rsi_oversold"]
            if uptrend and oversold and Direction.LONG in self.direction_modes:
                entry = float(nxt["open"])
                stop = entry - p["atr_stop_mult"] * atr
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=5,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes="RSI2 oversold within uptrend"))
        return signals
