"""
Multiple-testing / backtest-overfitting assessment.

Implements pragmatic, documented estimators:
  * deflated_sharpe_ratio: adjusts the observed Sharpe for the number of trials
    (configurations tested) and non-normality (skew/kurtosis), following the
    Bailey & López de Prado construction. Returns the probability the true
    Sharpe is > 0 after deflation.
  * pbo_cscv: Probability of Backtest Overfitting via Combinatorially Symmetric
    Cross-Validation — the fraction of splits where the in-sample-best
    configuration underperforms the median out-of-sample.
  * A simple trials counter so the number of variants tested is reported and a
    Bonferroni-style expectancy hurdle can be applied.

These are estimates with assumptions; they flag risk, they do not certify
safety.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np


def norm_cdf(x: float) -> float:
    """Standard normal CDF via erf (avoids a scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def sharpe(returns: np.ndarray) -> float:
    sd = returns.std(ddof=1)
    return float(returns.mean() / sd) if sd > 0 else 0.0


def deflated_sharpe_ratio(returns: np.ndarray, n_trials: int) -> dict:
    """Return observed SR (per-trade), the deflation benchmark, and P(SR>0)."""
    n = len(returns)
    if n < 3:
        return {}
    sr = sharpe(returns)
    g = returns
    mu, sd = g.mean(), g.std(ddof=1)
    skew = float(((g - mu) ** 3).mean() / (sd ** 3 + 1e-12))
    kurt = float(((g - mu) ** 4).mean() / (sd ** 4 + 1e-12))

    # expected max Sharpe across n_trials independent N(0,1) trials
    e = 0.5772156649
    z1 = _inv_norm(1 - 1.0 / max(n_trials, 1))
    z2 = _inv_norm(1 - 1.0 / (max(n_trials, 1) * e))
    sr0 = z1 * (1 - e) + z2 * e  # expected max under the null (per-trade SR units)
    sr0 /= math.sqrt(max(n - 1, 1))  # scale to the estimator's std error grid

    # variance of the SR estimator (non-normal adjustment)
    denom = math.sqrt(max((1 - skew * sr + (kurt - 1) / 4 * sr ** 2) / (n - 1), 1e-9))
    dsr = norm_cdf((sr - sr0) / denom)
    return {"sharpe_per_trade": sr, "deflation_benchmark_sr0": float(sr0),
            "prob_sr_positive_deflated": float(dsr), "n_trials": n_trials,
            "skew": skew, "kurtosis": kurt}


def pbo_cscv(perf_matrix: np.ndarray, n_splits: int = 16, seed: int = 31) -> dict:
    """Probability of Backtest Overfitting.

    perf_matrix: shape (T, C) of per-period performance for C configurations.
    Splits periods into two halves many ways; checks how often the IS-best
    config ranks below median OOS.
    """
    T, C = perf_matrix.shape
    if C < 2 or T < 4:
        return {}
    rng = np.random.default_rng(seed)
    half = T // 2
    logits = []
    for _ in range(n_splits):
        idx = rng.permutation(T)
        is_idx, oos_idx = idx[:half], idx[half:]
        is_perf = perf_matrix[is_idx].mean(axis=0)
        oos_perf = perf_matrix[oos_idx].mean(axis=0)
        best = int(np.argmax(is_perf))
        # rank of the IS-best in OOS (0..1)
        rank = (oos_perf <= oos_perf[best]).mean()
        rank = min(max(rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(rank / (1 - rank)))
    logits = np.array(logits)
    pbo = float((logits <= 0).mean())  # fraction where best IS underperforms OOS median
    return {"pbo": pbo, "n_splits": n_splits, "n_configs": C}


def bonferroni_expectancy_hurdle(base_alpha: float, n_trials: int) -> float:
    """Adjusted significance level after testing n_trials variants."""
    return base_alpha / max(n_trials, 1)


def _inv_norm(p: float) -> float:
    """Acklam's inverse normal CDF approximation."""
    p = min(max(p, 1e-9), 1 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
