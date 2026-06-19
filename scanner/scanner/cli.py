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


_LOG_KEYS = ("date", "symbol", "setup", "direction")


def _run_log(source, n_symbols, years, small_account, etf_only, account,
             backfill_days, out_path):
    import os
    real = source in ("polygon", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
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

    cols = ["date", "symbol", "setup", "direction", "regime", "entry", "stop",
            "risk_per_share", "target_2R", "target_2_5R", "target_3R", "atr",
            "adv_dollar_M", "tradability", "fresh_on_last_bar", "status"]
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
        for _, r in fresh.iterrows():
            print(f"    {r['date']}  {r['symbol']:<5} {r['direction']:<5} {r['setup']:<22} "
                  f"entry {r['entry']} stop {r['stop']} 3R {r['target_3R']} "
                  f"[trad {r['tradability']}]")
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


def _run_review(source, years, in_path, out_path, since=None, only_setup=None,
                by="setup"):
    import os
    real = source in ("polygon", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    adapter = get_adapter(source)
    as_of = pd.Timestamp.now("UTC").normalize()

    if not os.path.exists(in_path):
        print(f"No journal found at {in_path}. Run `log` first.")
        return
    rows = pd.read_csv(in_path).to_dict("records")
    if since:
        rows = [r for r in rows if str(r.get("date", "")) >= since]
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

    # optional per-trade detail for one family: tickers, dates, days, result
    if only_setup:
        gg = df[df["setup"] == only_setup].copy()
        print(f"\n  Individual closed trades — {only_setup} ({len(gg)}):")
        if gg.empty:
            print("    (none closed for this setup)")
        else:
            print(f"  {'entry':<11} {'exit':<11} {'days':>4} {'tkr':<5} {'dir':<5} "
                  f"{'R':>7} {'exit':<10}")
            print("  " + "-" * 60)
            for _, t in gg.sort_values("entry_time").iterrows():
                print(f"  {str(pd.Timestamp(t['entry_time']).date()):<11} "
                      f"{str(pd.Timestamp(t['exit_time']).date()):<11} "
                      f"{int(t['bars_held']):>4} {str(t['symbol']):<5} "
                      f"{str(t['direction']):<5} {t['realized_r']:>7.2f} "
                      f"{str(t['exit_reason']):<10}")

    if out_path:
        df.to_csv(out_path, index=False)
        print(f"\n  Full per-trade detail (every ticker, entry/exit date, days held, "
              f"R, reason) written: {out_path}")
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
    real = source in ("polygon", "csv", "schwab", "stooq")
    cfg = PipelineConfig()
    cfg.years = years
    adapter = get_adapter(source)
    as_of = pd.Timestamp.now("UTC").normalize()

    if not os.path.exists(in_path):
        print(f"No journal found at {in_path}. Run `log` first.")
        return
    rows = pd.read_csv(in_path).to_dict("records")
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

    pl = sub.add_parser("log", help="backfill + append a paper signal journal (CSV)")
    pl.add_argument("--source", default="synthetic",
                    choices=["synthetic", "csv", "polygon", "schwab", "stooq"])
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

    pr = sub.add_parser("review", help="score how logged paper candidates played out")
    pr.add_argument("--source", default="synthetic",
                    choices=["synthetic", "csv", "polygon", "schwab", "stooq"])
    pr.add_argument("--years", type=int, default=3)
    pr.add_argument("--in", default="signal_log.csv", dest="in_path",
                    help="journal CSV to review")
    pr.add_argument("--out", default="signal_outcomes.csv", dest="out_path",
                    help="per-trade outcomes CSV to write")
    pr.add_argument("--since", default=None,
                    help="only review signals on/after this date, e.g. 2026-01-01 (YTD)")
    pr.add_argument("--setup", default=None, dest="only_setup",
                    help="list individual trades (ticker/dates/days/result) for one family")
    pr.add_argument("--by", default="setup",
                    choices=["setup", "symbol", "regime", "year", "month", "direction"],
                    help="break outcomes down by this dimension (default: setup)")

    pc = sub.add_parser("concentration",
                        help="is a setup a broad edge, or one ticker / one rally?")
    pc.add_argument("--source", default="synthetic",
                    choices=["synthetic", "csv", "polygon", "schwab", "stooq"])
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

    args = ap.parse_args(argv)
    if args.cmd == "edge":
        _run_edge(args.source, args.symbols, args.fast, args.years,
                  args.small_account, args.etf_only, args.account)
        return
    if args.cmd == "review":
        _run_review(args.source, args.years, args.in_path, args.out_path,
                    args.since, args.only_setup, args.by)
        return
    if args.cmd == "concentration":
        _run_concentration(args.source, args.years, args.in_path, args.out_path,
                           args.since, args.setups, args.min_oos)
        return
    if args.cmd == "log":
        _run_log(args.source, args.symbols, args.years, args.small_account,
                 args.etf_only, args.account, args.backfill_days, args.out_path)
        return
    source = args.source or ("synthetic" if args.cmd == "demo" else "synthetic")
    _run(source, args.symbols, fast=args.fast or args.cmd == "demo",
         years=args.years, etf_only=args.etf_only)


if __name__ == "__main__":
    main()
