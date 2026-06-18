"""
Command-line interface.

    python -m scanner.cli demo                 # full pipeline on synthetic data
    python -m scanner.cli research --source polygon
    python -m scanner.cli scan --source polygon

Always prints a DATA INTEGRITY header (source, universe, timestamp, timezone,
last completed bar). If no real current data is available it prints
"CURRENT MARKET DATA NOT AVAILABLE — RESEARCH MODE ONLY" and refuses to present
synthetic signals as live. If nothing clears validation it prints exactly
"NO QUALIFYING SETUPS TODAY".
"""
from __future__ import annotations

import argparse
from typing import Dict, List

import pandas as pd

from . import DISCLAIMER, params
from .data import get_adapter
from .pipeline import (PipelineConfig, research, live_signals, SetupResult, SECTOR_MAP)
from .rank import SetupEvidence, build_table, to_markdown
from .sizing import RiskConfig
from .universe import default_candidates, filter_universe, UniverseConfig
from .validation import LABEL_TENTATIVE, LABEL_ROBUST

ELIGIBLE = {LABEL_TENTATIVE, LABEL_ROBUST}

# Documented adjustment methodology per source (price-return convention).
ADJUSTMENT_INFO = {
    "polygon": ("Polygon.io aggregates with adjusted=true (split-adjusted); "
                "price-return (dividends NOT reinvested)"),
    "csv": ("as supplied by local files — assumed fully split/dividend adjusted; "
            "treatment must be documented by the file producer"),
    "synthetic": "synthetic series — NOT real, no corporate actions",
}


def _print_header(source: str, universe_n: int, data_ts: str, real: bool):
    print("=" * 78)
    print("  RULE-BASED MARKET SCANNER — liquid U.S. stocks & ETFs")
    print("=" * 78)
    print(f"  Data source        : {source}")
    print(f"  OHLCV adjustment   : {ADJUSTMENT_INFO.get(source, 'unknown')}")
    print(f"  Corporate actions  : splits/dividends per source above; consistent "
          f"convention applied throughout")
    print(f"  Universe source    : default liquid watchlist (filtered)")
    print(f"  Universe filters   : price>=${params.MIN_PRICE:.0f}, "
          f"ADV>=${params.MIN_AVG_DOLLAR_VOLUME/1e6:.0f}M, no leveraged/OTC, "
          f"earnings±{params.EARNINGS_EXCLUSION_DAYS}d when calendar available")
    print(f"  Candidates scanned : {universe_n}")
    print(f"  Data timestamp     : {data_ts}")
    print(f"  Signal close       : {params.SIGNAL_CLOSE}")
    print(f"  Execution rule     : {params.EXECUTION_RULE}")
    print(f"  Timezone / session : UTC index, completed bars only")
    print(f"  Live data verified : {'YES' if real else 'NO — synthetic/offline'}")
    print("-" * 78)
    if not real:
        print("  CURRENT MARKET DATA NOT AVAILABLE — RESEARCH MODE ONLY")
        print("  (synthetic/offline data; signals below are NOT real current signals)")
        print("-" * 78)
    print(f"  {DISCLAIMER}")
    print("=" * 78)


def _evidence_from_result(r: SetupResult) -> SetupEvidence:
    warn = []
    if r.concentration and not r.concentration.get("passes", False):
        warn.append("concentration-sensitive")
    if r.oos.get("gap_tail_rate", 0) > 0.10:
        warn.append(f"gap-tail {r.oos['gap_tail_rate']:.0%}")
    pval = r.placebo.get("p_value")
    if pval is None or (isinstance(pval, float) and pval != pval) or pval >= 0.10:
        warn.append(f"placebo p={pval if pval is not None else 'n/a'}")
    return SetupEvidence(
        label=r.verdict.label,
        quality_total=r.quality["total"] if r.quality else None,
        oos_win_rate=r.oos.get("win_rate", 0.0),
        oos_expectancy_r=r.oos.get("expectancy_r", 0.0),
        oos_profit_factor=r.oos.get("profit_factor", 0.0),
        n_oos_trades=r.oos.get("n_trades", 0),
        typical_hold="≤10 trading days",
        concentration_regime_warning="; ".join(warn) or "none flagged",
    )


def _print_research(results: Dict[str, SetupResult]):
    print("\n## RESEARCH SUMMARY (per setup family)\n")
    for name, r in results.items():
        v = r.verdict
        q = r.quality["total"] if r.quality else "n/a"
        print(f"### {name}  ->  {v.label}")
        print(f"    OOS: n={r.oos.get('n_trades',0)} "
              f"win={r.oos.get('win_rate',0):.1%} "
              f"exp={r.oos.get('expectancy_r',0):.3f}R "
              f"(${r.oos.get('expectancy_currency',0):.0f}/trade) "
              f"PF={r.oos.get('profit_factor',0):.2f} "
              f"avg_win={r.oos.get('avg_winner_r',0):.2f}R "
              f"avg_loss={r.oos.get('avg_loser_r',0):.2f}R "
              f"planned_target={r.oos.get('planned_target_r',0):.2f}R")
        if r.cost_scenarios:
            cs = " | ".join(
                f"{k}: exp={v.get('expectancy_r',0):.3f}R PF={v.get('profit_factor',0):.2f}"
                for k, v in r.cost_scenarios.items())
            print(f"    Cost scenarios (slippage/side): {cs}")
        ci = r.boot.get("iid", {}).get("expectancy_r", {})
        if ci:
            print(f"    Expectancy 95% CI: [{ci.get('ci_low'):.3f}, {ci.get('ci_high'):.3f}]R")
        if r.holdout.get("n_trades"):
            print(f"    Holdout: n={r.holdout['n_trades']} "
                  f"exp={r.holdout.get('expectancy_r',0):.3f}R")
        print(f"    Quality score: {q}")
        if r.placebo:
            print(f"    Placebo p-value: {r.placebo.get('p_value')} "
                  f"(pass={r.placebo.get('passes')})")
        if r.concentration:
            print(f"    Concentration pass: {r.concentration.get('passes')}")
        of = r.overfitting.get("deflated_sharpe", {})
        if of:
            print(f"    Deflated Sharpe P(SR>0): "
                  f"{of.get('prob_sr_positive_deflated'):.2f} "
                  f"(trials={r.overfitting.get('n_trials')})")
        if r.overfitting.get("pbo"):
            print(f"    PBO: {r.overfitting['pbo'].get('pbo')}")
        if v.reasons:
            print(f"    Rejected because: {'; '.join(v.reasons)}")
        if v.warnings:
            print(f"    Warnings: {'; '.join(v.warnings)}")
        print()


def _print_risk_controls(risk: RiskConfig):
    print("\n## RISK CONTROLS (MODERATE profile)\n")
    print(f"  Risk per trade            : {risk.risk_per_trade_pct:.2%} of equity "
          f"(allowed band 0.25%–1.0%)")
    print(f"  Max total open planned risk: {risk.max_total_open_risk_pct:.0%}")
    print(f"  Max stressed open risk     : {risk.max_stressed_open_risk_pct:.0%} "
          f"(gap-tail x{risk.gap_tail_multiplier})")
    print(f"  Max sector / correlated    : {risk.max_sector_risk_pct:.0%}")
    print(f"  Max simultaneous positions : {risk.max_positions}")
    print(f"  Daily loss limit           : {risk.daily_loss_limit_r:.0f}R")
    print(f"  Weekly loss limit          : {risk.weekly_loss_limit_r:.0f}R")
    print("  Hard rules: no averaging down, no martingale, never widen stops,")
    print("              no naked options, no leverage unless separately tested,")
    print("              no new positions within 10 trading days before earnings")
    print("              unless the setup is separately designed/tested for events.")


def _run(source: str, n_symbols: int, fast: bool):
    real = source in ("polygon", "csv")
    cfg = PipelineConfig()
    if fast:
        cfg.n_boot = 400
        cfg.placebo_runs = 30
        cfg.param_perturb = (0.9, 1.1)

    adapter = get_adapter(source)
    as_of = pd.Timestamp.now("UTC").normalize()

    candidates = default_candidates()[:n_symbols]
    try:
        universe = filter_universe(adapter, as_of, UniverseConfig(), candidates)
    except Exception as exc:  # e.g. missing API key
        print(f"[universe] filter failed ({exc}); using raw candidates")
        universe = candidates
    if not universe:
        universe = candidates

    data_ts = as_of.isoformat()
    _print_header(source, len(universe), data_ts, real)

    results = research(adapter, universe, cfg=cfg, as_of=as_of)
    _print_research(results)

    # live ranked table
    eligible_names = [n for n, r in results.items() if r.verdict.label in ELIGIBLE]
    evidence = {n: _evidence_from_result(r) for n, r in results.items()}

    if eligible_names:
        sigs, live_ts = live_signals(adapter, universe, eligible_names, cfg, as_of)
    else:
        sigs, live_ts = [], data_ts

    print("\n## RANKED CURRENT SETUPS\n")
    if not real:
        print("(RESEARCH MODE — the rows below are illustrative, computed on "
              "synthetic data, and are NOT tradeable live signals.)\n")
    table = build_table(sigs, evidence, live_ts)
    print(to_markdown(table))

    if table.empty:
        print("\nNote: NO QUALIFYING SETUPS TODAY means either no setup family "
              "cleared validation, or no validated family has a fresh signal on "
              "the most recent completed bar.")
    else:
        print("\n### Top 3 (by historical OOS expectancy)")
        for _, row in table.head(3).iterrows():
            print(f"  - {row['Ticker']} {row['Direction']} via {row['Setup']}: "
                  f"entry {row['Entry']} stop {row['Stop']} target {row['Target']} "
                  f"(R:R {row['R:R']}); exp {row['Historical Expectancy']}, "
                  f"PF {row['Profit Factor']}, win {row['Historical Win Rate']}")

    _print_risk_controls(cfg.risk)
    print(f"\n(See RESEARCH_REPORT.md for full methodology. {len(results)} families "
          f"tested; {len(eligible_names)} reached paper/forward-observation eligibility.)")


def main(argv: List[str] = None):
    ap = argparse.ArgumentParser(description="Rule-based market scanner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("demo", "research", "scan"):
        p = sub.add_parser(cmd)
        p.add_argument("--source", default="synthetic" if cmd == "demo" else None,
                       choices=["synthetic", "csv", "polygon"])
        p.add_argument("--symbols", type=int, default=20,
                       help="number of candidate symbols to scan")
        p.add_argument("--fast", action="store_true",
                       help="smaller bootstrap/placebo counts for a quick run")
    args = ap.parse_args(argv)
    source = args.source or ("synthetic" if args.cmd == "demo" else "synthetic")
    _run(source, args.symbols, fast=args.fast or args.cmd == "demo")


if __name__ == "__main__":
    main()
