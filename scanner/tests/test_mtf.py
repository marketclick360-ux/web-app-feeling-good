"""
Single-ticker multi-timeframe model: it must (a) actually go to cash in a
sustained downtrend so its drawdown beats buy-and-hold, and (b) report
internally consistent buy-and-hold numbers.
"""
import numpy as np
import pandas as pd

from scanner.mtf import run_mtf, _max_dd


class _Bars:
    def __init__(self, df):
        self.df = df


class _StubAdapter:
    """Serves a single fixed price path as daily bars."""
    def __init__(self, close):
        idx = pd.bdate_range("2008-01-02", periods=len(close), tz="UTC")
        o = np.r_[close[0], close[:-1]]          # open = prior close (no gaps)
        self._df = pd.DataFrame({"open": o, "high": close * 1.001,
                                 "low": close * 0.999, "close": close,
                                 "volume": 1e7}, index=idx)

    def get_bars(self, symbol, tf, start=None, end=None, as_of=None):
        return _Bars(self._df)


def test_goes_to_cash_and_cuts_drawdown_in_a_crash():
    # 600 up days, then a 150-day -45% bleed, then recovery — buy&hold eats the
    # whole crash; the trend model should be in cash for most of it.
    up = np.linspace(100, 300, 600)
    crash = np.linspace(300, 165, 150)
    rec = np.linspace(165, 260, 250)
    close = np.concatenate([up, crash, rec])
    adapter = _StubAdapter(close)
    res = run_mtf(adapter, "TEST", years=4,
                  as_of=pd.Timestamp("2012-06-01", tz="UTC"), atr_stop_mult=None)
    assert res is not None
    # the model sidesteps enough of the crash to have a smaller max drawdown
    assert res.strat_max_dd < res.bh_max_dd
    # and it was not invested the entire time (it stepped aside)
    assert res.pct_time_invested < 100.0
    assert res.n_trades >= 1


def test_buy_and_hold_matches_price_path():
    close = np.linspace(100, 200, 800)            # smooth uptrend, ~+100%
    adapter = _StubAdapter(close)
    res = run_mtf(adapter, "TEST", years=3,
                  as_of=pd.Timestamp("2011-06-01", tz="UTC"), atr_stop_mult=None)
    # 200-bar indicator warmup is trimmed, so buy&hold starts mid-path (~125)
    # and returns ~+60% — just require a solid positive, not the full +100%.
    assert 40.0 < res.bh_total_return < 80.0
    # in a clean uptrend the model is invested almost the whole time, so it
    # should track buy-and-hold closely
    assert res.pct_time_invested > 80.0
    assert abs(res.strat_total_return - res.bh_total_return) < 6.0


def test_max_dd_helper():
    eq = np.array([100, 120, 90, 110, 80, 130])
    # worst peak->trough is 120 -> 80 = 33.3%
    assert abs(_max_dd(eq) - (40 / 120)) < 1e-9
