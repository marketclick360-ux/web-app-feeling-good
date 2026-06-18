"""
Objective market-regime classification.

Regimes are derived from the benchmark (default SPY) daily series using only
closed-bar data. Each bar is tagged with:
  * trend  : BULL | BEAR | SIDEWAYS   (price vs 200SMA and 50SMA slope)
  * vol    : HIGH_VOL | LOW_VOL       (20d realized vol percentile vs history)

The combined label (e.g. "BULL/LOW_VOL") is attached to every trade so results
can be reported per regime, as the spec requires. No subjective judgment is
involved — all thresholds are explicit and testable.
"""
from __future__ import annotations

import pandas as pd

from . import indicators as ind


def classify(benchmark_daily: pd.DataFrame,
             vol_window: int = 20,
             vol_hist: int = 252,
             slope_window: int = 20,
             sideways_band: float = 0.03) -> pd.DataFrame:
    """Return a DataFrame indexed like the benchmark with columns
    [trend, vol, regime]. Safe against look-ahead (all shifted/rolling)."""
    d = benchmark_daily.copy()
    d["sma50"] = ind.sma(d["close"], 50)
    d["sma200"] = ind.sma(d["close"], 200)
    d["sma50_slope"] = d["sma50"].diff(slope_window)
    d["rvol"] = ind.realized_vol(d["close"], vol_window)
    d["rvol_pctile"] = ind.pct_rank(d["rvol"], vol_hist)

    dist = (d["close"] - d["sma200"]) / (d["sma200"] + 1e-12)
    trend = pd.Series("SIDEWAYS", index=d.index)
    trend[(d["close"] > d["sma200"]) & (d["sma50_slope"] > 0) & (dist > sideways_band)] = "BULL"
    trend[(d["close"] < d["sma200"]) & (d["sma50_slope"] < 0) & (dist < -sideways_band)] = "BEAR"

    vol = pd.Series("LOW_VOL", index=d.index)
    vol[d["rvol_pctile"] > 0.7] = "HIGH_VOL"

    out = pd.DataFrame({"trend": trend, "vol": vol})
    out["regime"] = out["trend"] + "/" + out["vol"]
    # rows without enough history to classify are NaN-trend -> mark UNKNOWN
    out.loc[d["sma200"].isna(), ["trend", "vol", "regime"]] = "UNKNOWN"
    return out
