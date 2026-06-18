"""
Acceptance / rejection labeling.

Maps an evidence bundle to one of the four labels (never "proven/guaranteed/
safe"):
  REJECTED
  STATISTICALLY INCONCLUSIVE
  TENTATIVE — FOR PAPER OBSERVATION ONLY
  ROBUST — ELIGIBLE FOR FORWARD OBSERVATION ONLY

A strategy reaches ROBUST only when EVERY acceptance gate passes. Anything that
clears the statistical bar but has a soft failure (e.g. thin sample, one weak
regime, holdout merely flat) is TENTATIVE. CI-low <= 0 forces at most
STATISTICALLY INCONCLUSIVE. Hard failures (negative OOS expectancy, PF < 1.30,
failed placebo/concentration, negative holdout) force REJECTED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from . import params

LABEL_REJECTED = "REJECTED"
LABEL_INCONCLUSIVE = "STATISTICALLY INCONCLUSIVE"
LABEL_TENTATIVE = "TENTATIVE — FOR PAPER OBSERVATION ONLY"
LABEL_ROBUST = "ROBUST — ELIGIBLE FOR FORWARD OBSERVATION ONLY"


@dataclass
class Evidence:
    n_oos_trades: int
    oos_win_rate: float
    oos_expectancy_r: float
    oos_profit_factor: float
    oos_expectancy_ci_low: float
    planned_target_r: float
    holdout_expectancy_r: Optional[float]
    regime_positive_fraction: float
    param_stable: bool
    concentration_passes: bool
    placebo_passes: bool
    cost_stress_survives: bool
    gap_tail_rate: float
    n_trials_tested: int = 1
    pbo: Optional[float] = None


@dataclass
class Verdict:
    label: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def evaluate(e: Evidence) -> Verdict:
    reasons, warnings = [], []

    # ---- HARD REJECTIONS ----
    # NOTE: there is intentionally no minimum-R requirement. A high planned R
    # is neither required nor sufficient; expectancy/PF/robustness decide.
    if e.oos_expectancy_r <= 0:
        reasons.append(f"OOS expectancy {e.oos_expectancy_r:.3f}R not positive")
    if e.oos_profit_factor < params.MIN_PROFIT_FACTOR:
        reasons.append(f"OOS profit factor {e.oos_profit_factor:.2f} "
                       f"< {params.MIN_PROFIT_FACTOR}")
    if not e.concentration_passes:
        reasons.append("fails concentration test (edge driven by few trades/names)")
    if not e.placebo_passes:
        reasons.append("fails placebo test (special condition adds no edge)")
    if not e.cost_stress_survives:
        reasons.append("edge does not survive cost/slippage stress")
    if e.holdout_expectancy_r is not None and e.holdout_expectancy_r < 0:
        reasons.append(f"holdout expectancy {e.holdout_expectancy_r:.3f}R negative")
    if reasons:
        return Verdict(LABEL_REJECTED, reasons, warnings)

    # ---- STATISTICAL CONFIDENCE ----
    if e.oos_expectancy_ci_low <= 0:
        warnings.append("95% CI for expectancy includes zero")
        return Verdict(LABEL_INCONCLUSIVE, reasons, warnings)
    if e.n_oos_trades < params.MIN_OOS_TRADES:
        warnings.append(f"only {e.n_oos_trades} OOS trades (< {params.MIN_OOS_TRADES})")
        return Verdict(LABEL_INCONCLUSIVE, reasons, warnings)
    if e.pbo is not None and e.pbo > 0.5:
        warnings.append(f"PBO {e.pbo:.2f} > 0.50 (overfitting risk)")
        return Verdict(LABEL_INCONCLUSIVE, reasons, warnings)

    # ---- SOFT FLAGS -> TENTATIVE ----
    if e.oos_win_rate <= 0.50:
        warnings.append(f"OOS win rate {e.oos_win_rate:.1%} <= 50% "
                        "(payoff distribution must justify expectancy)")
    if e.n_oos_trades < params.PREFERRED_OOS_TRADES:
        warnings.append(f"{e.n_oos_trades} OOS trades "
                        f"(< {params.PREFERRED_OOS_TRADES} preferred)")
    if e.regime_positive_fraction < 0.6:
        warnings.append("positive in fewer than 60% of tested regimes")
    if not e.param_stable:
        warnings.append("parameter sensitivity elevated near chosen values")
    if e.holdout_expectancy_r is not None and e.holdout_expectancy_r == 0:
        warnings.append("holdout flat (not negative, not clearly positive)")
    if e.gap_tail_rate > 0.10:
        warnings.append(f"gap-tail losses (> 1R) on {e.gap_tail_rate:.1%} of trades")
    if e.n_trials_tested > 20:
        warnings.append(f"{e.n_trials_tested} variants tested — multiple-testing risk")

    if warnings:
        return Verdict(LABEL_TENTATIVE, reasons, warnings)
    return Verdict(LABEL_ROBUST, reasons, warnings)
