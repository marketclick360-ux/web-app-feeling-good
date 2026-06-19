"""
Concentration gate: it must REJECT edges carried by a single ticker / a few
winners, but must NOT falsely reject a setup that is diversified across many
tickers yet happens to span a single sector or a single (short) OOS year.
"""
from types import SimpleNamespace

import numpy as np

from scanner.backtest.concentration import run_concentration
from scanner.validation import evaluate, Evidence, LABEL_REJECTED
from scanner import params


def _t(symbol, sector, year, r):
    # trades_to_frame builds a DataFrame from each object's __dict__, so a
    # SimpleNamespace with the fields concentration reads is enough.
    return SimpleNamespace(symbol=symbol, sector=sector, year=year, realized_r=r)


def _trades(specs):
    return [_t(*s) for s in specs]


def test_single_ticker_fails_gate():
    # 20 trades, all one ticker, even if profitable -> maximal concentration.
    trades = _trades([("SLV", "METALS", 2025, 2.5 if i % 2 else -0.8)
                      for i in range(20)])
    conc = run_concentration(trades)
    assert conc["passes"] is False
    assert conc["drop_best_symbol"]["expectancy_r"] != conc["drop_best_symbol"]["expectancy_r"]  # NaN


def test_edge_dies_without_best_ticker_fails_gate():
    # SLV carries everything; a couple of other names are net losers.
    specs = [("SLV", "METALS", 2025, 3.0) for _ in range(18)]
    specs += [("GLD", "METALS", 2025, -0.9) for _ in range(6)]
    specs += [("XLE", "ENERGY", 2025, -0.9) for _ in range(6)]
    conc = run_concentration(_trades(specs))
    # removing SLV must turn expectancy negative -> fails
    assert conc["drop_best_symbol"]["expectancy_r"] <= 0
    assert conc["passes"] is False


def test_diversified_single_sector_single_year_not_falsely_rejected():
    # Many tickers, all same sector, all one year, broad-based positive edge.
    rng = np.random.default_rng(0)
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]
    specs = []
    for tk in tickers:
        for _ in range(12):
            # +1.6R winners ~55% of the time, -1R losers otherwise: positive,
            # and no single ticker or handful of winners carries it.
            specs.append((tk, "TECH", 2025, 1.6 if rng.random() < 0.55 else -1.0))
    conc = run_concentration(_trades(specs))
    # sector/year tests are skipped (one group each); they must NOT appear as
    # failures, and the symbol + top-winner tests should survive.
    assert "drop_best_sector" not in conc
    assert "drop_best_year" not in conc
    assert conc["drop_best_symbol"]["expectancy_r"] > 0
    assert conc["passes"] is True


def _evidence(concentration_passes):
    # adequate, otherwise-passing evidence; only concentration toggled
    return Evidence(
        n_oos_trades=params.MIN_OOS_TRADES + 20,
        oos_win_rate=0.55,
        oos_expectancy_r=0.20,
        oos_profit_factor=1.6,
        oos_expectancy_ci_low=0.05,
        planned_target_r=3.0,
        holdout_expectancy_r=0.1,
        regime_positive_fraction=0.8,
        param_stable=True,
        concentration_passes=concentration_passes,
        placebo_passes=True,
        cost_stress_survives=True,
        gap_tail_rate=0.02,
        n_trials_tested=5,
        pbo=0.1,
    )


def test_validation_rejects_when_concentration_fails():
    v = evaluate(_evidence(concentration_passes=False))
    assert v.label == LABEL_REJECTED
    assert any("concentration" in r.lower() for r in v.reasons)


def test_validation_keeps_when_concentration_passes():
    v = evaluate(_evidence(concentration_passes=True))
    assert v.label != LABEL_REJECTED
