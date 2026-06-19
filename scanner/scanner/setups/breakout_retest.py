"""
Breakout + retest.

Hypothesis: a volume-confirmed break above a multi-week resistance level, then a
pullback that holds the broken level (old resistance = new support), is a
higher-quality entry than chasing the initial breakout — it filters many false
breakouts. Long-only.

Objective: a close broke above the prior `lookback`-bar high within the last
`retest_window` bars on expanded volume; the current bar dips back to within
`buffer_atr`·ATR of that level but closes above it. Entry next open; stop just
below the reclaimed level. Target 3R.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction


class BreakoutRetest(Setup):
    name = "breakout_retest"
    hypothesis = ("Volume break of a multi-week high, then a held retest of the "
                  "broken level, filters false breakouts.")
    direction_modes = (Direction.LONG,)

    @staticmethod
    def default_params() -> dict:
        return {
            "lookback": 40,          # resistance window
            "retest_window": 10,     # bars allowed between breakout and retest
            "vol_ratio_min": 1.3,
            "buffer_atr": 0.3,
            "planned_r": 3.0,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        lb, rw = int(p["lookback"]), int(p["retest_window"])
        signals = []
        start = lb + rw + 1
        for i in range(start, len(df) - 1):
            row, nxt, ts = df.iloc[i], df.iloc[i + 1], df.index[i]
            if pd.isna(row.get("atr14")):
                continue
            if self._near_earnings(ts, context):
                continue
            atr = float(row["atr14"])
            if atr <= 0:
                continue
            reg = regime.iloc[i] if i < len(regime) else "UNKNOWN"

            # resistance level as of (rw+1) bars ago — the pre-breakout high
            level = float(df["high"].iloc[i - rw - lb:i - rw].max())
            window = df.iloc[i - rw:i]            # the breakout window (past bars)
            broke = bool((window["close"] > level).any())
            vol_ok = bool((window["vol_ratio"] > p["vol_ratio_min"]).any())
            # current bar retests and holds
            retest = (row["low"] <= level * (1 + 0.003)) and (row["close"] >= level)

            if broke and vol_ok and retest:
                entry = float(nxt["open"])
                stop = level - p["buffer_atr"] * atr
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes=f"retest of broken {level:.2f}"))
        return signals
