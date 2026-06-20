"""
Defensive-model exit simulator: each of the 6 exit models must behave exactly
as specified on hand-built bars, with NO costs so the realized R is exact.

These lock in the bits that are easy to get subtly wrong: breakeven actually
protects (exits ~0R, not -1R), the partial banks half at +1R, and the trailing
stop locks in profit after +1.5R.
"""
import numpy as np
import pandas as pd

from scanner.costs import CostModel
from scanner import defensive as D

ZERO = CostModel(commission_per_share=0.0, min_commission=0.0, sec_taf_bps=0.0,
                 spread_bps=0.0, slippage_frac=0.0, delay_bars=1)


def _bars(rows):
    """rows: list of (open, high, low, close). Index is business days, UTC."""
    idx = pd.bdate_range("2024-01-01", periods=len(rows), tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1_000_000
    return df


def _sim(rows, variant, entry_ref=100.0, init_stop=99.0, is_long=True,
         time_stop=10):
    df = _bars(rows)
    # signal on bar 0 -> fill on bar 1 (delay_bars=1)
    return D._simulate_variant(df, 1, is_long, entry_ref, init_stop,
                               time_stop, variant, ZERO)


def test_target_2r_winner_is_exactly_two_r():
    rows = [(100, 100, 100, 100),          # signal bar
            (100, 100.5, 99.5, 100.2),     # fill bar, nothing hit
            (100.5, 102.5, 100.0, 102.2)]  # +2R target (102) touched
    r = _sim(rows, "target_2R")
    assert r["exit_reason"] == "target"
    assert abs(r["realized_r"] - 2.0) < 1e-9


def test_stop_loss_is_minus_one_r():
    rows = [(100, 100, 100, 100),
            (100, 100.2, 98.5, 99.0)]      # low pierces the -1R stop (99)
    r = _sim(rows, "target_2R")
    assert r["exit_reason"] == "stop"
    assert abs(r["realized_r"] - (-1.0)) < 1e-9


def test_breakeven_protects_after_one_r():
    # price tags +1R then falls back through entry -> should exit ~0R, NOT -1R
    rows = [(100, 100, 100, 100),
            (100, 100.2, 99.5, 100.1),     # fill bar
            (100.3, 101.2, 100.5, 101.0),  # +1R (101) touched -> arm breakeven
            (100.4, 100.6, 99.8, 99.9)]    # falls to 99.8: breakeven stop (100) hit
    r = _sim(rows, "breakeven_then_2R")
    assert r["exit_reason"] == "stop"
    assert abs(r["realized_r"] - 0.0) < 1e-9   # breakeven, not a loss


def test_partial_banks_half_at_one_r():
    rows = [(100, 100, 100, 100),
            (100, 100.2, 99.6, 100.1),     # fill bar
            (100.3, 101.3, 100.4, 101.0),  # +1R -> sell half (bank +0.5R), BE on rest
            (100.2, 100.6, 99.9, 100.0)]   # rest stopped at breakeven (100)
    r = _sim(rows, "partial_1R_2R")
    assert abs(r["realized_r"] - 0.5) < 1e-9


def test_trailing_locks_in_profit_after_one_and_half_r():
    rows = [(100, 100, 100, 100),
            (100, 100.2, 99.6, 100.1),     # fill bar
            (100.4, 101.6, 101.0, 101.5),  # +1.5R -> arm trail; stop -> 100.6
            (101.0, 102.0, 101.2, 101.8),  # new high 102 -> trail stop -> 101.0
            (101.1, 101.3, 100.5, 100.8)]  # low 100.5 < 101.0 -> trailed stop hit
    r = _sim(rows, "trail_after_1.5R")
    assert r["exit_reason"] == "stop"
    assert abs(r["realized_r"] - 1.0) < 1e-9   # locked in +1R, not a loss


def test_time_stop_exits_at_next_open():
    rows = [(100, 100, 100, 100),
            (100, 100.3, 99.5, 100.0),     # fill bar, drift sideways
            (100.0, 100.4, 99.6, 100.1),
            (100.1, 100.3, 99.7, 100.0)]   # time_stop=2 -> exit at this open (100.1)
    r = _sim(rows, "target_2R", time_stop=2)
    assert r["exit_reason"] == "time"
    assert abs(r["realized_r"] - ((100.1 - 100.0))) < 1e-9


def test_short_winner_reaches_target():
    rows = [(100, 100, 100, 100),
            (100, 100.4, 99.6, 99.8),      # fill bar
            (99.5, 99.6, 97.8, 98.0)]      # low 97.8 <= 98 (-2R for a short)
    r = _sim(rows, "target_2R", init_stop=101.0, is_long=False)
    assert r["exit_reason"] == "target"
    assert abs(r["realized_r"] - 2.0) < 1e-9


def test_filter_series_shapes():
    idx = pd.bdate_range("2020-01-01", periods=400, tz="UTC")
    up = pd.Series(np.linspace(100, 200, 400), index=idx)
    bench = pd.DataFrame({"close": up})
    assert D._filter_series("none", bench, None) is None
    s = D._filter_series("spy_200d", bench, None)
    assert s.iloc[-1]  # steady uptrend -> above its 200d MA, risk-on
    a = D._filter_series("abs_momentum", bench, None)
    assert a.iloc[-1]  # 12-month return positive


def test_label_rejects_negative_and_concentration():
    neg = {"n": 200, "expectancy_r": -0.1, "profit_factor": 0.8, "win_rate": 0.4,
           "ci_low": -0.2, "gap_tail_rate": 0.05}
    conc_ok = {"passes": True}
    label, _ = D._label(neg, conc_ok, planned_r=2.0)
    assert label == "REJECTED"

    pos = {"n": 200, "expectancy_r": 0.2, "profit_factor": 1.5, "win_rate": 0.55,
           "ci_low": 0.05, "gap_tail_rate": 0.05}
    conc_bad = {"passes": False, "best_ticker": "SLV", "best_share": 0.7,
                "exp_without_best": -0.1}
    label2, _ = D._label(pos, conc_bad, planned_r=2.0)
    assert label2 == "REJECTED"  # edge is concentration-driven


def test_label_rejects_sub_floor_target():
    m = {"n": 200, "expectancy_r": 0.2, "profit_factor": 1.5, "win_rate": 0.55,
         "ci_low": 0.05, "gap_tail_rate": 0.05}
    label, _ = D._label(m, {"passes": True}, planned_r=1.5)
    assert label == "REJECTED"  # 1.5R < 2.0R defensive design floor
