"""Metric definitions: expectancy (R and currency), profit factor, drawdown."""
import pandas as pd

from scanner.backtest.engine import Trade
from scanner.backtest import metrics


def _trade(r, pnl, signal_time):
    return Trade(symbol="T", sector="X", setup="s", direction="long",
                 signal_time=pd.Timestamp(signal_time, tz="UTC"),
                 entry_time=pd.Timestamp(signal_time, tz="UTC"),
                 exit_time=pd.Timestamp(signal_time, tz="UTC"),
                 entry_price=100, exit_price=100 + pnl, stop=99, target=103,
                 shares=1, planned_risk_per_share=1.0, planned_r_multiple=3.0,
                 realized_r=r, pnl_dollars=pnl, bars_held=1, exit_reason="target",
                 regime="BULL/LOW_VOL", year=pd.Timestamp(signal_time).year,
                 worse_than_1r=(r < -1.0))


def test_profit_factor_and_expectancy():
    # two winners (+2R, +$200 each) and two losers (-1R, -$100 each)
    trades = [_trade(2, 200, "2020-01-02"), _trade(2, 200, "2020-02-03"),
              _trade(-1, -100, "2020-03-04"), _trade(-1, -100, "2020-04-06")]
    s = metrics.summary(trades)
    assert s["win_rate"] == 0.5
    assert abs(s["expectancy_r"] - 0.5) < 1e-9          # (2+2-1-1)/4
    assert abs(s["profit_factor"] - 2.0) < 1e-9         # 400 / 200
    assert abs(s["expectancy_currency"] - 50.0) < 1e-9  # 200 net / 4 trades
    assert abs(s["avg_winner_r"] - 2.0) < 1e-9
    assert abs(s["avg_loser_r"] + 1.0) < 1e-9


def test_max_drawdown_pct():
    # +200, +200, then -100, -100 around a 100k account
    trades = [_trade(2, 200, "2020-01-02"), _trade(2, 200, "2020-02-03"),
              _trade(-1, -100, "2020-03-04"), _trade(-1, -100, "2020-04-06")]
    dd = metrics.max_drawdown_pct(trades, starting_equity=100_000.0)
    # peak after +400 = 100400; trough after -200 = 100200; dd = 200/100400
    assert abs(dd - (200 / 100_400)) < 1e-9
