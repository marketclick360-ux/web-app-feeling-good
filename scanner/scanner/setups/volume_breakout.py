"""
Volume-confirmed support/resistance break.

Hypothesis: a decisive close through a well-tested horizontal level on
expanded volume signals that resting supply/demand at that level has been
absorbed, with old resistance acting as new support (and vice versa).

Objective level = prior 55-bar extreme (a "well-tested" horizontal boundary).
The stop sits just beyond the broken level, so the trade is invalidated if the
break fails and price re-enters the prior range.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction


class VolumeBreakout(Setup):
    name = "volume_breakout"
    hypothesis = ("Decisive volume-expansion close through a 55-bar boundary "
                  "marks absorption of resting supply/demand at that level.")

    @staticmethod
    def default_params() -> dict:
        return {
            "vol_ratio_min": 1.7,
            "buffer_atr": 0.25,   # stop placed this far back inside old range
            "planned_r": 2.5,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        signals = []
        for i in range(1, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(row.get("hi55_prev")) or pd.isna(row.get("atr14")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0 or row["vol_ratio"] < p["vol_ratio_min"]:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"
            level_hi = float(row["hi55_prev"])

            if row["close"] > level_hi and Direction.LONG in self.direction_modes:
                entry = float(nxt["open"])
                stop = level_hi - p["buffer_atr"] * atr  # old resistance = new support
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes=f"break above 55-bar high {level_hi:.2f} on volume"))
        return signals
