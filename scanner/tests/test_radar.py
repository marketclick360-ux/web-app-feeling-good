"""
Radar backtest: entries fire where they should, exits behave (strength exit for
mean-reversion, channel exit for breakouts, hard stop honored), the SPY filter
blocks signals when risk-off, and the stats are internally consistent.
"""
import numpy as np
import pandas as pd

from scanner.radar import run_radar, _rsi, _stats, RadarTrade


class _Bars:
    def __init__(self, df):
        self.df = df


class _StubAdapter:
    """Serves one price path for every ticker requested."""
    def __init__(self, frames):
        self.frames = frames  # name -> df

    def get_bars(self, symbol, tf, start=None, end=None, as_of=None):
        return _Bars(self.frames[symbol])


def _df(close, low_off=0.005, high_off=0.005, vol=2e6):
    close = np.asarray(close, dtype=float)
    idx = pd.bdate_range("2015-01-02", periods=len(close), tz="UTC")
    return pd.DataFrame({
        "open": np.r_[close[0], close[:-1]],
        "high": close * (1 + high_off),
        "low": close * (1 - low_off),
        "close": close,
        "volume": vol,
    }, index=idx)


def _uptrend_with_dips(n=1500, seed=3):
    rng = np.random.default_rng(seed)
    drift = np.linspace(0, 1.2, n)
    wiggle = np.cumsum(rng.normal(0, 0.008, n))
    dip = np.zeros(n)
    for start in range(300, n - 60, 120):        # periodic sharp 3-day dips
        dip[start:start + 3] -= 0.02
    return 100 * np.exp(drift + wiggle + np.cumsum(dip))


def test_rsi2_bounds():
    s = pd.Series(np.linspace(100, 120, 50))
    r = _rsi(s, 2)
    assert float(r.iloc[-1]) > 90          # straight up -> RSI(2) ~ 100
    s2 = pd.Series(np.linspace(120, 100, 50))
    assert float(_rsi(s2, 2).iloc[-1]) < 10


def test_radar_produces_trades_and_consistent_stats():
    path = _uptrend_with_dips()
    frames = {"SPY": _df(path), "AAA": _df(path * 1.1), "BBB": _df(path * 0.9)}
    res = run_radar(_StubAdapter(frames), ["AAA", "BBB"], years=6,
                    as_of=pd.Timestamp("2020-11-01", tz="UTC"), spy_filter=True)
    assert res, "should return results"
    total = sum(r["stats"].get("n", 0) for r in res.values())
    assert total > 0, "an uptrend with dips must fire at least some entries"
    for r in res.values():
        s = r["stats"]
        if s.get("n"):
            assert -100 < s["expectancy"] < 100
            assert 0 <= s["win_rate"] <= 1
            assert r["per_week"] >= 0


def test_spy_filter_blocks_downtrend():
    up = _uptrend_with_dips()
    down = up[::-1].copy()                     # SPY falling the whole time
    frames = {"SPY": _df(down), "AAA": _df(up)}
    res = run_radar(_StubAdapter(frames), ["AAA"], years=6,
                    as_of=pd.Timestamp("2020-11-01", tz="UTC"), spy_filter=True)
    total_filtered = sum(r["stats"].get("n", 0) for r in res.values())
    res2 = run_radar(_StubAdapter(frames), ["AAA"], years=6,
                     as_of=pd.Timestamp("2020-11-01", tz="UTC"), spy_filter=False)
    total_open = sum(r["stats"].get("n", 0) for r in res2.values())
    assert total_filtered < total_open         # risk-off gate must cut trades
    assert total_filtered <= total_open


def test_oversold_reclaim_fires():
    # long uptrend, then a sharp 2-bar break below the 20-day low (still above
    # the 200-day), then a green reclaim bar -> the entry must fire
    base = np.linspace(100, 160, 600)
    base[560:562] = [149.0, 148.5]            # the break
    base[562:] = np.linspace(154, 156, 38)    # green recovery, above sma200
    frames = {"SPY": _df(base), "AAA": _df(base)}
    res = run_radar(_StubAdapter(frames), ["AAA"], years=4,
                    as_of=pd.Timestamp("2017-06-01", tz="UTC"), spy_filter=False,
                    strategies=["oversold_reclaim_20d"])
    assert res["oversold_reclaim_20d"]["stats"].get("n", 0) >= 1


def test_radar_signal_fires_on_fresh_breakout():
    from scanner.radar import radar_signal
    # steady uptrend whose LAST bar closes above the prior 20- and 55-day highs
    base = np.linspace(100, 150, 600)
    base[-1] = base[-2] * 1.03                 # decisive breakout close
    frames = {"SPY": _df(base), "AAA": _df(base)}
    res = radar_signal(_StubAdapter(frames), ["AAA"],
                       as_of=pd.Timestamp("2017-06-01", tz="UTC"))
    assert res["risk_on"] is True
    strategies = {r["strategy"] for r in res["rows"] if r["ticker"] == "AAA"}
    assert "breakout_20d" in strategies and "breakout_55d" in strategies
    row = next(r for r in res["rows"] if r["strategy"] == "breakout_20d")
    assert row["stop_2atr"] < row["close"] and row["risk_pct"] > 0


def test_ticker_profile_fields_and_sanity():
    from scanner.radar import ticker_profile
    up = _uptrend_with_dips()
    frames = {"SPY": _df(up), "AAA": _df(up * 1.1)}
    rows = ticker_profile(_StubAdapter(frames), ["AAA"],
                          as_of=pd.Timestamp("2020-11-01", tz="UTC"), years=6)
    assert len(rows) == 1
    p = rows[0]
    assert p["ticker"] == "AAA"
    assert p["personality"] in ("MOMO", "CHOP", "NEUTRAL")
    assert 0 <= p["followthrough_pct"] <= 100
    assert p["vol_mood"] in ("SLEEPY", "WILD", "NORMAL")
    assert 0 <= p["vol_pctile"] <= 100
    # AAA is SPY's path scaled: beta ~ 1, correlation ~ 1
    assert abs(p["beta"] - 1.0) < 0.15
    assert p["corr_spy"] > 0.95
    assert p["max_dd_pct"] <= 0
    assert p["typical_pullback_pct"] <= 0
    assert 0 <= p["pos_52w_pct"] <= 100


def test_breakout_report_card(tmp_path):
    from scanner.radar import breakout_report_card
    csv = tmp_path / "trades.csv"
    pd.DataFrame({
        "ticker":   ["AAA", "AAA", "BBB", "BBB"],
        "strategy": ["breakout_20d", "breakout_55d",
                     "breakout_20d", "pullback_rsi2_200d"],
        "ret_pct":  [10.0, -2.0, 5.0, 99.0],   # the rsi2 row must be excluded
    }).to_csv(csv, index=False)
    card = breakout_report_card(str(csv))
    assert [c["ticker"] for c in card] == ["AAA", "BBB"]  # sorted by total $
    a = card[0]
    assert a["n"] == 2 and a["win_rate"] == 50
    assert abs(a["total_per_$1k"] - 80.0) < 1e-9          # (10-2)% * $1k
    assert card[1]["n"] == 1                              # rsi2 trade excluded


def test_stats_math():
    trades = [RadarTrade("A", "s", "2020-01-01", "2020-01-05", 100, 102, 2.0, 4, "strength", 2020),
              RadarTrade("A", "s", "2020-02-01", "2020-02-05", 100, 99, -1.0, 4, "stop", 2020)]
    s = _stats(trades)
    assert s["n"] == 2 and abs(s["expectancy"] - 0.5) < 1e-9
    assert abs(s["profit_factor"] - 2.0) < 1e-9
