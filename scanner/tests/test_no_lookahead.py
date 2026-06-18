"""
Look-ahead guard: indicator values at row t must not change when future rows
are added/removed. This numerically verifies that enrich_daily and the regime
classifier use only past/current data.
"""
import numpy as np
import pandas as pd

from scanner import indicators as ind
from scanner import regime as regime_mod
from scanner.data.synthetic import SyntheticAdapter


def _frame():
    a = SyntheticAdapter(seed=3, n_days=800)
    end = pd.Timestamp.now("UTC").normalize()
    return a.get_bars("AAPL", "1d", end - pd.Timedelta(days=2000), end).df


def test_indicators_no_lookahead():
    df = _frame()
    full = ind.enrich_daily(df)
    cut = len(df) - 50
    partial = ind.enrich_daily(df.iloc[:cut])
    cols = ["sma20", "sma50", "atr14", "rsi14", "adx14", "hi20_prev",
            "bb_bw20", "vol_ratio", "ret20"]
    common = partial.index.intersection(full.index)
    # compare the last 30 overlapping rows of the truncated frame
    tail = common[-30:]
    a = full.loc[tail, cols].to_numpy()
    b = partial.loc[tail, cols].to_numpy()
    assert np.allclose(a, b, equal_nan=True, atol=1e-8), "indicator changed with future data"


def test_rolling_prev_excludes_current():
    df = _frame()
    hi = ind.rolling_high_prev(df["high"], 20)
    # the prior-20 high at t must never include the current bar's high by construction
    for t in range(40, 60):
        window_excl = df["high"].iloc[t - 20:t].max()
        assert np.isclose(hi.iloc[t], window_excl)


def test_regime_no_lookahead():
    df = _frame()
    full = regime_mod.classify(df)
    partial = regime_mod.classify(df.iloc[:len(df) - 40])
    common = partial.index.intersection(full.index)[-20:]
    assert (full.loc[common, "regime"].values == partial.loc[common, "regime"].values).all()
