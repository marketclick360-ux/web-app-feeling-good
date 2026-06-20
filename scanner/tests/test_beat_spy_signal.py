"""
beat_spy live-signal logic: each strategy's current allocation reflects the
LATEST close (not a stale month-end), and the rules are not mislabeled.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

import beat_spy


def _args():
    return SimpleNamespace(equity="SPY", bond="AGG", ma=200, mom=200, buffer=1.5)


def _frame(values):
    idx = pd.bdate_range("2023-01-02", periods=len(values), tz="UTC")
    return pd.DataFrame({"open": values, "high": values, "low": values,
                         "close": values, "volume": [1e6] * len(values)}, index=idx)


def test_uptrend_is_risk_on():
    eq = _frame(np.linspace(100, 200, 300))      # steadily rising
    bond = _frame(np.linspace(100, 100, 300))    # flat bonds
    a = _args()
    for key in ("200d_timing", "abs_momentum", "dual_momentum", "spy_or_bonds"):
        s = beat_spy._one_signal(key, eq, bond, a)
        assert s["alloc"] == "EQ", f"{key} should be risk-on in an uptrend"


def test_downtrend_is_defensive():
    eq = _frame(np.linspace(200, 100, 300))      # steadily falling
    bond = _frame(np.linspace(100, 100, 300))
    a = _args()
    # timing/momentum go to cash; spy_or_bonds goes to bonds (not equity)
    assert beat_spy._one_signal("200d_timing", eq, bond, a)["alloc"] == "CASH"
    assert beat_spy._one_signal("abs_momentum", eq, bond, a)["alloc"] == "CASH"
    assert beat_spy._one_signal("spy_or_bonds", eq, bond, a)["alloc"] != "EQ"


def test_signal_uses_latest_close_not_stale_month_end():
    # price ends just below its MA -> timing must read OUT today, even though it
    # was IN for most of the series (the old bug reported it as held-IN).
    vals = np.concatenate([np.linspace(100, 200, 290), np.linspace(200, 150, 10)])
    eq = _frame(vals)
    s = beat_spy._one_signal("200d_timing", eq, None, _args())
    close = float(eq["close"].iloc[-1])
    sma = float(eq["close"].rolling(200).mean().iloc[-1])
    expected = "EQ" if close > sma else "CASH"
    assert s["alloc"] == expected


def test_report_runs_for_all(capsys):
    eq = _frame(np.linspace(100, 200, 300))
    bond = _frame(np.linspace(100, 110, 300))
    keys = ["200d_timing", "200d_buffer", "abs_momentum", "dual_momentum",
            "spy_or_bonds"]
    beat_spy._print_signal_report(keys, eq, bond, _args())
    out = capsys.readouterr().out
    assert "MONTHLY SIGNAL" in out
    assert "TIMING / REGIME signals" in out      # the not-a-3R-setup warning
    assert "abs_momentum" in out and "200d_timing" in out
