"""
Placebo / control tests.

Core question: does the setup's *special* condition add value, or is the result
explained by generic exposure (direction + ATR stop + 3R target) in the same
names over the same era?

`random_date_placebo` builds matched control trades that enter on RANDOM dates
in the SAME symbols, with the SAME direction mix and the SAME stop/target
geometry, then runs them through the identical engine. If the real edge is not
distinguishable from this placebo, the setup fails.

Returns an empirical p-value = P(placebo expectancy >= real expectancy). A
large p-value (e.g. > 0.10) means the special condition is not adding
demonstrable value -> reject.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from ..setups.base import Signal, Direction
from .engine import BacktestEngine, Trade


def _real_expectancy(trades: List[Trade]) -> float:
    if not trades:
        return float("nan")
    return float(np.mean([t.realized_r for t in trades]))


def random_date_placebo(real_trades: List[Trade],
                        bars_by_symbol: Dict[str, pd.DataFrame],
                        engine: BacktestEngine,
                        atr_lookup: Dict[str, pd.Series],
                        n_runs: int = 200, seed: int = 29) -> Dict[str, float]:
    """Compare real expectancy to a distribution of matched random-entry placebos."""
    if not real_trades:
        return {}
    rng = np.random.default_rng(seed)
    real_exp = _real_expectancy(real_trades)
    # preserve per-symbol/direction counts and planned R
    by_sym: Dict[str, list] = {}
    for t in real_trades:
        by_sym.setdefault(t.symbol, []).append(t)

    placebo_exps = []
    for run in range(n_runs):
        sigs: Dict[str, List[Signal]] = {}
        for sym, ts_list in by_sym.items():
            bars = bars_by_symbol[sym]
            atr = atr_lookup[sym]
            n = len(bars)
            picks = rng.integers(20, max(n - 12, 21), size=len(ts_list))
            out = []
            for t, pos in zip(ts_list, picks):
                stime = bars.index[pos]
                entry = float(bars["open"].iloc[min(pos + 1, n - 1)])
                a = float(atr.iloc[pos]) if not np.isnan(atr.iloc[pos]) else entry * 0.02
                is_long = t.direction == "long"
                risk = 1.5 * a
                stop = entry - risk if is_long else entry + risk
                tgt = entry + t.planned_r_multiple * risk if is_long \
                    else entry - t.planned_r_multiple * risk
                out.append(Signal(
                    sym, Direction.LONG if is_long else Direction.SHORT,
                    "placebo", stime, entry, stop, tgt,
                    planned_r_multiple=t.planned_r_multiple,
                    time_stop_bars=10))
            sigs[sym] = out
        placebo_trades = BacktestEngine(
            cost=engine.cost, risk=engine.risk_cfg, sector_map=engine.sector_map,
            enforce_portfolio_risk=False,
        ).run(sigs, bars_by_symbol)
        placebo_exps.append(_real_expectancy(placebo_trades))

    placebo_exps = np.array([x for x in placebo_exps if not np.isnan(x)])
    if len(placebo_exps) == 0:
        return {"real_expectancy_r": real_exp, "p_value": float("nan")}
    p_value = float((placebo_exps >= real_exp).mean())
    return {
        "real_expectancy_r": float(real_exp),
        "placebo_mean_r": float(placebo_exps.mean()),
        "placebo_p95_r": float(np.quantile(placebo_exps, 0.95)),
        "p_value": p_value,
        "passes": bool(p_value < 0.10),
    }
