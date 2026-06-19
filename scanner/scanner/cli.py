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
from . import edge as edge_mod
from . import indicators as ind
from . import tradability as trad_mod
from .data import get_adapter
from .pipeline import (PipelineConfig, research, live_signals, SetupResult, SECTOR_MAP)
from .rank import SetupEvidence, build_table, to_markdown
from .sizing import RiskConfig
from .universe import (default_candidates, etf_candidates, filter_universe,
                       small_account_etf_candidates, small_account_config,
                       UniverseConfig)
from .validation import LABEL_TENTATIVE, LABEL_ROBUST

ELIGIBLE = {LABEL_TENTATIVE, LABEL_ROBUST}

# Documented adjustment methodology per source (price-return convention).
ADJUSTMENT_INFO = {
    "polygon": ("Polygon.io aggregates with adjusted=true (split-adjusted); "
                "price-return (dividends NOT reinvested)"),
    "schwab": ("Schwab pricehistory: split-adjusted; price-return (dividends NOT "
               "reinvested); NOT survivorship-bias-free (disclose as limitation)"),
    "stooq": ("Stooq split- & dividend-adjusted daily; NOT survivorship-bias-free (disclose as limitation)"),
    "csv": ("as supplied by local files — assumed fully split/dividend adjusted; "
            "treatment must be documented by the file producer"),
    "synthetic": "synthetic series — NOT real, no corporate actions",
}


def _survivorship_note(adapter, etf_only: bool) -> str:
    sf = getattr(adapter, "survivorship_free", None)
    if sf is True:
        return "NO (survivorship-bias-free source)"
    base = "YES — source lacks delisted tickers/point-in-time constituents"
    if etf_only:
        base += "; reduced by ETF-only universe (indices rarely delist)"
    return base


def _print_header(source: str, universe_n: int, data_ts: str, real: bool,
                  adapter=None, etf_only: bool = False):
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
    if adapter is not None:
        print(f"  Survivorship bias  : {_survivorship_note(adapter, etf_only)}")
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
        if r.target_sweep:
            sw = " | ".join(
                f"{rr:.1f}R: n={m.get('n_trades',0)} exp={m.get('expectancy_r',0):.3f}R "
                f"PF={m.get('profit_factor',0):.2f} win={m.get('win_rate',0):.0%}"
                for rr, m in r.target_sweep.items())
            print(f"    Target sweep (OOS, research only — 3R needed to accept): {sw}")
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
    print("  STAGED SIZING for an UNVALIDATED system (recommended):")
    print("    research / paper        : 0% (no live capital)")
    print("    first tiny live test    : 0.25% per trade")
    print("    after 100+ fwd trades   : up to 0.50%")
    print("    only after strong fwd   : consider the 1.0% shown above")
    print("    evidence")


def _run(source: str, n_symbols: int, fast: bool, years: int = 10,
         etf_only: bool = False):
    real = source in ("polygon", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    if fast:
        cfg.n_boot = 400
        cfg.placebo_runs = 30
        cfg.param_perturb = (0.9, 1.1)

    adapter = get_adapter(source)
    as_of = pd.Timestamp.now("UTC").normalize()

    pool = etf_candidates() if etf_only else default_candidates()
    candidates = pool[:n_symbols]
    try:
        universe = filter_universe(adapter, as_of, UniverseConfig(), candidates)
    except Exception as exc:  # e.g. missing API key
        print(f"[universe] filter failed ({exc}); using raw candidates")
        universe = candidates
    if not universe:
        universe = candidates

    data_ts = as_of.isoformat()
    _print_header(source, len(universe), data_ts, real, adapter=adapter,
                  etf_only=etf_only)

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


def _tradability_map(adapter, universe, as_of, account):
    """Per-symbol tradability from the last completed daily bar."""
    out = {}
    for sym in universe:
        try:
            bars = adapter.get_bars(sym, "1d", start=as_of - pd.Timedelta(days=420),
                                    end=as_of, as_of=as_of).df
        except Exception:
            continue
        if len(bars) < 60:
            continue
        enr = ind.enrich_daily(bars)
        last = enr.iloc[-1]
        price = float(last["close"])
        atr = float(last["atr14"]) if last["atr14"] == last["atr14"] else price * 0.02
        adv = float(last["adv20"]) if last["adv20"] == last["adv20"] else 0.0
        out[sym.upper()] = {"price": price, "atr": atr, "adv": adv,
                            "avg_vol": float(last.get("vol_sma20", 0) or 0),
                            "trad": trad_mod.score(price, adv, atr, 1.5 * atr, account)}
    return out


def _run_edge(source, n_symbols, fast, years, small_account, etf_only, account):
    real = source in ("polygon", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    if fast:
        cfg.n_boot, cfg.placebo_runs, cfg.param_perturb = 400, 30, (0.9, 1.1)

    adapter = get_adapter(source)
    as_of = pd.Timestamp.now("UTC").normalize()

    if small_account:
        ucfg = small_account_config()
        pool = small_account_etf_candidates() if etf_only else \
            (small_account_etf_candidates() + default_candidates())
    else:
        ucfg = UniverseConfig()
        pool = etf_candidates() if etf_only else default_candidates()
    candidates = pool[:n_symbols]
    try:
        universe = filter_universe(adapter, as_of, ucfg, candidates)
    except Exception as exc:
        print(f"[universe] filter failed ({exc}); using raw candidates")
        universe = candidates
    if not universe:
        universe = candidates

    _print_header(source, len(universe), as_of.isoformat(), real,
                  adapter=adapter, etf_only=etf_only)
    print(f"  Mode               : EDGE{' / SMALL-ACCOUNT' if small_account else ''} "
          f"(account ${account:,.0f})")
    _maxp = f"${ucfg.max_price:.0f}" if ucfg.max_price else "∞"
    print(f"  Universe filter    : ADV>=${ucfg.min_adv_dollar/1e6:.0f}M, "
          f"price ${ucfg.min_price:.0f}-{_maxp}, no leveraged/OTC")
    print(f"  Output             : HYPOTHETICAL backtest — requires forward testing; "
          f"no profitability claimed")
    print("=" * 78)

    results = research(adapter, universe, cfg=cfg, as_of=as_of)
    reports = edge_mod.build_reports(results, cfg)
    trad = _tradability_map(adapter, universe, as_of, account) if real else {}

    # ---- per-family scorecards ----
    print("\n## SETUP-FAMILY SCORECARDS\n")
    for r in reports:
        print(f"### {r.family}   [{r.bucket.split('.')[0]}]   grade {r.grade}   "
              f"({r.label})")
        print(f"    symbols tested={r.n_symbols}  IS trades={r.is_trades}  "
              f"OOS trades={r.oos_trades}  signals/mo={r.signals_per_month:.2f}  "
              f"trades/mo={r.trades_per_month:.2f}")
        print(f"    frequency: {r.frequency_tag}")
        if r.sample_status == "NO SAMPLE":
            print("    NO SAMPLE — no OOS trades; no stats computed.")
            print()
            continue
        if r.sample_status == "INCONCLUSIVE":
            print(f"    STATISTICALLY INCONCLUSIVE — {r.oos_trades} OOS trades "
                  f"(< {params.MIN_OOS_TRADES}); edge stats not reliable.")
        print(f"    win={r.win_rate:.1%}  avgWin={r.avg_win_r:.2f}R  "
              f"avgLoss={r.avg_loss_r:.2f}R  exp={r.expectancy_r:.3f}R  "
              f"PF={r.profit_factor:.2f}  maxDD={r.max_dd_r:.1f}R  "
              f"CIlow={r.ci_low if r.ci_low is None else round(r.ci_low,3)}")
        if r.target_sweep:
            sw = " | ".join(f"{rr:.1f}R exp={m.get('expectancy_r',0):.3f} "
                            f"PF={m.get('profit_factor',0):.2f}"
                            for rr, m in r.target_sweep.items())
            print(f"    target sweep (3R needed to accept): {sw}")
        if r.regime_breakdown:
            rb = " | ".join(f"{reg}:exp={exp:.2f}R(n={n})"
                            for reg, n, win, exp in r.regime_breakdown)
            print(f"    regime: {rb}  (consistency {r.regime_consistency:.0%})")
        print(f"    concentration: {r.concentration_warning}")
        if r.edge_score is not None:
            print(f"    EDGE SCORE: {r.edge_score}/100  {r.edge_components}")
        print()

    # ---- four buckets ----
    print("\n## FAMILY BUCKETS\n")
    for bucket in (edge_mod.BUCKET_VALIDATED, edge_mod.BUCKET_PAPER,
                   edge_mod.BUCKET_WATCHLIST, edge_mod.BUCKET_REJECTED):
        members = [r for r in reports if r.bucket == bucket]
        print(f"{bucket}")
        if not members:
            print("   (none)")
        for r in members:
            print(f"   - {r.family}: grade {r.grade}, "
                  f"edge {r.edge_score if r.edge_score is not None else 'n/a'}, "
                  f"{r.frequency_tag}")
        print()

    # ---- current candidates from best (A/B) families ----
    best = edge_mod.best_families(reports)
    print("## CURRENT CANDIDATES (most recent completed bar)\n")
    if not real:
        print("(RESEARCH MODE — synthetic data; illustrative, not tradeable.)")
    if not best:
        print("NO QUALIFYING SETUPS TODAY — no family reached Validated/Paper "
              "status, so no current candidate is surfaced.")
    else:
        sigs, live_ts = live_signals(adapter, universe, best, cfg, as_of)
        if not sigs:
            print(f"No fresh signals on the latest bar ({live_ts}) from the "
                  f"qualifying families: {', '.join(best)}.")
        for s in sigs:
            sym = s.symbol.upper()
            risk = s.risk_per_share
            t = trad.get(sym)
            tg = f"{t['trad'].score}/100 ({t['trad'].grade})" if t else "n/a"
            shares = t['trad'].shares_at_risk if t else {}
            print(f"  {sym} {s.direction.value} via {s.setup_name}")
            print(f"     entry {s.entry_ref:.2f}  stop {s.stop:.2f}  "
                  f"risk/sh {risk:.2f}  ATR {t['atr']:.2f}" if t else
                  f"     entry {s.entry_ref:.2f}  stop {s.stop:.2f}  risk/sh {risk:.2f}")
            d = 1 if s.direction.value == "long" else -1
            print(f"     targets: 2R {s.entry_ref + d*2*risk:.2f}  "
                  f"2.5R {s.entry_ref + d*2.5*risk:.2f}  "
                  f"3R {s.entry_ref + d*3*risk:.2f} (planned)")
            print(f"     small-account tradability: {tg}  shares@risk {shares}")
            print(f"     options suitability: UNKNOWN (needs live options chain)")
            print(f"     status: paper-only candidate (HYPOTHETICAL — forward-test first)")
    print("\nReminder: backtests are hypothetical and do not prove future results. "
          "Paper-trade first; size 0% → 0.25% only after forward evidence.")


def main(argv: List[str] = None):
    ap = argparse.ArgumentParser(description="Rule-based market scanner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("demo", "research", "scan"):
        p = sub.add_parser(cmd)
        p.add_argument("--source", default="synthetic" if cmd == "demo" else None,
                       choices=["synthetic", "csv", "polygon", "schwab", "stooq"])
        p.add_argument("--symbols", type=int, default=20,
                       help="number of candidate symbols to scan")
        p.add_argument("--years", type=int, default=10,
                       help="years of history (use 2 for Polygon free tier)")
        p.add_argument("--fast", action="store_true",
                       help="smaller bootstrap/placebo counts for a quick run")
        p.add_argument("--etf-only", action="store_true", dest="etf_only",
                       help="use the liquid ETF universe (cleaner, less survivorship bias)")

    pe = sub.add_parser("edge", help="validate setup families, grade, bucket, "
                                     "then surface current candidates")
    pe.add_argument("--source", default="synthetic",
                    choices=["synthetic", "csv", "polygon", "schwab", "stooq"])
    pe.add_argument("--symbols", type=int, default=30)
    pe.add_argument("--years", type=int, default=12)
    pe.add_argument("--fast", action="store_true")
    pe.add_argument("--etf-only", action="store_true", dest="etf_only")
    pe.add_argument("--small-account", action="store_true", dest="small_account",
                    help="small-account universe + tradability scoring")
    pe.add_argument("--account", type=float, default=trad_mod.DEFAULT_ACCOUNT,
                    help="account size for position-sizing checks")

    args = ap.parse_args(argv)
    if args.cmd == "edge":
        _run_edge(args.source, args.symbols, args.fast, args.years,
                  args.small_account, args.etf_only, args.account)
        return
    source = args.source or ("synthetic" if args.cmd == "demo" else "synthetic")
    _run(source, args.symbols, fast=args.fast or args.cmd == "demo",
         years=args.years, etf_only=args.etf_only)


if __name__ == "__main__":
    main()
