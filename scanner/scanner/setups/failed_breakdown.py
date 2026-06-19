"""
Failed breakdown / bear trap reversal.

Hypothesis: when price breaks below an established support level and then
quickly reclaims it (within a few bars) on expanding volume, trapped short
sellers and stopped-out longs must cover/re-buy, fueling a sharp reversal.
Long-only.

Objective: within the last `trap_window` bars the low broke below the prior
`lookback`-bar support; the current bar closes back ABOVE that support on
expanded volume. Entry next open; stop below the failed-breakdown low. Target 3R.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from .base import Setup, Signal, Direction


class FailedBreakdown(Setup):
    name = "failed_breakdown"
    hypothesis = ("Quick reclaim of broken support on volume traps shorts and "
                  "fuels a reversal.")
    direction_modes = (Direction.LONG,)

    @staticmethod
    def default_params() -> dict:
        return {
            "lookback": 40,         # support window
            "trap_window": 3,       # bars allowed below support before reclaim
            "vol_ratio_min": 1.3,
            "buffer_atr": 0.25,
            "planned_r": 3.0,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        lb, tw = int(p["lookback"]), int(p["trap_window"])
        signals = []
        start = lb + tw + 1
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

            # support as of (tw+1) bars ago — the pre-break low
            support = float(df["low"].iloc[i - tw - lb:i - tw].min())
            window = df.iloc[i - tw:i + 1]        # trap window incl current bar
            broke_below = bool((window["low"] < support).any())
            reclaim = row["close"] > support
            vol_ok = row["vol_ratio"] > p["vol_ratio_min"]
            trap_low = float(window["low"].min())

            if broke_below and reclaim and vol_ok:
                entry = float(nxt["open"])
                stop = trap_low - p["buffer_atr"] * atr
                if entry - stop <= 0:
                    continue
                target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                signals.append(Signal(
                    symbol, Direction.LONG, self.name, ts, entry, stop, target,
                    planned_r_multiple=p["planned_r"], time_stop_bars=10,
                    hypothesis=self.hypothesis, regime_at_signal=str(reg),
                    notes=f"reclaim of {support:.2f} (trap low {trap_low:.2f})"))
        return signals
