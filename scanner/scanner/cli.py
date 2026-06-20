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
from .timeframe import wrap_timeframe
from .pipeline import (PipelineConfig, research, live_signals, build_signal_log,
                       evaluate_logged_signals, SetupResult, SECTOR_MAP)
from .backtest import metrics
from .backtest.engine import trades_to_frame
from .rank import SetupEvidence, build_table, to_markdown
from .sizing import RiskConfig
from .setups.registry import ALL_SETUPS, INTRADAY_ONLY
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
         etf_only: bool = False, timeframe: int = 1):
    real = source in ("polygon", "massive", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    if fast:
        cfg.n_boot = 400
        cfg.placebo_runs = 30
        cfg.param_perturb = (0.9, 1.1)

    adapter = wrap_timeframe(get_adapter(source), timeframe)
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


def _warn_no_data(source, adapter):
    """Print a clear, friendly 'the data did not load' message — so a data
    glitch is never silently reported as 'no setups qualified'."""
    base = getattr(adapter, "base", adapter)
    rate_limited = getattr(base, "last_error", None) == "rate_limited"
    print("\n" + "!" * 78)
    print("  DATA FAILED TO LOAD — no price history came back for your symbols.")
    print("!" * 78)
    print("  This is NOT 'no good setups' — the backtest got ZERO data to test,")
    print("  so every family shows grade F. The fix is about the data feed:")
    if source == "stooq":
        if rate_limited:
            print("\n  • stooq RATE-LIMITED you. It throttles bursts of free downloads.")
        else:
            print("\n  • stooq returned nothing for these tickers (often rate-limiting).")
        print("    What to do (any one):")
        print("      1. Wait ~5 minutes and run it again (the limit resets).")
        print("      2. Use your Massive key instead (handles many symbols cleanly):")
        print("         export MASSIVE_API_KEY=your_key   then add  --source massive")
        print("      3. Ask for fewer symbols, e.g.  --symbols 6")
    else:
        print(f"\n  • The '{source}' feed returned no data. Check the key/connection,")
        print("    or try  --source stooq  (free) or  --source massive  (your key).")
    print("\n  Nothing is wrong with the strategies — they just had no data to chew on.")


def _run_edge(source, n_symbols, fast, years, small_account, etf_only, account,
              timeframe=1):
    real = source in ("polygon", "massive", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    if fast:
        cfg.n_boot, cfg.placebo_runs, cfg.param_perturb = 400, 30, (0.9, 1.1)

    adapter = wrap_timeframe(get_adapter(source), timeframe)
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

    # Loud, honest failure: if NO symbol's price data actually loaded, every
    # family is "grade F / NO SAMPLE" for a boring reason — the data didn't
    # arrive — NOT because no edge exists. Say so plainly instead of pretending
    # nothing qualified.
    if reports and all(r.oos_trades == 0 and r.is_trades == 0 for r in reports):
        _warn_no_data(source, adapter)
        return

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


def _edge_universe(adapter, as_of, small_account, etf_only, n_symbols):
    """Same universe selection edge uses, factored so compare can reuse it."""
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
    return universe or candidates


def _run_compare(sources, n_symbols, fast, years, small_account, etf_only,
                 account, timeframe=1):
    """Run the SAME backtest + validation on two (or more) independent data
    sources and show the grades side by side. A setup that passes on BOTH feeds
    is far more likely to be a real edge than a one-source data quirk."""
    cfg = PipelineConfig()
    cfg.years = years
    if fast:
        cfg.n_boot, cfg.placebo_runs, cfg.param_perturb = 400, 30, (0.9, 1.1)
    as_of = pd.Timestamp.now("UTC").normalize()

    print("=" * 78)
    print("  CROSS-CHECK — same backtest on two data feeds (agreement = trust)")
    print("=" * 78)
    print(f"  Sources: {', '.join(sources)}   Years: {years}   "
          f"{'small-account ' if small_account else ''}"
          f"{'ETF-only' if etf_only else 'all'}")
    print("  A setup graded A/B on BOTH feeds is a real candidate. Passing on only")
    print("  one feed is a red flag (a data artifact, not an edge). HYPOTHETICAL.")
    print("=" * 78)

    # family -> {source: EdgeReport}
    by_family = {}
    ok_sources = []
    for src in sources:
        try:
            adapter = wrap_timeframe(get_adapter(src), timeframe)
            universe = _edge_universe(adapter, as_of, small_account, etf_only,
                                      n_symbols)
            print(f"\n  [{src}] backtesting {len(universe)} symbols…")
            results = research(adapter, universe, cfg=cfg, as_of=as_of)
            reports = edge_mod.build_reports(results, cfg)
        except Exception as exc:
            print(f"  [{src}] UNAVAILABLE — {exc}")
            continue
        ok_sources.append(src)
        for r in reports:
            by_family.setdefault(r.family, {})[src] = r

    if len(ok_sources) < 2:
        print("\n  Need at least TWO working sources to cross-check. "
              "Fix the unavailable one (e.g. set POLYGON_API_KEY) and re-run.")
        return

    def _passed(rep):
        return rep is not None and rep.bucket.split(".")[0] in ("A", "B")

    print("\n  SIDE-BY-SIDE (grade · OOS trades):")
    head = f"  {'family':<28}" + "".join(f"{s:<16}" for s in ok_sources) + "verdict"
    print(head)
    print("  " + "-" * (len(head)))
    rows_sorted = sorted(by_family.items(),
                         key=lambda kv: -sum(_passed(kv[1].get(s)) for s in ok_sources))
    confirmed = []
    for fam, per in rows_sorted:
        cells = ""
        passes = 0
        for s in ok_sources:
            rep = per.get(s)
            if rep is None:
                cells += f"{'—':<16}"
            else:
                g = rep.grade
                n = rep.oos_trades
                cells += f"{g + ' n=' + str(n):<16}"
                passes += int(_passed(rep))
        if passes == len(ok_sources):
            verdict = "✅ BOTH — candidate"
            confirmed.append(fam)
        elif passes > 0:
            only = [s for s in ok_sources if _passed(per.get(s))]
            verdict = f"⚠ only {', '.join(only)}"
        else:
            verdict = "— rejected by both"
        print(f"  {fam:<28}{cells}{verdict}")

    print("\n  VERDICT")
    if confirmed:
        print(f"    Confirmed on ALL feeds (worth forward-testing): "
              f"{', '.join(confirmed)}")
    else:
        print("    No setup passed on every feed. Nothing is cross-confirmed — "
              "do NOT forward-test a one-feed result.")
    print("    Reminder: agreement raises confidence, it does not prove profit. "
          "Forward-test on paper before any real money.")


def _run_report(source, n_symbols, fast, years, small_account, etf_only, account,
                backfill_days, out_path, timeframe=1):
    """One-line full picture: PART 1 backtests + validates (what's PROVEN), then
    PART 2 lists today's candidates (what's AVAILABLE right now)."""
    print("#" * 78)
    print("#  FULL REPORT — Part 1: what PASSED the backtest   "
          "Part 2: today's TRADES")
    print("#" * 78)
    print("\n\n========================  PART 1 of 2  ========================")
    print("  BACKTEST + DOUBLE-TEST — which setups are proven enough to trade?")
    print("  (look at the FAMILY BUCKETS: only A/B are worth acting on)")
    print("==============================================================")
    _run_edge(source, n_symbols, fast, years, small_account, etf_only, account,
              timeframe)

    print("\n\n========================  PART 2 of 2  ========================")
    print("  TODAY'S CANDIDATES — the actual trades available right now")
    print("  (only act on ones from A/B families above; paper first)")
    print("==============================================================")
    # log only needs a short history for indicator warm-up
    _run_log(source, n_symbols, min(years, 3), small_account, etf_only, account,
             backfill_days, out_path, timeframe)

    print("\n" + "#" * 78)
    print("#  HOW TO USE THIS REPORT")
    print("#   1. Part 1 buckets = which STRATEGIES are proven (trust A/B only).")
    print("#   2. Part 2 = today's TRADES. Take only those whose setup is A/B.")
    print("#   3. Paper-trade first. Then `review` to see how they played out.")
    print("#" * 78)


_LOG_KEYS = ("date", "symbol", "setup", "direction")


def _run_log(source, n_symbols, years, small_account, etf_only, account,
             backfill_days, out_path, timeframe=1):
    import os
    real = source in ("polygon", "massive", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    adapter = wrap_timeframe(get_adapter(source), timeframe)
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
    print(f"  Mode               : SIGNAL LOG (paper journal)")
    print(f"  Backfill window    : last {backfill_days} days")
    print(f"  Journal file       : {out_path}")
    print("  Every row is HYPOTHETICAL — a paper candidate, not a trade or advice.")
    print("=" * 78)
    if not real:
        print("(RESEARCH MODE — synthetic data; log rows are illustrative only.)\n")

    setup_names = [n for n in ALL_SETUPS if n not in INTRADAY_ONLY]
    rows = build_signal_log(adapter, universe, setup_names, cfg, as_of,
                            backfill_days=backfill_days, account=account)

    cols = ["date", "symbol", "setup", "direction", "timeframe", "regime",
            "price", "support", "resistance", "dist_to_support_%",
            "entry", "stop", "risk_per_share", "target_2R", "target_2_5R",
            "target_3R", "atr", "adv_dollar_M", "tradability",
            "fresh_on_last_bar", "status"]
    new_df = pd.DataFrame(rows, columns=cols)

    existing = pd.read_csv(out_path) if os.path.exists(out_path) else pd.DataFrame(columns=cols)
    if not existing.empty:
        seen = set(existing[list(_LOG_KEYS)].astype(str).agg("|".join, axis=1))
        keys = new_df[list(_LOG_KEYS)].astype(str).agg("|".join, axis=1)
        add = new_df[~keys.isin(seen)]
    else:
        add = new_df
    parts = [f for f in (existing, add) if not f.empty]
    combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=cols)
    if not combined.empty:
        combined = combined.drop_duplicates(subset=list(_LOG_KEYS)).sort_values(
            ["date", "symbol", "setup"]).reset_index(drop=True)
    combined.to_csv(out_path, index=False)

    fresh = new_df[new_df["fresh_on_last_bar"] == "YES"]
    print(f"  Signals generated this run : {len(new_df)}")
    print(f"  NEW rows appended to journal: {len(add)}")
    print(f"  Total rows in journal      : {len(combined)}")
    print(f"  Fresh on most recent bar   : {len(fresh)}")
    if len(fresh):
        print("\n  FRESH candidates (most recent completed bar — act next session, paper):")
        print(f"    {'date':<10} {'tkr':<5} {'dir':<5} {'setup':<22} {'price':>8} "
              f"{'support':>8} {'resist':>8} {'→sup%':>6} {'entry':>8} {'stop':>8} "
              f"{'3R':>8} {'trad':<6}")
        for _, r in fresh.iterrows():
            sup = r.get("support", "")
            res = r.get("resistance", "")
            dsup = r.get("dist_to_support_%", "")
            print(f"    {str(r['date']):<10} {str(r['symbol']):<5} {str(r['direction']):<5} "
                  f"{str(r['setup']):<22} {r['price']:>8} {str(sup):>8} {str(res):>8} "
                  f"{(str(dsup)+'%' if dsup != '' else ''):>6} {r['entry']:>8} "
                  f"{r['stop']:>8} {r['target_3R']:>8} {str(r['tradability']):<6}")
        print("    support/resist = nearest rule-based level (MAs + recent swing "
              "highs/lows). →sup% = how far price sits ABOVE support (smaller = "
              "closer to support = better long entry).")
    if not new_df.empty:
        by_setup = new_df.groupby("setup").size().sort_values(ascending=False)
        print("\n  By setup family (this run):")
        for name, cnt in by_setup.items():
            print(f"    {name:<24} {cnt}")
    print(f"\n  Journal saved: {out_path}. Re-run anytime — only NEW signals are appended.")
    print("  Schedule it (macOS) to log automatically, e.g. weekdays at 5pm ET:")
    print(f'    (crontab -e)  0 17 * * 1-5  cd "{os.getcwd()}" && '
          f'./.venv/bin/python -m scanner.cli log --source {source} '
          f'{"--small-account " if small_account else ""}'
          f'{"--etf-only " if etf_only else ""}--backfill-days 5 >> log_cron.txt 2>&1')


def _calendar_days(entry, exit_) -> int:
    try:
        return int((pd.Timestamp(exit_) - pd.Timestamp(entry)).days)
    except (ValueError, TypeError):
        return 0


def _trade_outcomes_frame(df):
    """Tidy per-trade CSV: the human-relevant columns first (ticker, entry/exit
    date & price, how long it lasted, R, reason), then everything else."""
    out = df.copy()
    if out.empty:
        return out
    out["entry_date"] = pd.to_datetime(out["entry_time"]).dt.date.astype(str)
    out["exit_date"] = pd.to_datetime(out["exit_time"]).dt.date.astype(str)
    out["trading_days_held"] = out["bars_held"].astype(int)
    out["calendar_days_held"] = [
        _calendar_days(e, x) for e, x in zip(out["entry_time"], out["exit_time"])]
    front = ["symbol", "setup", "direction", "entry_date", "entry_price",
             "exit_date", "exit_price", "trading_days_held", "calendar_days_held",
             "realized_r", "exit_reason", "stop", "target", "regime", "year"]
    front = [c for c in front if c in out.columns]
    rest = [c for c in out.columns if c not in front]
    return out[front + rest].sort_values(["symbol", "entry_date"])


def _print_trade_table(gg, title):
    """Print each closed trade with entry/exit price, dates and duration."""
    print(f"\n  {title} ({len(gg)}):")
    if gg.empty:
        print("    (none closed)")
        return
    print(f"  {'tkr':<5} {'dir':<5} {'entry':<11} {'entry$':>8} {'exit':<11} "
          f"{'exit$':>8} {'days':>4} {'cal':>4} {'R':>7} {'reason':<10}")
    print("  " + "-" * 86)
    for _, t in gg.sort_values("entry_time").iterrows():
        ed = pd.Timestamp(t["entry_time"]).date()
        xd = pd.Timestamp(t["exit_time"]).date()
        print(f"  {str(t['symbol']):<5} {str(t['direction']):<5} "
              f"{str(ed):<11} {float(t['entry_price']):>8.2f} "
              f"{str(xd):<11} {float(t['exit_price']):>8.2f} "
              f"{int(t['bars_held']):>4} {_calendar_days(t['entry_time'], t['exit_time']):>4} "
              f"{t['realized_r']:>7.2f} {str(t['exit_reason']):<10}")
    print("    days = trading days held; cal = calendar days; $ = cost-adjusted fill.")


def _journal_timeframe(rows) -> int:
    """Largest timeframe (candle size in days) recorded in the journal rows.
    Older journals without the column default to 1-day candles."""
    tfs = []
    for r in rows:
        try:
            tfs.append(int(float(r.get("timeframe", 1))))
        except (TypeError, ValueError):
            continue
    return max(tfs) if tfs else 1


def _run_review(source, years, in_path, out_path, since=None, only_setup=None,
                by="setup", show_trades=False):
    import os
    real = source in ("polygon", "massive", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    as_of = pd.Timestamp.now("UTC").normalize()

    if not os.path.exists(in_path):
        print(f"No journal found at {in_path}. Run `log` first.")
        return
    rows = pd.read_csv(in_path).to_dict("records")
    if since:
        rows = [r for r in rows if str(r.get("date", "")) >= since]
    # Resolve forward outcomes on the SAME timeframe the signals were logged on.
    tf = _journal_timeframe(rows)
    adapter = wrap_timeframe(get_adapter(source), tf)
    if tf > 1:
        print(f"  (timeframe: {tf}-day candles, from journal)")
    dates = sorted(str(r["date"]) for r in rows if r.get("date"))
    span = f"{dates[0]} → {dates[-1]}" if dates else "n/a"

    print("=" * 78)
    print("  PAPER JOURNAL REVIEW — how logged candidates actually played out")
    print("=" * 78)
    print(f"  Journal: {in_path}   Source: {source}   Live data: {'YES' if real else 'NO'}")
    print(f"  Window : {span}" + (f"   (since {since})" if since else ""))
    print(f"  Logged candidates: {len(rows)}")
    print("  HYPOTHETICAL outcomes at the 3R target (gap/stop/target/time-stop,")
    print("  same engine as the backtests). Not advice; forward evidence only.")
    print("=" * 78)

    # signals fired per family (from the journal — includes still-open ones)
    journal_counts = {}
    for r in rows:
        journal_counts[r.get("setup", "?")] = journal_counts.get(r.get("setup", "?"), 0) + 1

    trades = evaluate_logged_signals(adapter, rows, cfg, as_of)
    if not trades:
        print("\n  No CLOSED paper trades yet (candidates still open / too recent).")
        print("  Signals fired per family (still open):")
        for name, c in sorted(journal_counts.items(), key=lambda kv: -kv[1]):
            print(f"    {name:<24} {c}")
        return

    df = trades_to_frame(trades)
    s = metrics.summary(trades)
    wins_all = int((df["realized_r"] > 0).sum())
    losses_all = int((df["realized_r"] <= 0).sum())
    wl_all = f"{wins_all/losses_all:.2f}" if losses_all else "∞"
    n_open = len(rows) - len(trades)
    print(f"\n  CLOSED paper trades : {s['n_trades']}   (still open/pending: {n_open})")
    print(f"  Wins / Losses       : {wins_all} / {losses_all}   (win:loss ratio {wl_all})")
    print(f"  Win rate            : {s['win_rate']:.1%}")
    print(f"  Expectancy          : {s['expectancy_r']:.3f}R  (${s['expectancy_currency']:.0f}/trade nominal)")
    print(f"  Profit factor       : {s['profit_factor']:.2f}")
    print(f"  Avg win / avg loss  : {s['avg_winner_r']:.2f}R / {s['avg_loser_r']:.2f}R")
    print(f"  Max drawdown        : {s['max_drawdown_r']:.1f}R")
    print(f"  Exits: target {s['pct_target_exits']:.0%} | time {s['pct_time_exits']:.0%} | "
          f"gap-tail(<-1R) {s['gap_tail_rate']:.0%}")

    # group key on the trades frame
    dfk = df.copy()
    if by == "month":
        dfk["_k"] = pd.to_datetime(dfk["entry_time"]).dt.strftime("%Y-%m")
    elif by == "year":
        dfk["_k"] = dfk["year"].astype(str)
    else:
        dfk["_k"] = dfk[by].astype(str)
    # fired counts (journal) for the same key
    fired = {}
    for r in rows:
        if by == "setup":
            k = str(r.get("setup", "?"))
        elif by == "symbol":
            k = str(r.get("symbol", "?")).upper()
        elif by == "regime":
            k = str(r.get("regime", "?"))
        elif by == "year":
            k = str(r.get("date", ""))[:4]
        elif by == "month":
            k = str(r.get("date", ""))[:7]
        else:
            k = str(r.get(by, "?"))
        fired[k] = fired.get(k, 0) + 1

    print(f"\n  By {by}:")
    print(f"  {by:<24} {'fired':>5} {'closed':>6} {'W':>4} {'L':>4} {'W:L':>5} "
          f"{'win%':>5} {'exp(R)':>8} {'PF':>6} {'hold':>5}")
    print("  " + "-" * 84)
    grp_rows = []
    for k, g in dfk.groupby("_k"):
        w = int((g["realized_r"] > 0).sum())
        l = int((g["realized_r"] <= 0).sum())
        gw = float(g.loc[g["realized_r"] > 0, "realized_r"].sum())
        gl = float(-g.loc[g["realized_r"] <= 0, "realized_r"].sum())
        pf = gw / gl if gl > 0 else float("inf")
        grp_rows.append({"k": k, "fired": fired.get(str(k), len(g)), "closed": len(g),
                         "w": w, "l": l, "wl": (w / l if l else float("inf")),
                         "win": w / len(g), "exp": float(g["realized_r"].mean()),
                         "pf": pf, "hold": float(g["bars_held"].mean())})
    grp_rows.sort(key=lambda x: -x["exp"])
    for r in grp_rows:
        wl = f"{r['wl']:.2f}" if r["l"] else "∞"
        pf = f"{r['pf']:.2f}" if r["pf"] != float("inf") else "∞"
        print(f"  {str(r['k']):<24} {r['fired']:>5} {r['closed']:>6} {r['w']:>4} {r['l']:>4} "
              f"{wl:>5} {r['win']:>5.0%} {r['exp']:>8.3f} {pf:>6} {r['hold']:>5.1f}")
    if by != "setup":
        print(f"  (grouped by {by}; small per-group samples are unreliable — "
              "a high past win% is hindsight, not a prediction.)")

    # per-trade detail: entry/exit price, dates, how long it lasted, result.
    # Shown for one family with --setup, or for ALL closed trades with --trades.
    if only_setup:
        gg = df[df["setup"] == only_setup].copy()
        _print_trade_table(gg, f"Individual closed trades — {only_setup}")
    elif show_trades:
        _print_trade_table(df, "Individual closed trades — ALL families")

    if out_path:
        out_df = _trade_outcomes_frame(df)
        out_df.to_csv(out_path, index=False)
        print(f"\n  Full per-trade detail (ticker, entry/exit date & PRICE, days "
              f"held, calendar days, R, reason) written: {out_path}")
        print(f"  Open it in VS Code (or Excel) to see every trade's entry, exit "
              f"and how long it lasted.")
    print("\n  'fired' = signals logged in the window (incl. still-open); 'closed' = "
          "resolved at 3R/stop/time. Hold = trading days in the trade.")
    print("  Reminder: a small/medium closed sample is STATISTICALLY INCONCLUSIVE. "
          "Aim for 100+ per family. Hypothetical, not advice.")


# --------------------------------------------------------------------------
# Concentration analysis: is a setup a broad edge, or one ticker / one rally?
# --------------------------------------------------------------------------

def _grp_stats(g):
    """Core metrics for a group of closed trades (a DataFrame with realized_r)."""
    n = len(g)
    if n == 0:
        return dict(n=0, total_r=0.0, exp=0.0, win=0.0, pf=float("nan"),
                    best=0.0, worst=0.0)
    r = g["realized_r"].astype(float)
    gw = float(r[r > 0].sum())
    gl = float(-r[r <= 0].sum())
    return dict(
        n=n,
        total_r=float(r.sum()),
        exp=float(r.mean()),
        win=float((r > 0).mean()),
        pf=(gw / gl) if gl > 0 else float("inf"),
        best=float(r.max()),
        worst=float(r.min()),
    )


def _pf_str(pf):
    if pf != pf:        # NaN
        return "n/a"
    return "∞" if pf == float("inf") else f"{pf:.2f}"


def _run_concentration(source, years, in_path, out_path, since=None,
                       setups=None, min_oos=100):
    """Per-ticker contribution + drop-one / drop-best / drop-period tests.

    Analysis only — does NOT change strategy rules. Answers: is the edge broad,
    or carried by a single ticker (e.g. SLV) or a single hot period?
    """
    import os
    real = source in ("polygon", "massive", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    as_of = pd.Timestamp.now("UTC").normalize()

    if not os.path.exists(in_path):
        print(f"No journal found at {in_path}. Run `log` first.")
        return
    rows = pd.read_csv(in_path).to_dict("records")
    tf = _journal_timeframe(rows)
    adapter = wrap_timeframe(get_adapter(source), tf)
    if since:
        rows = [r for r in rows if str(r.get("date", "")) >= since]

    print("=" * 78)
    print("  CONCENTRATION ANALYSIS — is the edge broad, or one ticker / one rally?")
    print("=" * 78)
    print(f"  Journal: {in_path}   Source: {source}   Live data: {'YES' if real else 'NO'}")
    print("  Analysis only. No strategy changes. HYPOTHETICAL 3R outcomes.")
    print("=" * 78)

    trades = evaluate_logged_signals(adapter, rows, cfg, as_of)
    if not trades:
        print("\n  No CLOSED paper trades yet (candidates still open / too recent).")
        return
    df = trades_to_frame(trades)
    df["symbol"] = df["symbol"].astype(str).str.upper()
    _et = pd.to_datetime(df["entry_time"], utc=True).dt.tz_localize(None)
    df["_month"] = _et.dt.strftime("%Y-%m")
    df["_q"] = _et.dt.to_period("Q").astype(str)
    df["year"] = df["year"].astype(int)

    fams = setups or sorted(df["setup"].unique())
    report_rows = []

    for fam in fams:
        fam_df = df[df["setup"] == fam].copy()
        base = _grp_stats(fam_df)
        if base["n"] == 0:
            print(f"\n  {fam}: no closed trades.")
            continue

        print("\n" + "=" * 78)
        print(f"  SETUP: {fam}")
        print("=" * 78)
        print(f"  Closed trades {base['n']} | total {base['total_r']:+.2f}R | "
              f"exp {base['exp']:+.3f}R | win {base['win']:.0%} | "
              f"PF {_pf_str(base['pf'])}")
        if base["n"] < min_oos:
            print(f"  ⚠ n={base['n']} < {min_oos} → STATISTICALLY INCONCLUSIVE "
                  "(promising at best, not validated).")

        # --- per-ticker contribution table ---
        print("\n  Per-ticker contribution (sorted by total R):")
        print(f"  {'tkr':<6} {'n':>3} {'totR':>8} {'avgR':>7} {'win%':>5} "
              f"{'PF':>6} {'best':>6} {'worst':>6} {'%profit':>8}")
        print("  " + "-" * 64)
        pos_total = float(fam_df.loc[fam_df["realized_r"] > 0, "realized_r"].sum())
        tkr_stats = {}
        for tkr, g in fam_df.groupby("symbol"):
            st = _grp_stats(g)
            tkr_stats[tkr] = st
        for tkr, st in sorted(tkr_stats.items(), key=lambda kv: -kv[1]["total_r"]):
            share = (max(st["total_r"], 0.0) / pos_total * 100) if pos_total > 0 else 0.0
            print(f"  {tkr:<6} {st['n']:>3} {st['total_r']:>+8.2f} {st['exp']:>+7.2f} "
                  f"{st['win']:>5.0%} {_pf_str(st['pf']):>6} {st['best']:>+6.2f} "
                  f"{st['worst']:>+6.2f} {share:>7.0f}%")
            report_rows.append(dict(
                setup=fam, dimension="ticker", key=tkr, n=st["n"],
                total_r=round(st["total_r"], 3), avg_r=round(st["exp"], 3),
                win_rate=round(st["win"], 3), profit_factor=_pf_str(st["pf"]),
                largest_winner=round(st["best"], 3), largest_loser=round(st["worst"], 3),
                pct_of_profit=round(share, 1)))

        # --- drop-one-ticker tests ---
        print("\n  Drop-one-ticker (remove each ticker, recompute the rest):")
        print(f"  {'remove':<8} {'n':>3} {'exp(R)':>8} {'win%':>5} {'PF':>6}  flag")
        print("  " + "-" * 50)
        weakened = []
        for tkr in sorted(tkr_stats, key=lambda t: -tkr_stats[t]["total_r"]):
            rest = fam_df[fam_df["symbol"] != tkr]
            st = _grp_stats(rest)
            flag = ""
            if st["exp"] <= 0:
                flag = "EXP→≤0"
                weakened.append(tkr)
            elif base["exp"] > 0 and st["exp"] < 0.5 * base["exp"]:
                flag = "halved"
                weakened.append(tkr)
            print(f"  {tkr:<8} {st['n']:>3} {st['exp']:>+8.3f} {st['win']:>5.0%} "
                  f"{_pf_str(st['pf']):>6}  {flag}")
            report_rows.append(dict(
                setup=fam, dimension="drop_ticker", key=tkr, n=st["n"],
                total_r=round(st["total_r"], 3), avg_r=round(st["exp"], 3),
                win_rate=round(st["win"], 3), profit_factor=_pf_str(st["pf"]),
                largest_winner="", largest_loser="", pct_of_profit=""))

        # --- drop-best-ticker test ---
        best_tkr = max(tkr_stats, key=lambda t: tkr_stats[t]["total_r"])
        rest = fam_df[fam_df["symbol"] != best_tkr]
        db = _grp_stats(rest)
        best_share = (max(tkr_stats[best_tkr]["total_r"], 0.0) / pos_total * 100) \
            if pos_total > 0 else 0.0
        print(f"\n  Drop-BEST-ticker ({best_tkr}, {best_share:.0f}% of profit): "
              f"exp {base['exp']:+.3f}R → {db['exp']:+.3f}R  "
              f"(n {base['n']}→{db['n']}, PF {_pf_str(base['pf'])}→{_pf_str(db['pf'])})")

        # --- drop-best-period tests ---
        period_collapse = False
        for label, col in (("month", "_month"), ("quarter", "_q"), ("year", "year")):
            sums = fam_df.groupby(col)["realized_r"].sum()
            if sums.empty:
                continue
            best_k = sums.idxmax()
            dp = _grp_stats(fam_df[fam_df[col] != best_k])
            note = ""
            if base["exp"] > 0 and dp["exp"] <= 0:
                note = "  ← EXP→≤0 without this period"
                period_collapse = True
            print(f"  Drop-best-{label:<7} ({best_k}): exp {base['exp']:+.3f}R → "
                  f"{dp['exp']:+.3f}R (n→{dp['n']}){note}")
            report_rows.append(dict(
                setup=fam, dimension=f"drop_{label}", key=str(best_k), n=dp["n"],
                total_r=round(dp["total_r"], 3), avg_r=round(dp["exp"], 3),
                win_rate=round(dp["win"], 3), profit_factor=_pf_str(dp["pf"]),
                largest_winner="", largest_loser="", pct_of_profit=""))

        # --- verdict ---
        n_tickers = len(tkr_stats)
        if base["exp"] <= 0:
            verdict = (f"NO EDGE — base expectancy {base['exp']:+.3f}R is ≤0 before "
                       "any concentration test. Nothing to keep.")
        elif db["exp"] <= 0:
            verdict = (f"REJECTED — CONCENTRATION-DRIVEN: removing {best_tkr} "
                       f"turns expectancy {db['exp']:+.3f}R (≤0).")
        elif best_share >= 50:
            verdict = (f"CONCENTRATION-DRIVEN: {best_tkr} alone is {best_share:.0f}% "
                       f"of profit (survives at {db['exp']:+.3f}R but fragile).")
        elif period_collapse:
            verdict = ("CONCENTRATION-DRIVEN (time): one period carries it — "
                       "expectancy turns ≤0 without the best month/quarter/year.")
        elif n_tickers >= 5 and db["exp"] > 0:
            verdict = (f"DIVERSIFIED — survives dropping {best_tkr} at "
                       f"{db['exp']:+.3f}R across {n_tickers} tickers. "
                       "TENTATIVE CANDIDATE — needs longer OOS / forward paper.")
        else:
            verdict = (f"INCONCLUSIVE — survives drop-best at {db['exp']:+.3f}R but "
                       f"only {n_tickers} tickers; keep paper-tracking.")
        if base["n"] < min_oos:
            verdict += f"  (n={base['n']}<{min_oos}: STATISTICALLY INCONCLUSIVE.)"
        print(f"\n  VERDICT: {verdict}")
        report_rows.append(dict(
            setup=fam, dimension="VERDICT", key=verdict, n=base["n"],
            total_r=round(base["total_r"], 3), avg_r=round(base["exp"], 3),
            win_rate=round(base["win"], 3), profit_factor=_pf_str(base["pf"]),
            largest_winner=best_tkr, largest_loser="",
            pct_of_profit=round(best_share, 1)))

    if out_path and report_rows:
        pd.DataFrame(report_rows).to_csv(out_path, index=False)
        print(f"\n  Concentration report written: {out_path}")
    print("\n  Analysis only — no strategy rules changed. 0% live risk until "
          "concentration, placebo, cost stress, AND forward paper all pass.")


# --------------------------------------------------------------------------
# Trade plan: real dates, gap to the next signal, and money required.
# --------------------------------------------------------------------------

def _run_plan(source, years, in_path, out_path, since=None, account=2000.0,
              risk_pct=0.01):
    """Answer the practical questions: when do signals come (and how long until
    the next one), how much money each trade needs, the peak capital required if
    trades overlap, plus the interesting/important highlights."""
    import os
    from .sizing import RiskConfig, shares_for_trade

    cfg = PipelineConfig()
    cfg.years = years
    as_of = pd.Timestamp.now("UTC").normalize()

    if not os.path.exists(in_path):
        print(f"No journal found at {in_path}. Run `log` first.")
        return
    rows = pd.read_csv(in_path).to_dict("records")
    if since:
        rows = [r for r in rows if str(r.get("date", "")) >= since]
    rows = [r for r in rows if r.get("date")]
    if not rows:
        print("No dated signals in the journal for this window.")
        return
    tf = _journal_timeframe(rows)
    adapter = wrap_timeframe(get_adapter(source), tf)
    rcfg = RiskConfig()
    rcfg.risk_per_trade_pct = risk_pct
    dollar_risk_budget = account * risk_pct

    print("=" * 78)
    print("  TRADE PLAN — when signals come, and how much money it takes")
    print("=" * 78)
    print(f"  Journal: {in_path}   Source: {source}"
          + (f"   Timeframe: {tf}-day candles" if tf > 1 else ""))
    print(f"  Account assumed    : ${account:,.0f}    Risk/trade: {risk_pct:.2%} "
          f"(${dollar_risk_budget:,.0f} at risk per trade)")
    print("  HYPOTHETICAL paper plan — not advice. Sizing is fixed-fractional on "
          "the entry-to-stop distance.")
    print("=" * 78)

    # ---------- CADENCE: dates and time until the next signal ----------
    rows.sort(key=lambda r: str(r["date"]))
    dates = [pd.Timestamp(str(r["date"])) for r in rows]
    span_days = max((dates[-1] - dates[0]).days, 1)
    gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    uniq_days = sorted(set(d.date() for d in dates))
    day_gaps = [(uniq_days[i + 1] - uniq_days[i]).days
                for i in range(len(uniq_days) - 1)]
    print("\n  CADENCE — how often, and how long before the next signal")
    print(f"    Signals logged     : {len(rows)} over {span_days} days "
          f"({dates[0].date()} → {dates[-1].date()})")
    print(f"    Signals per month  : {len(rows) / (span_days / 30.4):.1f}")
    if day_gaps:
        import statistics as _st
        longest = max(day_gaps)
        li = day_gaps.index(longest)
        print(f"    Days between signal DAYS: avg {_st.mean(day_gaps):.1f}, "
              f"median {_st.median(day_gaps):.0f}, longest {longest} "
              f"({uniq_days[li]} → {uniq_days[li + 1]})")
        print(f"    Active signal days : {len(uniq_days)} of {span_days} "
              f"({len(uniq_days) / span_days:.0%} of calendar days had a signal)")
    if gaps:
        same_day = sum(1 for g in gaps if g == 0)
        print(f"    Clustering         : {same_day} signals landed on a day that "
              f"already had another (they bunch up, then go quiet).")

    # No-margin cash account: you can never deploy more dollars than you have,
    # so the real share count is the smaller of the risk-based size and what the
    # cash can buy. (A tight stop wants thousands of shares; the wallet says no.)
    def _sized(entry, stop):
        risk_sh = shares_for_trade(account, entry, stop, rcfg)
        cash_sh = int(account // entry) if entry > 0 else 0
        return min(risk_sh, cash_sh), risk_sh, cash_sh

    # ---------- MONEY: per-trade sizing and affordability ----------
    plan_rows = []
    deployed_list, affordable, cash_capped = [], 0, 0
    for i, r in enumerate(rows):
        try:
            entry, stop = float(r["entry"]), float(r["stop"])
        except (ValueError, TypeError, KeyError):
            continue
        sh, risk_sh, cash_sh = _sized(entry, stop)
        deployed = sh * entry
        d_risk = sh * abs(entry - stop)
        nxt = (dates[i + 1] - dates[i]).days if i < len(rows) - 1 else None
        capped = sh >= 1 and cash_sh < risk_sh
        if sh >= 1:
            affordable += 1
            deployed_list.append(deployed)
            cash_capped += int(capped)
        plan_rows.append({
            "date": str(r["date"]), "symbol": str(r.get("symbol", "")).upper(),
            "setup": r.get("setup", ""), "direction": r.get("direction", ""),
            "entry": round(entry, 2), "stop": round(stop, 2),
            "shares_at_account": sh, "dollars_deployed": round(deployed, 0),
            "dollar_risk": round(d_risk, 2),
            "days_to_next_signal": nxt,
            "affordable": ("yes" if sh >= 1 else
                           "NO (1 share costs more than the account)"),
            "cash_capped": "yes" if capped else "",
        })
    print("\n  MONEY — how much each trade needs (at this account & risk)")
    if deployed_list:
        import statistics as _st
        print(f"    $ deployed per trade: avg ${_st.mean(deployed_list):,.0f}, "
              f"median ${_st.median(deployed_list):,.0f}, "
              f"max ${max(deployed_list):,.0f} (never more than the ${account:,.0f} "
              "you have)")
        print(f"    As % of account     : avg {_st.mean(deployed_list)/account:.0%}, "
              f"max {max(deployed_list)/account:.0%}")
    if cash_capped:
        print(f"    ℹ {cash_capped} trades are CASH-CAPPED: the proper 1% risk size "
              "needs more cash than you have, so you'd buy fewer shares and your "
              "real risk on those is BELOW 1% (small-account reality).")
    unafford = len(plan_rows) - affordable
    if unafford:
        print(f"    ⚠ {unafford} of {len(plan_rows)} signals can't be taken at "
              f"${account:,.0f} — one share costs more than the whole account. "
              "Stick to cheaper ETFs (SPLG/QQQM/etc.) or fund more.")

    # ---------- PEAK CAPITAL: overlapping open trades ----------
    trades = evaluate_logged_signals(adapter, rows, cfg, as_of)
    if trades:
        df = trades_to_frame(trades)
        events = []  # (time, +deployed on entry, -deployed on exit)
        for _, t in df.iterrows():
            sh, _, _ = _sized(float(t["entry_price"]), float(t["stop"]))
            dep = sh * float(t["entry_price"])
            events.append((pd.Timestamp(t["entry_time"]), dep, +1))
            events.append((pd.Timestamp(t["exit_time"]), -dep, -1))
        events.sort(key=lambda e: (e[0], e[2] * -1))  # process exits before entries on ties? keep entries last
        cur_cap = cur_n = peak_cap = peak_n = 0
        peak_when = None
        # also track peak position COUNT (independent of when $ peaks)
        c2 = 0
        peak_count = 0
        for ts, d, k in sorted(events, key=lambda e: e[0]):
            c2 += k
            peak_count = max(peak_count, c2)
        for ts, d, k in events:
            cur_cap += d
            cur_n += k
            if cur_cap > peak_cap:
                peak_cap, peak_n, peak_when = cur_cap, cur_n, ts
        print("\n  PEAK CAPITAL — how many trades overlap, and the cash to hold them")
        print(f"    Most trades open at once: {peak_count} "
              f"(around {peak_when.date() if peak_when is not None else 'n/a'})")
        capped_positions = min(peak_count, rcfg.max_positions)
        print(f"    Cash-account reality    : a no-margin account can't hold more "
              f"than ~${account:,.0f} of stock total at any moment, and the "
              f"moderate profile caps you at {rcfg.max_positions} open positions. "
              f"So you'd hold at most {capped_positions} of those at a time and "
              "skip the rest.")
        if peak_count > rcfg.max_positions:
            print(f"    ⚠ Signals bunch up to {peak_count} at once — far over the "
                  f"{rcfg.max_positions}-position cap. Most overlaps would be "
                  "SKIPPED live, so realistically you need about one account's "
                  f"worth of cash (${account:,.0f}), not more.")

        # ---------- HIGHLIGHTS ----------
        df["_cal"] = [(pd.Timestamp(x) - pd.Timestamp(e)).days
                      for e, x in zip(df["entry_time"], df["exit_time"])]
        df["_pnl$"] = df["realized_r"] * dollar_risk_budget
        best = df.loc[df["realized_r"].idxmax()]
        worst = df.loc[df["realized_r"].idxmin()]
        wins = int((df["realized_r"] > 0).sum())
        n = len(df)
        top_tkr = df["symbol"].value_counts().head(3)
        reasons = df["exit_reason"].value_counts()
        print("\n  HIGHLIGHTS — interesting & important")
        print(f"    Closed trades       : {n}   Win rate: {wins/n:.0%}   "
              f"Expectancy: {df['realized_r'].mean():+.3f}R "
              f"(${df['_pnl$'].mean():+,.0f}/trade)")
        print(f"    Best trade          : {best['symbol']} {best['realized_r']:+.2f}R "
              f"(${best['_pnl$']:+,.0f}) entered {pd.Timestamp(best['entry_time']).date()}, "
              f"held {int(best['_cal'])} cal days")
        print(f"    Worst trade         : {worst['symbol']} {worst['realized_r']:+.2f}R "
              f"(${worst['_pnl$']:+,.0f}) entered {pd.Timestamp(worst['entry_time']).date()}, "
              f"held {int(worst['_cal'])} cal days")
        print(f"    Hold time (calendar): avg {df['_cal'].mean():.0f} days, "
              f"shortest {int(df['_cal'].min())}, longest {int(df['_cal'].max())}")
        print(f"    Most active tickers : "
              + ", ".join(f"{k} ({v})" for k, v in top_tkr.items()))
        print(f"    How trades closed   : "
              + ", ".join(f"{k} {v/n:.0%}" for k, v in reasons.items()))
    else:
        print("\n  PEAK CAPITAL / HIGHLIGHTS: no CLOSED trades yet (still open or "
              "too recent). Re-run after some have resolved.")

    if out_path and plan_rows:
        pd.DataFrame(plan_rows).to_csv(out_path, index=False)
        print(f"\n  Per-signal plan (date, days-to-next, shares, $ deployed, "
              f"$ risk, affordable?) written: {out_path}")
    print("\n  Reminder: HYPOTHETICAL paper plan. Sizing assumes you risk a fixed "
          f"{risk_pct:.1%} of the account per trade; real fills, fees and skipped "
          "signals will differ.")


def main(argv: List[str] = None):
    ap = argparse.ArgumentParser(description="Rule-based market scanner")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("demo", "research", "scan"):
        p = sub.add_parser(cmd)
        p.add_argument("--source", default="synthetic" if cmd == "demo" else None,
                       choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
        p.add_argument("--symbols", type=int, default=20,
                       help="number of candidate symbols to scan")
        p.add_argument("--years", type=int, default=10,
                       help="years of history (use 2 for Polygon free tier)")
        p.add_argument("--fast", action="store_true",
                       help="smaller bootstrap/placebo counts for a quick run")
        p.add_argument("--etf-only", action="store_true", dest="etf_only",
                       help="use the liquid ETF universe (cleaner, less survivorship bias)")
        p.add_argument("--timeframe", type=int, default=1, choices=[1, 2, 3],
                       help="candle size in trading days (1=daily, 2=two-day). "
                            "One timeframe per run — see scanner/timeframe.py.")

    pe = sub.add_parser("edge", help="validate setup families, grade, bucket, "
                                     "then surface current candidates")
    pe.add_argument("--source", default="stooq",
                    choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
    pe.add_argument("--symbols", type=int, default=30)
    pe.add_argument("--years", type=int, default=12)
    pe.add_argument("--fast", action="store_true")
    pe.add_argument("--etf-only", action="store_true", dest="etf_only")
    pe.add_argument("--small-account", action="store_true", dest="small_account",
                    help="small-account universe + tradability scoring")
    pe.add_argument("--account", type=float, default=trad_mod.DEFAULT_ACCOUNT,
                    help="account size for position-sizing checks")
    pe.add_argument("--timeframe", type=int, default=1, choices=[1, 2, 3],
                    help="candle size in trading days (1=daily, 2=two-day)")

    pl = sub.add_parser("log", help="backfill + append a paper signal journal (CSV)")
    pl.add_argument("--source", default="stooq",
                    choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
    pl.add_argument("--symbols", type=int, default=30)
    pl.add_argument("--years", type=int, default=3,
                    help="history depth for indicator warmup")
    pl.add_argument("--backfill-days", type=int, default=365, dest="backfill_days",
                    help="how far back to log signals (default 365)")
    pl.add_argument("--etf-only", action="store_true", dest="etf_only")
    pl.add_argument("--small-account", action="store_true", dest="small_account")
    pl.add_argument("--account", type=float, default=trad_mod.DEFAULT_ACCOUNT)
    pl.add_argument("--out", default="signal_log.csv", dest="out_path",
                    help="journal CSV path (appended idempotently)")
    pl.add_argument("--timeframe", type=int, default=1, choices=[1, 2, 3],
                    help="candle size in trading days (1=daily, 2=two-day). "
                         "Recorded in the journal so review/concentration match it.")

    pr = sub.add_parser("review", help="score how logged paper candidates played out")
    pr.add_argument("--source", default="stooq",
                    choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
    pr.add_argument("--years", type=int, default=3)
    pr.add_argument("--in", default="signal_log.csv", dest="in_path",
                    help="journal CSV to review")
    pr.add_argument("--out", default="signal_outcomes.csv", dest="out_path",
                    help="per-trade outcomes CSV to write")
    pr.add_argument("--since", default=None,
                    help="only review signals on/after this date, e.g. 2026-01-01 (YTD)")
    pr.add_argument("--setup", default=None, dest="only_setup",
                    help="list individual trades (ticker/dates/days/result) for one family")
    pr.add_argument("--trades", action="store_true", dest="show_trades",
                    help="print every closed trade: entry/exit date & price, how "
                         "long it lasted (trading + calendar days), R, reason")
    pr.add_argument("--by", default="setup",
                    choices=["setup", "symbol", "regime", "year", "month", "direction"],
                    help="break outcomes down by this dimension (default: setup)")

    pc = sub.add_parser("concentration",
                        help="is a setup a broad edge, or one ticker / one rally?")
    pc.add_argument("--source", default="stooq",
                    choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
    pc.add_argument("--years", type=int, default=12)
    pc.add_argument("--in", default="signal_log.csv", dest="in_path",
                    help="journal CSV to analyze")
    pc.add_argument("--out", default="concentration_report.csv", dest="out_path",
                    help="concentration report CSV to write")
    pc.add_argument("--since", default=None,
                    help="only analyze signals on/after this date, e.g. 2026-01-01")
    pc.add_argument("--setup", action="append", dest="setups", default=None,
                    help="restrict to a setup family (repeatable); default: all")
    pc.add_argument("--min-oos", type=int, default=100, dest="min_oos",
                    help="minimum closed trades to consider validated (default 100)")

    pp = sub.add_parser("plan",
                        help="dates, time-to-next-signal, money required, highlights")
    pp.add_argument("--source", default="stooq",
                    choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
    pp.add_argument("--years", type=int, default=3)
    pp.add_argument("--in", default="signal_log.csv", dest="in_path",
                    help="journal CSV to plan from")
    pp.add_argument("--out", default="trade_plan.csv", dest="out_path",
                    help="per-signal plan CSV to write")
    pp.add_argument("--since", default=None,
                    help="only plan signals on/after this date, e.g. 2026-01-01")
    pp.add_argument("--account", type=float, default=trad_mod.DEFAULT_ACCOUNT,
                    help="account size in dollars (how much you'd trade with)")
    pp.add_argument("--risk-pct", type=float, default=0.01, dest="risk_pct",
                    help="fraction of the account risked per trade (default 0.01 = 1%%)")

    pm = sub.add_parser("compare",
                        help="run the backtest on two data feeds; trust what passes BOTH")
    pm.add_argument("--sources", nargs="+", default=["stooq", "polygon"],
                    choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"],
                    help="two or more data feeds to cross-check (default: stooq polygon)")
    pm.add_argument("--symbols", type=int, default=30)
    pm.add_argument("--years", type=int, default=4)
    pm.add_argument("--fast", action="store_true")
    pm.add_argument("--etf-only", action="store_true", dest="etf_only")
    pm.add_argument("--small-account", action="store_true", dest="small_account")
    pm.add_argument("--account", type=float, default=trad_mod.DEFAULT_ACCOUNT)
    pm.add_argument("--timeframe", type=int, default=1, choices=[1, 2, 3])

    prp = sub.add_parser("report",
                         help="one line: what PASSED the backtest + today's TRADES")
    prp.add_argument("--source", default="stooq",
                     choices=["synthetic", "csv", "polygon", "massive", "schwab", "stooq"])
    prp.add_argument("--symbols", type=int, default=30)
    prp.add_argument("--years", type=int, default=10,
                     help="backtest history depth (default 10)")
    prp.add_argument("--fast", action="store_true",
                     help="quicker run (smaller bootstrap/placebo counts)")
    prp.add_argument("--etf-only", action="store_true", dest="etf_only")
    prp.add_argument("--small-account", action="store_true", dest="small_account")
    prp.add_argument("--account", type=float, default=trad_mod.DEFAULT_ACCOUNT)
    prp.add_argument("--backfill-days", type=int, default=7, dest="backfill_days",
                     help="how far back to list today's candidates (default 7)")
    prp.add_argument("--out", default="signal_log.csv", dest="out_path",
                     help="journal CSV for today's candidates")
    prp.add_argument("--timeframe", type=int, default=1, choices=[1, 2, 3])

    args = ap.parse_args(argv)
    if args.cmd == "report":
        _run_report(args.source, args.symbols, args.fast, args.years,
                    args.small_account, args.etf_only, args.account,
                    args.backfill_days, args.out_path, args.timeframe)
        return
    if args.cmd == "compare":
        _run_compare(args.sources, args.symbols, args.fast, args.years,
                     args.small_account, args.etf_only, args.account,
                     args.timeframe)
        return
    if args.cmd == "edge":
        _run_edge(args.source, args.symbols, args.fast, args.years,
                  args.small_account, args.etf_only, args.account, args.timeframe)
        return
    if args.cmd == "review":
        _run_review(args.source, args.years, args.in_path, args.out_path,
                    args.since, args.only_setup, args.by, args.show_trades)
        return
    if args.cmd == "concentration":
        _run_concentration(args.source, args.years, args.in_path, args.out_path,
                           args.since, args.setups, args.min_oos)
        return
    if args.cmd == "plan":
        _run_plan(args.source, args.years, args.in_path, args.out_path,
                  args.since, args.account, args.risk_pct)
        return
    if args.cmd == "log":
        _run_log(args.source, args.symbols, args.years, args.small_account,
                 args.etf_only, args.account, args.backfill_days, args.out_path,
                 args.timeframe)
        return
    source = args.source or ("synthetic" if args.cmd == "demo" else "synthetic")
    _run(source, args.symbols, fast=args.fast or args.cmd == "demo",
         years=args.years, etf_only=args.etf_only, timeframe=args.timeframe)


if __name__ == "__main__":
    main()
