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


def test_support_zone_counts_touches():
    from scanner.mtf import _support_zones, _nearest_support
    # build a saw-tooth that bounces off ~100 three times, between peaks at ~110
    seg_down = np.linspace(110, 100, 8)
    seg_up = np.linspace(100, 110, 8)
    close = np.concatenate([seg_down, seg_up, seg_down, seg_up, seg_down, seg_up])
    idx = pd.bdate_range("2022-01-03", periods=len(close), tz="UTC")
    df = pd.DataFrame({"open": close, "high": close + 0.5,
                       "low": close - 0.2, "close": close}, index=idx)
    zones = _support_zones(df, window=3, tol_pct=2.0, lookback=200)
    # a ~99.8 support zone should be found with multiple touches
    near = [z for z in zones if abs(z["level"] - 99.8) < 3]
    assert near and max(z["touches"] for z in near) >= 2
    sup = _nearest_support(df, price=101.0)
    assert sup is not None and sup["touches"] >= 2 and 0 <= sup["dist_pct"] <= 5
    assert sup["span_years"] >= 0 and "years_since_last" in sup


def test_support_history_measures_a_multiyear_floor():
    from scanner.mtf import support_history
    # ~6 years of bars that repeatedly dip to ~100 and rally to ~120
    cycle = np.concatenate([np.linspace(120, 100, 30), np.linspace(100, 120, 30)])
    close = np.tile(cycle, 26)[:1560]            # ~6 years of business days
    adapter = _StubAdapter(close)
    s = support_history(adapter, "TEST",
                        as_of=pd.Timestamp("2014-02-01", tz="UTC"),
                        years=25, min_span_years=2.0)
    assert s is not None and s["has_floor"] is True
    assert s["touches"] >= 3 and s["span_years"] >= 2
    assert s["n_events"] >= 3 and "median_gain" in s and "median_days_to_peak" in s


def test_volume_study_bigger_moves_on_higher_volume():
    from scanner.mtf import volume_study
    rng = np.random.default_rng(1)
    n = 1200
    ret = rng.normal(0, 0.01, n)                    # daily returns
    close = 100 * np.exp(np.cumsum(ret))
    # volume scales with the size of the move -> heavy days = big moves
    base_v = 1e6
    volume = base_v * (1 + 8 * np.abs(ret)) * rng.uniform(0.8, 1.2, n)
    idx = pd.bdate_range("2018-01-02", periods=n, tz="UTC")
    df = pd.DataFrame({"open": close, "high": close * 1.005, "low": close * 0.995,
                       "close": close, "volume": volume}, index=idx)

    class _A:
        def get_bars(self, *a, **k):
            class _B:
                pass
            b = _B(); b.df = df; return b

    s = volume_study(_A(), "TEST", as_of=pd.Timestamp("2022-09-01", tz="UTC"))
    assert s is not None and s["buckets"]
    moves = {b["bucket"]: b["median_move"] for b in s["buckets"]}
    # the highest-volume bucket should move more than the lowest one
    assert moves[s["buckets"][-1]["bucket"]] > moves[s["buckets"][0]["bucket"]]
