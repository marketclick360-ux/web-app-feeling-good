"""
Opening-range breakout (intraday).

Hypothesis: the first minutes of the session establish a provisional balance
area; a break of that range on participation often initiates the day's
directional move. Runs on INTRADAY frames (15m or 1h) only — it groups bars by
session date, defines the opening range from the first `or_bars` bars, and
signals the first subsequent bar that closes beyond the range.

Time stop = end of the same session (no overnight hold), satisfying the
"intraday to 10 days" holding window at the short end. Requires reliable
intraday history; if only daily data is available this family is not testable
and must be disclosed as such.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base import Setup, Signal, Direction


class OpeningRangeBreakout(Setup):
    name = "opening_range_breakout"
    hypothesis = ("Break of the session's opening range on participation "
                  "initiates the day's directional move.")

    @staticmethod
    def default_params() -> dict:
        return {
            "or_bars": 2,           # bars composing the opening range
            "vol_ratio_min": 1.2,
            "stop_mode": "or_opposite",  # stop at opposite side of opening range
            "planned_r": 3.0,
        }

    def generate(self, df, regime, symbol, context: Optional[dict] = None) -> list:
        p = self.params
        if not isinstance(df.index, pd.DatetimeIndex):
            return []
        signals = []
        sessions = df.groupby(df.index.date)
        vol_sma = df["volume"].rolling(20, min_periods=5).mean()

        for day, sess in sessions:
            if len(sess) <= p["or_bars"] + 1:
                continue
            ts0 = sess.index[0]
            if self._near_earnings(ts0, context):
                continue
            or_block = sess.iloc[:p["or_bars"]]
            or_high = float(or_block["high"].max())
            or_low = float(or_block["low"].min())
            if or_high - or_low <= 0:
                continue
            reg = regime.reindex([sess.index[p["or_bars"]]]).iloc[0] \
                if len(regime) else "UNKNOWN"
            triggered = False
            for j in range(p["or_bars"], len(sess) - 1):
                if triggered:
                    break
                bar, nxt = sess.iloc[j], sess.iloc[j + 1]
                ts = sess.index[j]
                vr = bar["volume"] / (vol_sma.get(ts, np.nan) + 1e-12)
                if vr < p["vol_ratio_min"]:
                    continue
                bars_left = len(sess) - 1 - (j + 1)
                if bar["close"] > or_high and Direction.LONG in self.direction_modes:
                    entry = float(nxt["open"])
                    stop = or_low if p["stop_mode"] == "or_opposite" else or_high - (or_high - or_low)
                    if entry - stop <= 0:
                        continue
                    target = self._planned_target(entry, stop, Direction.LONG, p["planned_r"])
                    signals.append(Signal(
                        symbol, Direction.LONG, self.name, ts, entry, stop, target,
                        planned_r_multiple=p["planned_r"],
                        time_stop_bars=max(bars_left, 1),
                        hypothesis=self.hypothesis, regime_at_signal=str(reg),
                        notes=f"ORB long {day} range[{or_low:.2f},{or_high:.2f}]"))
                    triggered = True
                elif bar["close"] < or_low and Direction.SHORT in self.direction_modes:
                    entry = float(nxt["open"])
                    stop = or_high if p["stop_mode"] == "or_opposite" else or_low + (or_high - or_low)
                    if stop - entry <= 0:
                        continue
                    target = self._planned_target(entry, stop, Direction.SHORT, p["planned_r"])
                    signals.append(Signal(
                        symbol, Direction.SHORT, self.name, ts, entry, stop, target,
                        planned_r_multiple=p["planned_r"],
                        time_stop_bars=max(bars_left, 1),
                        hypothesis=self.hypothesis, regime_at_signal=str(reg),
                        notes=f"ORB short {day} range[{or_low:.2f},{or_high:.2f}]"))
                    triggered = True
        return signals
