"""
Setup Quality Score — mathematically defined, no subjective judgment.

Total 100 points, allocated exactly as specified:
  25  OOS expectancy strength & confidence  (expectancy scaled, gated by CI low)
  20  Profit factor after costs & stress     (PF mapped 1.0->0, >=2.0->full)
  15  Robustness across regimes              (fraction of regimes with +expectancy)
  15  Parameter stability                    (1 - normalized expectancy dispersion)
  10  Concentration-test resilience          (pass=full; else scaled by survival)
  10  Placebo-test advantage                 (1 - p_value, floored at 0)
   5  Liquidity & execution practicality     (ADV / frequency feasibility)

If any required input is missing, the score is NOT assigned (returns None) — a
missing-data setup is never ranked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def _clip01(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


@dataclass
class QualityInputs:
    oos_expectancy_r: float
    oos_expectancy_ci_low: float
    profit_factor: float
    regime_positive_fraction: float       # 0..1 of tested regimes with +expectancy
    param_expectancies: list              # expectancies across param perturbations
    concentration_passes: bool
    concentration_min_expectancy: float   # worst stressed expectancy
    placebo_p_value: float
    liquidity_ok: bool
    trades_per_year: float


def score(q: Optional[QualityInputs]) -> Optional[dict]:
    if q is None:
        return None
    required = [q.oos_expectancy_r, q.oos_expectancy_ci_low, q.profit_factor,
                q.regime_positive_fraction, q.placebo_p_value]
    if any(v is None or (isinstance(v, float) and np.isnan(v)) for v in required):
        return None
    if not q.param_expectancies:
        return None

    # 25 — expectancy strength, hard-gated by CI lower bound
    exp_component = _clip01(q.oos_expectancy_r / 0.30) * 25.0
    if q.oos_expectancy_ci_low <= 0:
        exp_component *= 0.4  # heavy penalty when CI includes zero

    # 20 — profit factor (1.0 -> 0 pts, 2.0+ -> full)
    pf = min(q.profit_factor, 3.0)
    pf_component = _clip01((pf - 1.0) / 1.0) * 20.0

    # 15 — regime robustness
    regime_component = _clip01(q.regime_positive_fraction) * 15.0

    # 15 — parameter stability: lower dispersion of expectancy = more stable
    pe = np.array(q.param_expectancies, dtype=float)
    mean_abs = np.abs(pe.mean()) + 1e-9
    dispersion = pe.std(ddof=0) / mean_abs
    stability = _clip01(1.0 - dispersion)
    # also require the perturbed set to stay positive on average
    if pe.mean() <= 0:
        stability *= 0.3
    stability_component = stability * 15.0

    # 10 — concentration resilience
    if q.concentration_passes:
        conc_component = 10.0
    else:
        conc_component = _clip01(q.concentration_min_expectancy / 0.10) * 10.0

    # 10 — placebo advantage
    placebo_component = _clip01(1.0 - q.placebo_p_value) * 10.0

    # 5 — liquidity / execution practicality
    liq = 1.0 if q.liquidity_ok else 0.0
    # penalize implausibly high turnover (execution drag)
    freq_ok = 1.0 if q.trades_per_year <= 250 else _clip01(500 / q.trades_per_year)
    liq_component = liq * freq_ok * 5.0

    components = {
        "expectancy_25": round(exp_component, 2),
        "profit_factor_20": round(pf_component, 2),
        "regime_robustness_15": round(regime_component, 2),
        "param_stability_15": round(stability_component, 2),
        "concentration_10": round(conc_component, 2),
        "placebo_10": round(placebo_component, 2),
        "liquidity_5": round(liq_component, 2),
    }
    total = round(sum(components.values()), 2)
    return {"total": total, "components": components}
