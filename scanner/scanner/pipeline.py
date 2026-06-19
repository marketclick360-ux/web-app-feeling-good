"""
End-to-end orchestration: data -> setups -> backtest -> validation -> ranking.

Two entry points:
  * research(): for each setup family, backtest across the universe, split into
    development / out-of-sample / holdout, run walk-forward, bootstrap CIs,
    placebo, concentration, parameter-sensitivity and overfitting checks, score
    quality, and assign an accept/reject label.
  * scan(): produce CURRENT live candidates (signals triggered on the most
    recent completed bar; entry is the NEXT session open via a forward stop/
    limit order) and rank only those whose setup cleared validation.

Everything uses completed bars only and a single, explicit data timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import indicators as ind
from . import quality as quality_mod
from . import regime as regime_mod
from .data.base import DataAdapter
from .backtest import metrics
from .backtest.bootstrap import iid_bootstrap, block_bootstrap_expectancy, monte_carlo_drawdown
from .backtest.concentration import run_concentration
from .backtest.engine import BacktestEngine
from .backtest.overfitting import deflated_sharpe_ratio, pbo_cscv
from .backtest.placebo import random_date_placebo
from .backtest.walkforward import time_splits, walk_forward
from .costs import CostModel, DEFAULT_COSTS, scenario_costs
from .rank import SetupEvidence, build_table
from .setups.base import Setup, Signal, Direction
from .setups.registry import ALL_SETUPS, INTRADAY_ONLY, DEFAULT_RESEARCH_SETUPS
from .sizing import RiskConfig
from .validation import Evidence, evaluate
from . import params

# Minimal sector map for the default universe (concentration/sector tests).
SECTOR_MAP = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMD": "Tech", "AVGO": "Tech",
    "GOOGL": "Comm", "META": "Comm", "NFLX": "Comm", "DIS": "Comm",
    "AMZN": "Discretionary", "TSLA": "Discretionary", "HD": "Discretionary",
    "COST": "Staples", "WMT": "Staples", "PG": "Staples", "KO": "Staples",
    "JPM": "Financials", "BAC": "Financials", "XOM": "Energy", "CVX": "Energy",
    "UNH": "Health", "JNJ": "Health", "CRM": "Tech", "INTC": "Tech",
    "QCOM": "Tech", "MU": "Tech", "BA": "Industrials", "CAT": "Industrials",
    "GE": "Industrials", "F": "Discretionary",
    "SPY": "Index", "QQQ": "Index", "IWM": "Index", "DIA": "Index", "VTI": "Index",
    "XLF": "Sector", "XLK": "Sector", "XLE": "Sector", "XLV": "Sector",
    "XLI": "Sector", "XLY": "Sector", "XLP": "Sector", "XLB": "Sector",
    "XLU": "Sector", "XLRE": "Sector", "XLC": "Sector", "SMH": "Sector",
    "GLD": "Commodity", "SLV": "Commodity", "TLT": "Bonds", "HYG": "Bonds",
    "EEM": "Intl", "EFA": "Intl", "ARKK": "Sector", "IBB": "Sector",
}

# Sector label -> sector ETF, for relative-strength-vs-sector setups.
SECTOR_ETF = {
    "Tech": "XLK", "Comm": "XLC", "Discretionary": "XLY", "Staples": "XLP",
    "Financials": "XLF", "Energy": "XLE", "Health": "XLV",
    "Industrials": "XLI",
}


def _sector_close_map(adapter: DataAdapter, symbols, cfg, as_of):
    """symbol -> sector ETF close series (for sector_leader_continuation)."""
    needed = {SECTOR_ETF[SECTOR_MAP.get(s.upper(), "")]
              for s in symbols if SECTOR_MAP.get(s.upper(), "") in SECTOR_ETF}
    start = as_of - pd.Timedelta(days=int(cfg.years * 365.25) + 300)
    etf_close = {}
    for etf in needed:
        df = adapter.get_bars(etf, "1d", start=start, end=as_of, as_of=as_of).df
        if len(df) > 250:
            etf_close[etf] = df["close"]
    out = {}
    for s in symbols:
        etf = SECTOR_ETF.get(SECTOR_MAP.get(s.upper(), ""))
        if etf and etf in etf_close:
            out[s.upper()] = etf_close[etf]
    return out


@dataclass
class PipelineConfig:
    benchmark: str = "SPY"
    years: int = 10
    cost: CostModel = field(default_factory=lambda: DEFAULT_COSTS)  # 'normal' scenario
    risk: RiskConfig = field(default_factory=RiskConfig)
    n_boot: int = 2000
    param_perturb: tuple = (0.8, 0.9, 1.1, 1.2)  # multiplicative param sweeps
    placebo_runs: int = 100


@dataclass
class SetupResult:
    name: str
    verdict: object
    quality: Optional[dict]
    dev: dict
    oos: dict
    holdout: dict
    walk: dict
    boot: dict
    placebo: dict
    concentration: dict
    overfitting: dict
    cost_scenarios: dict = field(default_factory=dict)
    target_sweep: dict = field(default_factory=dict)
    n_signals_raw: int = 0
    n_symbols_tested: int = 0
    oos_trades: list = field(default_factory=list)


def _load_universe_frames(adapter: DataAdapter, symbols: List[str],
                          cfg: PipelineConfig, as_of: pd.Timestamp):
    start = as_of - pd.Timedelta(days=int(cfg.years * 365.25) + 60)
    frames, atr_lookup = {}, {}
    for sym in symbols:
        raw = adapter.get_bars(sym, "1d", start=start, end=as_of, as_of=as_of).df
        if len(raw) < 250:
            continue
        enr = ind.enrich_daily(raw)
        frames[sym] = enr
        atr_lookup[sym] = enr["atr14"]
    return frames, atr_lookup


def _backtest_setup(setup: Setup, frames, regime_by_sym, context, cfg: PipelineConfig,
                    cost: Optional[CostModel] = None):
    signals_by_symbol, bars_by_symbol = {}, {}
    for sym, df in frames.items():
        reg = regime_by_sym.get(sym)
        sigs = setup.generate(df, reg, sym, context)
        if sigs:
            signals_by_symbol[sym] = sigs
        bars_by_symbol[sym] = df
    engine = BacktestEngine(cost=cost or cfg.cost, risk=cfg.risk,
                            sector_map=SECTOR_MAP, enforce_portfolio_risk=True)
    trades = engine.run(signals_by_symbol, bars_by_symbol)
    n_signals = sum(len(v) for v in signals_by_symbol.values())
    return trades, engine, bars_by_symbol, n_signals


def _param_sensitivity(setup_cls, frames, regime_by_sym, context, cfg: PipelineConfig):
    """Perturb each numeric default param multiplicatively; collect OOS expectancy."""
    base = setup_cls.default_params()
    expectancies = []
    perf_rows = []  # for PBO: rows = configs, but we transpose later
    configs = []
    for pname, pval in base.items():
        if not isinstance(pval, (int, float)) or isinstance(pval, bool):
            continue
        for mult in cfg.param_perturb:
            overrides = {pname: type(pval)(pval * mult)} if pval else {}
            if not overrides:
                continue
            s = setup_cls(**overrides)
            trades, _, _, _ = _backtest_setup(s, frames, regime_by_sym, context, cfg)
            _, oos, _ = time_splits(trades)
            m = metrics.summary(oos)
            expectancies.append(m.get("expectancy_r", 0.0))
            configs.append(f"{pname}x{mult}")
            # yearly expectancy vector for PBO
            if oos:
                df = pd.DataFrame([t.__dict__ for t in oos])
                yearly = df.groupby("year")["realized_r"].mean()
                perf_rows.append(yearly)
    return expectancies, configs, perf_rows


def research(adapter: DataAdapter, symbols: List[str],
             setup_names: Optional[List[str]] = None,
             cfg: Optional[PipelineConfig] = None,
             as_of: Optional[pd.Timestamp] = None) -> Dict[str, SetupResult]:
    cfg = cfg or PipelineConfig()
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    setup_names = setup_names or list(DEFAULT_RESEARCH_SETUPS)

    frames, atr_lookup = _load_universe_frames(adapter, symbols, cfg, as_of)
    # benchmark + regime
    bench_raw = adapter.get_bars(cfg.benchmark, "1d",
                                 start=as_of - pd.Timedelta(days=int(cfg.years*365.25)+260),
                                 end=as_of, as_of=as_of).df
    bench = ind.enrich_daily(bench_raw)
    reg_df = regime_mod.classify(bench_raw)
    context = {"benchmark": bench,
               "sector_close": _sector_close_map(adapter, list(frames), cfg, as_of)}
    regime_by_sym = {sym: reg_df["regime"].reindex(df.index).ffill().fillna("UNKNOWN")
                     for sym, df in frames.items()}

    results: Dict[str, SetupResult] = {}
    n_trials_global = len(setup_names) * (1 + len(cfg.param_perturb) * 3)

    for name in setup_names:
        setup_cls = ALL_SETUPS[name]
        setup = setup_cls()
        trades, engine, bars_by_symbol, n_signals_raw = _backtest_setup(
            setup, frames, regime_by_sym, context, cfg)
        dev_t, oos_t, hold_t = time_splits(trades)
        dev, oos, hold = (metrics.summary(dev_t), metrics.summary(oos_t),
                          metrics.summary(hold_t))
        walk = walk_forward(trades)

        # With zero OOS trades there is nothing to test — do NOT run placebo /
        # concentration / bootstrap / cost / overfitting claims on an empty set.
        has_sample = len(oos_t) > 0
        if has_sample:
            boot = {"iid": iid_bootstrap(oos_t, n_boot=cfg.n_boot),
                    "block": block_bootstrap_expectancy(oos_t, n_boot=cfg.n_boot),
                    "mc_drawdown": monte_carlo_drawdown(oos_t)}
            conc = run_concentration(oos_t)
            plac = random_date_placebo(oos_t, bars_by_symbol, engine, atr_lookup,
                                       n_runs=cfg.placebo_runs)
            cost_scenarios = {}
            for scen in params.COST_SCENARIOS:
                sc_trades, _, _, _ = _backtest_setup(setup, frames, regime_by_sym, context,
                                                  cfg, cost=scenario_costs(scen))
                _, sc_oos, _ = time_splits(sc_trades)
                cost_scenarios[scen] = metrics.summary(sc_oos)
            st = cost_scenarios[params.ACCEPTANCE_SCENARIO]
            cost_survives = (st.get("expectancy_r", -1) > 0
                             and st.get("profit_factor", 0) >= params.MIN_PROFIT_FACTOR)
            param_exps, configs, perf_rows = _param_sensitivity(
                setup_cls, frames, regime_by_sym, context, cfg)
        else:
            boot, conc, plac, cost_scenarios = {}, {}, {}, {}
            cost_survives = False
            param_exps, configs, perf_rows = [], [], []

        # target-R sweep: test 2.0R / 2.5R / 3.0R for transparency (research only;
        # acceptance still requires the 3R variant to pass every gate).
        target_sweep = {}
        if has_sample:
            for r_mult in (2.0, 2.5, 3.0):
                sw_trades, _, _, _ = _backtest_setup(setup_cls(planned_r=r_mult),
                                                  frames, regime_by_sym, context, cfg)
                _, sw_oos, _ = time_splits(sw_trades)
                target_sweep[r_mult] = metrics.summary(sw_oos)
        param_stable = bool(param_exps and np.mean(param_exps) > 0
                            and (np.std(param_exps) / (abs(np.mean(param_exps)) + 1e-9)) < 1.0)

        # overfitting
        oos_r = np.array([t.realized_r for t in oos_t]) if oos_t else np.array([])
        dsr = deflated_sharpe_ratio(oos_r, n_trials=n_trials_global) if len(oos_r) > 2 else {}
        pbo = {}
        if len(perf_rows) >= 2:
            mat = pd.concat(perf_rows, axis=1).fillna(0.0).to_numpy()
            pbo = pbo_cscv(mat)
        overfit = {"deflated_sharpe": dsr, "pbo": pbo, "n_trials": n_trials_global}

        # regime robustness
        reg_bd = metrics.breakdown(oos_t, "regime")
        regime_pos_frac = (float((reg_bd["expectancy_r"] > 0).mean())
                           if not reg_bd.empty else 0.0)

        # quality score
        ci_low = boot.get("iid", {}).get("expectancy_r", {}).get("ci_low", float("nan"))
        q_inputs = quality_mod.QualityInputs(
            oos_expectancy_r=oos.get("expectancy_r", float("nan")),
            oos_expectancy_ci_low=ci_low,
            profit_factor=oos.get("profit_factor", 0.0),
            regime_positive_fraction=regime_pos_frac,
            param_expectancies=param_exps,
            concentration_passes=conc.get("passes", False),
            concentration_min_expectancy=min(
                [v.get("expectancy_r", 0) for k, v in conc.items()
                 if isinstance(v, dict)] or [0.0]),
            placebo_p_value=plac.get("p_value", 1.0),
            liquidity_ok=True,
            trades_per_year=(oos.get("n_trades", 0) / max(cfg.years * 0.3, 1)),
        ) if oos.get("n_trades", 0) > 0 else None
        qual = quality_mod.score(q_inputs)

        ev = Evidence(
            n_oos_trades=oos.get("n_trades", 0),
            oos_win_rate=oos.get("win_rate", 0.0),
            oos_expectancy_r=oos.get("expectancy_r", -1.0),
            oos_profit_factor=oos.get("profit_factor", 0.0),
            oos_expectancy_ci_low=ci_low if ci_low == ci_low else -1.0,
            planned_target_r=oos.get("planned_target_r", setup.target_r),
            holdout_expectancy_r=hold.get("expectancy_r") if hold.get("n_trades") else None,
            regime_positive_fraction=regime_pos_frac,
            param_stable=param_stable,
            concentration_passes=conc.get("passes", False),
            placebo_passes=plac.get("passes", False),
            cost_stress_survives=cost_survives,
            gap_tail_rate=oos.get("gap_tail_rate", 0.0),
            n_trials_tested=n_trials_global,
            pbo=pbo.get("pbo"),
        )
        verdict = evaluate(ev)

        results[name] = SetupResult(
            name=name, verdict=verdict, quality=qual, dev=dev, oos=oos,
            holdout=hold, walk=walk, boot=boot, placebo=plac,
            concentration=conc, overfitting=overfit,
            cost_scenarios=cost_scenarios, target_sweep=target_sweep,
            n_signals_raw=n_signals_raw, n_symbols_tested=len(frames),
            oos_trades=oos_t)
    return results


def live_signals(adapter: DataAdapter, symbols: List[str], setup_names: List[str],
                 cfg: PipelineConfig, as_of: pd.Timestamp) -> (List[Signal], str):
    """Signals triggered on the most recent completed bar. Entry is the NEXT
    session open via a forward stop/limit order (represented with a synthetic
    forward bar whose open == last close, clearly a proxy until the bar exists)."""
    frames, _ = _load_universe_frames(adapter, symbols, cfg, as_of)
    bench_raw = adapter.get_bars(cfg.benchmark, "1d",
                                 start=as_of - pd.Timedelta(days=int(cfg.years*365.25)+260),
                                 end=as_of, as_of=as_of).df
    context = {"benchmark": ind.enrich_daily(bench_raw),
               "sector_close": _sector_close_map(adapter, list(frames), cfg, as_of)}
    reg_df = regime_mod.classify(bench_raw)

    out: List[Signal] = []
    data_ts = None
    for sym, df in frames.items():
        if df.empty:
            continue
        last_ts = df.index[-1]
        data_ts = max(data_ts, last_ts) if data_ts else last_ts
        # append a forward proxy bar so the last real bar can be a signal bar
        fwd_idx = df.index[-1] + (df.index[-1] - df.index[-2])
        fwd = df.iloc[[-1]].copy()
        fwd.index = [fwd_idx]
        fwd["open"] = df["close"].iloc[-1]
        ext = pd.concat([df, fwd])
        reg = reg_df["regime"].reindex(ext.index).ffill().fillna("UNKNOWN")
        for name in setup_names:
            sigs = ALL_SETUPS[name]().generate(ext, reg, sym, context)
            out.extend([s for s in sigs if s.signal_time == last_ts])
    ts_str = f"{data_ts.isoformat()} (most recent completed daily bar)" if data_ts \
        else "UNKNOWN"
    return out, ts_str


def evaluate_logged_signals(adapter: DataAdapter, rows: list,
                            cfg: PipelineConfig, as_of: pd.Timestamp) -> list:
    """Replay logged paper candidates through the SAME backtest engine (gap
    handling, stop/target/time-stop) to see how each actually played out. Each
    row needs date, symbol, setup, direction, entry, stop, target_3R. Trades
    that haven't completed yet (not enough forward bars) are excluded = still
    open. Returns Trade objects (realized_r is in R units)."""
    from .backtest.engine import BacktestEngine

    by_sym = {}
    for r in rows:
        by_sym.setdefault(str(r["symbol"]).upper(), []).append(r)

    signals_by_symbol, bars_by_symbol = {}, {}
    start = as_of - pd.Timedelta(days=int(cfg.years * 365.25) + 500)
    for sym, rs in by_sym.items():
        bars = adapter.get_bars(sym, "1d", start=start, end=as_of, as_of=as_of).df
        if bars.empty:
            continue
        bars_by_symbol[sym] = bars
        sigs = []
        for r in rs:
            try:
                st = pd.Timestamp(str(r["date"]), tz="UTC")
                entry, stop, tgt = float(r["entry"]), float(r["stop"]), float(r["target_3R"])
            except (ValueError, KeyError, TypeError):
                continue
            if st not in bars.index or entry == stop:
                continue
            d = Direction.LONG if str(r["direction"]) == "long" else Direction.SHORT
            sigs.append(Signal(sym, d, str(r["setup"]), st, entry, stop, tgt,
                               planned_r_multiple=3.0, time_stop_bars=10))
        if sigs:
            signals_by_symbol[sym] = sigs
    engine = BacktestEngine(sector_map=SECTOR_MAP, enforce_portfolio_risk=False)
    return engine.run(signals_by_symbol, bars_by_symbol)


def build_signal_log(adapter: DataAdapter, symbols: List[str], setup_names: List[str],
                     cfg: PipelineConfig, as_of: pd.Timestamp,
                     backfill_days: int = 365, account: float = 2000.0) -> list:
    """Every signal each family would have fired over the last `backfill_days`,
    as flat log rows (for a paper journal). Includes a forward-proxy bar so the
    freshest signal on the most recent completed bar is captured too. Each row
    is HYPOTHETICAL — a paper candidate, not a trade. Dedup is the caller's job."""
    from .tradability import score as trad_score

    frames, _ = _load_universe_frames(adapter, symbols, cfg, as_of)
    bench_raw = adapter.get_bars(cfg.benchmark, "1d",
                                 start=as_of - pd.Timedelta(days=int(cfg.years*365.25)+260),
                                 end=as_of, as_of=as_of).df
    context = {"benchmark": ind.enrich_daily(bench_raw),
               "sector_close": _sector_close_map(adapter, list(frames), cfg, as_of)}
    reg_df = regime_mod.classify(bench_raw)
    cutoff = as_of - pd.Timedelta(days=backfill_days)

    rows = []
    for name in setup_names:
        setup = ALL_SETUPS[name]()
        for sym, df in frames.items():
            if df.empty or len(df) < 2:
                continue
            fwd_idx = df.index[-1] + (df.index[-1] - df.index[-2])
            fwd = df.iloc[[-1]].copy()
            fwd.index = [fwd_idx]
            fwd["open"] = df["close"].iloc[-1]
            ext = pd.concat([df, fwd])
            reg = reg_df["regime"].reindex(ext.index).ffill().fillna("UNKNOWN")
            for s in setup.generate(ext, reg, sym, context):
                if s.signal_time < cutoff:
                    continue
                erow = df.loc[s.signal_time] if s.signal_time in df.index else None
                atr = float(erow["atr14"]) if erow is not None and erow["atr14"] == erow["atr14"] \
                    else float("nan")
                adv = float(erow["adv20"]) if erow is not None and erow.get("adv20") == erow.get("adv20") \
                    else 0.0
                risk = s.risk_per_share
                d = 1 if s.direction.value == "long" else -1
                t = trad_score(s.entry_ref, adv, atr if atr == atr else s.entry_ref * 0.02,
                               risk, account)
                fresh = s.signal_time == df.index[-1]
                rows.append({
                    "date": s.signal_time.date().isoformat(),
                    "symbol": sym.upper(), "setup": name, "direction": s.direction.value,
                    "regime": s.regime_at_signal,
                    "entry": round(s.entry_ref, 2), "stop": round(s.stop, 2),
                    "risk_per_share": round(risk, 2),
                    "target_2R": round(s.entry_ref + d * 2 * risk, 2),
                    "target_2_5R": round(s.entry_ref + d * 2.5 * risk, 2),
                    "target_3R": round(s.target, 2),
                    "atr": round(atr, 2) if atr == atr else "",
                    "adv_dollar_M": round(adv / 1e6, 1),
                    "tradability": f"{t.score:.0f}/{t.grade}",
                    "fresh_on_last_bar": "YES" if fresh else "",
                    "status": "HYPOTHETICAL — paper only",
                })
    rows.sort(key=lambda r: (r["date"], r["symbol"], r["setup"]))
    return rows
