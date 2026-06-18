"""
Bootstrap confidence intervals + Monte Carlo trade-order analysis.

Provides:
  * iid bootstrap CIs for win rate, expectancy, profit factor
  * stationary block bootstrap (preserves short-run autocorrelation/regime
    clustering) — preferred over plain reshuffling per the spec
  * Monte Carlo reshuffle of trade order for max-drawdown distribution

The 95% CI lower bound for expectancy is a hard acceptance gate: if it is not
clearly above zero, the strategy is labelled STATISTICALLY INCONCLUSIVE.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def _r(trades) -> np.ndarray:
    if isinstance(trades, pd.DataFrame):
        return trades["realized_r"].to_numpy()
    return np.array([t.realized_r for t in trades])


def _stats(r: np.ndarray) -> Dict[str, float]:
    wins, losses = r[r > 0], r[r <= 0]
    gl = -losses.sum()
    pf = wins.sum() / gl if gl > 0 else np.inf
    return {"win_rate": (r > 0).mean(), "expectancy_r": r.mean(),
            "profit_factor": pf if np.isfinite(pf) else 10.0}


def iid_bootstrap(trades, n_boot: int = 5000, seed: int = 13,
                  alpha: float = 0.05) -> Dict[str, dict]:
    r = _r(trades)
    if len(r) < 2:
        return {}
    rng = np.random.default_rng(seed)
    keys = ["win_rate", "expectancy_r", "profit_factor"]
    draws = {k: np.empty(n_boot) for k in keys}
    n = len(r)
    for b in range(n_boot):
        sample = r[rng.integers(0, n, n)]
        s = _stats(sample)
        for k in keys:
            draws[k][b] = s[k]
    out = {}
    for k in keys:
        lo, hi = np.quantile(draws[k], [alpha / 2, 1 - alpha / 2])
        out[k] = {"mean": float(draws[k].mean()), "ci_low": float(lo),
                  "ci_high": float(hi)}
    return out


def block_bootstrap_expectancy(trades, block: int = 10, n_boot: int = 5000,
                               seed: int = 17, alpha: float = 0.05) -> Dict[str, float]:
    """Stationary block bootstrap CI for expectancy (regime-preserving)."""
    r = _r(trades)
    n = len(r)
    if n < block + 1:
        return {}
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for b in range(n_boot):
        out, total = [], 0
        while total < n:
            start = rng.integers(0, n)
            length = rng.geometric(1 / block)
            idx = (start + np.arange(length)) % n
            out.append(r[idx])
            total += length
        means[b] = np.concatenate(out)[:n].mean()
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return {"expectancy_r_mean": float(means.mean()),
            "ci_low": float(lo), "ci_high": float(hi)}


def monte_carlo_drawdown(trades, n_sims: int = 5000, seed: int = 23) -> Dict[str, float]:
    """Distribution of max drawdown (R) under random trade ordering."""
    r = _r(trades)
    if len(r) < 2:
        return {}
    rng = np.random.default_rng(seed)
    dds = np.empty(n_sims)
    for i in range(n_sims):
        perm = rng.permutation(r)
        eq = np.cumsum(perm)
        dds[i] = (np.maximum.accumulate(eq) - eq).max()
    return {"dd_median_r": float(np.median(dds)),
            "dd_p95_r": float(np.quantile(dds, 0.95)),
            "dd_max_r": float(dds.max())}
