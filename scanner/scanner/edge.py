"""
Edge mode — validate setup FAMILIES, grade them, and bucket them before any
current trade candidate is shown.

This sits on top of pipeline.research() (which does the heavy backtest +
validation per family) and adds:
  * a per-family scorecard (counts, win/expectancy/PF, drawdown, regime
    breakdown, concentration warning, target sweep, frequency)
  * an EDGE SCORE (0-100) combining 8 components
  * a FREQUENCY score (flags < 1 signal/month; highlights the 2-6/month band)
  * a letter GRADE (A+ … F) gated by sample size and the 3R rule
  * four buckets: Validated Edge / Paper-Only / Watchlist / Rejected

HARD RULES honoured here:
  * n = 0  -> NO SAMPLE (never fabricate expectancy / PF / confidence)
  * OOS < 100 -> STATISTICALLY INCONCLUSIVE (no edge claims)
  * only the 3R variant can be an accepted forward-test candidate; 2R / 2.5R
    are diagnostic only
  * nothing is called profitable — all results are HYPOTHETICAL and require
    forward testing
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import params
from .backtest import metrics
from .validation import (LABEL_ROBUST, LABEL_TENTATIVE, LABEL_INCONCLUSIVE,
                         LABEL_REJECTED, LABEL_NO_SAMPLE)

# output buckets
BUCKET_VALIDATED = "A. VALIDATED EDGE CANDIDATES"
BUCKET_PAPER = "B. PAPER-ONLY CANDIDATES"
BUCKET_WATCHLIST = "C. WATCHLIST — INTERESTING BUT UNPROVEN"
BUCKET_REJECTED = "D. REJECTED"

IDEAL_FREQ_LOW, IDEAL_FREQ_HIGH = 2.0, 6.0   # signals/month sweet spot


def _clip01(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


@dataclass
class EdgeReport:
    family: str
    n_symbols: int
    label: str
    sample_status: str            # OK | NO SAMPLE | INCONCLUSIVE
    is_trades: int
    oos_trades: int
    signals_per_month: float
    trades_per_month: float
    win_rate: Optional[float]
    avg_win_r: Optional[float]
    avg_loss_r: Optional[float]
    expectancy_r: Optional[float]
    profit_factor: Optional[float]
    max_dd_r: Optional[float]
    ci_low: Optional[float]
    regime_consistency: Optional[float]
    regime_breakdown: list
    concentration_warning: str
    target_sweep: dict
    frequency_tag: str
    edge_score: Optional[float]
    edge_components: dict
    grade: str
    bucket: str
    reasons: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _frequency_tag(spm: float) -> str:
    if spm <= 0:
        return "NONE (0/mo)"
    if spm < 1.0:
        return f"TOO SPARSE ({spm:.2f}/mo, < 1/mo)"
    if IDEAL_FREQ_LOW <= spm <= IDEAL_FREQ_HIGH:
        return f"IDEAL ({spm:.1f}/mo — matches ~2 trades/wk goal)"
    if spm > 20:
        return f"TOO BUSY ({spm:.1f}/mo)"
    return f"OK ({spm:.1f}/mo)"


def _frequency_component(spm: float) -> float:
    """0..1: full credit in the 2-6/mo band, penalties outside."""
    if spm <= 0:
        return 0.0
    if spm < 1.0:
        return 0.2 * spm            # ramp 0..0.2 below 1/mo
    if spm < IDEAL_FREQ_LOW:
        return 0.5 + 0.5 * (spm - 1.0) / (IDEAL_FREQ_LOW - 1.0)
    if spm <= IDEAL_FREQ_HIGH:
        return 1.0
    if spm <= 20:
        return _clip01(1.0 - (spm - IDEAL_FREQ_HIGH) / (20 - IDEAL_FREQ_HIGH) * 0.6)
    return 0.3


def _concentration_warning(conc: dict) -> str:
    if not conc:
        return "n/a (no sample)"
    base = conc.get("baseline", {}).get("expectancy_r")
    if base is None or base <= 0:
        return "n/a"
    flags = []
    for dim, label in (("drop_best_symbol", "one ticker"),
                       ("drop_best_sector", "one sector"),
                       ("drop_best_year", "one year")):
        v = conc.get(dim, {})
        if not isinstance(v, dict):
            continue
        exp = v.get("expectancy_r", 1)
        if exp is None:
            continue
        # NaN (e.g. only one ticker total) or non-positive both signal that the
        # edge does not survive removing the single biggest contributor.
        if (isinstance(exp, float) and exp != exp) or exp <= 0:
            removed = v.get("removed")
            who = f" ({removed})" if removed not in (None, "") else ""
            tail = (" — only one ticker, maximal concentration"
                    if isinstance(exp, float) and exp != exp
                    else f" → expectancy {exp:.3f}R")
            flags.append(f"{label}{who} dominates{tail}")
    # top winners
    for pct in (0.05,):
        v = conc.get(f"drop_top_{int(pct*100)}pct_winners", {})
        if isinstance(v, dict) and v.get("expectancy_r", 1) <= 0:
            flags.append("top 5% of winners drive the edge")
    return "; ".join(flags) if flags else "none (robust to removals)"


def _edge_score(r: EdgeReport, conc: dict) -> (float, dict):
    """8-component edge score, 0-100. Only meaningful when sample_status == OK."""
    exp = r.expectancy_r or 0.0
    ci = r.ci_low if r.ci_low is not None else -1.0
    n = r.oos_trades
    rc = r.regime_consistency or 0.0
    dd = abs(r.max_dd_r) if r.max_dd_r is not None else 1e9
    spm = r.signals_per_month

    c = {}
    c["oos_expectancy_20"] = _clip01(exp / 0.30) * 20
    c["lower_conf_bound_15"] = 15.0 if ci > 0 else _clip01((ci + 0.10) / 0.10) * 6.0
    c["trade_count_15"] = _clip01(n / params.PREFERRED_OOS_TRADES) * 15
    c["regime_consistency_15"] = _clip01(rc) * 15
    c["drawdown_10"] = _clip01(1.0 - dd / 15.0) * 10        # 15R dd -> 0 pts
    c["signal_frequency_10"] = _frequency_component(spm) * 10
    c["concentration_10"] = 10.0 if (conc.get("passes") if conc else False) else 3.0
    # target robustness: expectancy positive & stable across 2/2.5/3R
    sw = r.target_sweep or {}
    exps = [m.get("expectancy_r", 0.0) for m in sw.values() if m]
    if exps and np.mean(exps) > 0:
        disp = np.std(exps) / (abs(np.mean(exps)) + 1e-9)
        c["target_robustness_5"] = _clip01(1.0 - disp) * 5
    else:
        c["target_robustness_5"] = 0.0
    total = round(sum(c.values()), 1)
    return total, {k: round(v, 1) for k, v in c.items()}


def _grade(r: EdgeReport) -> str:
    if r.sample_status == "NO SAMPLE":
        return "F"
    if r.label == LABEL_REJECTED:
        return "F"
    if r.sample_status == "INCONCLUSIVE":
        return "C"                      # interesting but unproven, capped
    s = r.edge_score or 0.0
    # frequency downgrade: an edge nobody can trade < 1/mo is capped
    sparse = r.signals_per_month < 1.0
    if s >= 85 and not sparse:
        return "A+"
    if s >= 75 and not sparse:
        return "A"
    if s >= 65:
        return "B+" if not sparse else "B"
    if s >= 55:
        return "B" if not sparse else "C"
    if s >= 40:
        return "C"
    return "F"


def _bucket(label: str, sample_status: str) -> str:
    if label == LABEL_ROBUST:
        return BUCKET_VALIDATED
    if label == LABEL_TENTATIVE:
        return BUCKET_PAPER
    if label == LABEL_INCONCLUSIVE:
        return BUCKET_WATCHLIST
    return BUCKET_REJECTED   # REJECTED or NO SAMPLE


def build_report(name: str, res, cfg) -> EdgeReport:
    oos = res.oos
    n_oos = oos.get("n_trades", 0)
    months = max(cfg.years * 12.0, 1e-9)
    spm = res.n_signals_raw / months
    tpm = (res.dev.get("n_trades", 0) + n_oos) / months

    if n_oos == 0:
        sample_status = "NO SAMPLE"
    elif n_oos < params.MIN_OOS_TRADES:
        sample_status = "INCONCLUSIVE"
    else:
        sample_status = "OK"

    if sample_status == "NO SAMPLE":
        # never fabricate stats on zero trades
        rpt = EdgeReport(
            family=name, n_symbols=res.n_symbols_tested, label=res.verdict.label,
            sample_status=sample_status, is_trades=res.dev.get("n_trades", 0),
            oos_trades=0, signals_per_month=spm, trades_per_month=tpm,
            win_rate=None, avg_win_r=None, avg_loss_r=None, expectancy_r=None,
            profit_factor=None, max_dd_r=None, ci_low=None,
            regime_consistency=None, regime_breakdown=[],
            concentration_warning="n/a (no sample)", target_sweep={},
            frequency_tag=_frequency_tag(spm), edge_score=None, edge_components={},
            grade="F", bucket=BUCKET_REJECTED,
            reasons=res.verdict.reasons, warnings=res.verdict.warnings)
        return rpt

    reg_bd = metrics.breakdown(res.oos_trades, "regime")
    regime_breakdown = []
    if not reg_bd.empty:
        for _, row in reg_bd.iterrows():
            regime_breakdown.append((row["regime"], int(row["n"]),
                                     float(row["win_rate"]),
                                     float(row["expectancy_r"])))
    sig_regimes = [r for r in regime_breakdown if r[1] >= 5]
    regime_consistency = (np.mean([1.0 if r[3] > 0 else 0.0 for r in sig_regimes])
                          if sig_regimes else 0.0)
    ci_low = res.boot.get("iid", {}).get("expectancy_r", {}).get("ci_low")

    rpt = EdgeReport(
        family=name, n_symbols=res.n_symbols_tested, label=res.verdict.label,
        sample_status=sample_status, is_trades=res.dev.get("n_trades", 0),
        oos_trades=n_oos, signals_per_month=spm, trades_per_month=tpm,
        win_rate=oos.get("win_rate"), avg_win_r=oos.get("avg_winner_r"),
        avg_loss_r=oos.get("avg_loser_r"), expectancy_r=oos.get("expectancy_r"),
        profit_factor=oos.get("profit_factor"), max_dd_r=oos.get("max_drawdown_r"),
        ci_low=ci_low, regime_consistency=float(regime_consistency),
        regime_breakdown=regime_breakdown,
        concentration_warning=_concentration_warning(res.concentration),
        target_sweep=res.target_sweep, frequency_tag=_frequency_tag(spm),
        edge_score=None, edge_components={}, grade="", bucket="",
        reasons=res.verdict.reasons, warnings=res.verdict.warnings)

    score, comps = _edge_score(rpt, res.concentration)
    rpt.edge_score = score if sample_status == "OK" else None
    rpt.edge_components = comps if sample_status == "OK" else {}
    rpt.grade = _grade(rpt)
    rpt.bucket = _bucket(res.verdict.label, sample_status)
    return rpt


def build_reports(results: Dict[str, object], cfg) -> List[EdgeReport]:
    reps = [build_report(name, res, cfg) for name, res in results.items()]
    # rank: by bucket priority, then edge score, then expectancy
    order = {BUCKET_VALIDATED: 0, BUCKET_PAPER: 1, BUCKET_WATCHLIST: 2,
             BUCKET_REJECTED: 3}
    reps.sort(key=lambda r: (order.get(r.bucket, 9), -(r.edge_score or -1),
                             -(r.expectancy_r or -9)))
    return reps


def best_families(reps: List[EdgeReport]) -> List[str]:
    """Families good enough to surface current candidates from (A or B buckets,
    3R-accepted)."""
    return [r.family for r in reps
            if r.bucket in (BUCKET_VALIDATED, BUCKET_PAPER)]
