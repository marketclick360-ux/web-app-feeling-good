"""
Multi-day candle resampling: correct aggregation, no look-ahead, no repainting.
"""
import numpy as np
import pandas as pd

from scanner.timeframe import resample_bars, wrap_timeframe, TimeframeAdapter
from scanner.data.synthetic import SyntheticAdapter


def _frame(n=12):
    idx = pd.bdate_range("2024-01-01", periods=n, tz="UTC")
    return pd.DataFrame({
        "open": np.arange(n, dtype=float) + 1,
        "high": np.arange(n, dtype=float) + 2,
        "low": np.arange(n, dtype=float) + 0.5,
        "close": np.arange(n, dtype=float) + 1.5,
        "volume": np.arange(n, dtype=float) + 100,
    }, index=idx)


def test_aggregation_ohlcv():
    df = _frame(4)
    out = resample_bars(df, 2)
    assert len(out) == 2
    # first candle = rows 0,1
    assert out.iloc[0]["open"] == df.iloc[0]["open"]
    assert out.iloc[0]["close"] == df.iloc[1]["close"]
    assert out.iloc[0]["high"] == max(df.iloc[0]["high"], df.iloc[1]["high"])
    assert out.iloc[0]["low"] == min(df.iloc[0]["low"], df.iloc[1]["low"])
    assert out.iloc[0]["volume"] == df.iloc[0]["volume"] + df.iloc[1]["volume"]


def test_right_labeled_and_tz_preserved():
    out = resample_bars(_frame(4), 2)
    assert out.index.tz is not None
    # candle is labeled at its LAST constituent day (closed-period contract)
    assert out.index[0] == _frame(4).index[1]


def test_no_repaint_prefix_matches():
    df = _frame(12)
    full = resample_bars(df, 2)
    # resampling only the first 8 daily bars must reproduce the earlier candles
    prefix = resample_bars(df.iloc[:8], 2)
    shared = full.iloc[: len(prefix)]
    assert shared.round(9).equals(prefix.round(9))


def test_incomplete_trailing_dropped():
    # 9 daily bars, 2-day candles → last lone day is not a closed candle
    out = resample_bars(_frame(9), 2)
    assert len(out) == 4  # floor(9/2), trailing single-day group dropped


def test_n1_is_passthrough():
    df = _frame(5)
    assert resample_bars(df, 1) is df
    assert wrap_timeframe("anything", 1) == "anything"


def test_adapter_wrapper_serves_resampled_bars():
    base = SyntheticAdapter(seed=7, n_days=400)
    end = pd.Timestamp.now("UTC").normalize()
    start = end - pd.Timedelta(days=800)
    daily = base.get_bars("AAPL", "1d", start, end).df
    tf = wrap_timeframe(base, 2)
    assert isinstance(tf, TimeframeAdapter)
    two = tf.get_bars("AAPL", "1d", start, end).df
    # roughly half as many candles, never more
    assert 0 < len(two) <= len(daily) // 2 + 1
    # liquidity is judged on raw daily bars, not aggregated candles
    assert tf.adv_dollar("AAPL", end) == base.adv_dollar("AAPL", end)
