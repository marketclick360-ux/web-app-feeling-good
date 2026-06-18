"""
Technical indicators — vectorized, no look-ahead, no repainting.

Conventions enforced here:
  * Every indicator at row t uses ONLY data from rows <= t.
  * "Reference levels" a setup compares the *current* bar against (e.g. a
    prior breakout high, prior NR7 range) are exposed as `*_prev` helpers
    that are explicitly shifted by 1 bar, so a setup can never peek at the
    bar it is evaluating.
  * Wilder's smoothing is used for ATR/ADX/RSI to match standard platforms.

No function in this module references future rows. The test
`tests/test_no_lookahead.py` verifies this property numerically.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ATR (RMA of true range)."""
    tr = true_range(df)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / (loss + 1e-12)
    return 100 - (100 / (1 + rs))


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ADX — trend-strength filter (objective, non-directional)."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df)
    atr_n = tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / n, adjust=False, min_periods=n).mean() / (atr_n + 1e-12)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / n, adjust=False, min_periods=n).mean() / (atr_n + 1e-12)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rolling_high_prev(s: pd.Series, n: int) -> pd.Series:
    """Highest value over the prior n bars, EXCLUDING the current bar."""
    return s.rolling(n, min_periods=n).max().shift(1)


def rolling_low_prev(s: pd.Series, n: int) -> pd.Series:
    """Lowest value over the prior n bars, EXCLUDING the current bar."""
    return s.rolling(n, min_periods=n).min().shift(1)


def dollar_volume(df: pd.DataFrame) -> pd.Series:
    return df["close"] * df["volume"]


def adv_dollar(df: pd.DataFrame, n: int = 20) -> pd.Series:
    return dollar_volume(df).rolling(n, min_periods=n).mean()


def bollinger_bandwidth(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.Series:
    mid = sma(s, n)
    sd = s.rolling(n, min_periods=n).std(ddof=0)
    return (2 * k * sd) / (mid + 1e-12)


def realized_vol(s: pd.Series, n: int = 20, annualize: int = 252) -> pd.Series:
    return s.pct_change().rolling(n, min_periods=n).std(ddof=0) * np.sqrt(annualize)


def pct_rank(s: pd.Series, n: int) -> pd.Series:
    """Trailing percentile rank (0..1) of the current value within n bars."""
    return s.rolling(n, min_periods=n).apply(
        lambda x: (x[-1] >= x).mean(), raw=True)


def enrich_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the common indicator set used by daily setups. No look-ahead."""
    d = df.copy()
    d["sma20"] = sma(d["close"], 20)
    d["sma50"] = sma(d["close"], 50)
    d["sma200"] = sma(d["close"], 200)
    d["ema10"] = ema(d["close"], 10)
    d["ema20"] = ema(d["close"], 20)
    d["atr14"] = atr(d, 14)
    d["atr_pct"] = d["atr14"] / (d["close"] + 1e-12)
    d["rsi14"] = rsi(d["close"], 14)
    d["adx14"] = adx(d, 14)
    d["adv20"] = adv_dollar(d, 20)
    d["bb_bw20"] = bollinger_bandwidth(d["close"], 20)
    d["bb_bw_pctile"] = pct_rank(d["bb_bw20"], 120)
    d["hi20_prev"] = rolling_high_prev(d["high"], 20)
    d["lo20_prev"] = rolling_low_prev(d["low"], 20)
    d["hi55_prev"] = rolling_high_prev(d["high"], 55)
    d["lo10_prev"] = rolling_low_prev(d["low"], 10)
    d["vol_sma20"] = sma(d["volume"], 20)
    d["vol_ratio"] = d["volume"] / (d["vol_sma20"] + 1e-12)
    d["ret20"] = d["close"].pct_change(20)
    d["ret63"] = d["close"].pct_change(63)
    return d
