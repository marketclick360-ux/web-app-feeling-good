"""
Defensive swing-trading model — exit & risk-control research.

GOAL (stated by the user): using the SAME entries we already have, find the
exit + risk-management combination that "loses the least when wrong, keeps
drawdown low, and still produces positive expectancy." This module does NOT
invent or tune entries, and it does NOT optimize anything per ticker.

It holds the entries fixed and varies only what happens AFTER entry:

  EXIT MODELS (6)
    target_1.5R           fixed +1.5R target, -1R stop
    target_2R             fixed +2.0R target, -1R stop
    target_2.5R           fixed +2.5R target, -1R stop
    breakeven_then_2R     -1R stop; once +1R is touched, stop -> breakeven; target +2R
    partial_1R_2R         sell half at +1R, move stop on the rest to breakeven, target +2R
    trail_after_1.5R      -1R stop; after +1.5R, trail the stop 1R below the running high

  RISK FILTERS (4) — only take a signal when the market is "risk-on"
    none                  take every signal
    spy_200d              SPY close > its 200-day moving average
    abs_momentum          SPY 12-month total return > 0
    dual_momentum         SPY 12-month return > AGG 12-month return AND SPY 12m > 0

  RISK CONTROLS (portfolio replay) — max 1 new trade/month, max N open,
    position cap (% of equity), fixed-fractional account risk, and an optional
    monthly circuit-breaker that stops new trades for the rest of a month once
    that month is down -2R (or -3R).

Realism: indicators on completed bars, entry filled at the NEXT bar's open,
slippage+spread on both sides, gap-through-stop recorded as the ACTUAL loss
(can be worse than -1R), conservative same-bar (stop assumed before target),
time-stop exit. Nothing here is a live-trading green light — results are
labeled REJECTED / STATISTICALLY INCONCLUSIVE / TENTATIVE / PAPER-TRACK ONLY.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import indicators as ind
from . import regime as regime_mod
from . import params
from .costs import CostModel, DEFAULT_COSTS
from .data.base import DataAdapter
from .setups.base import Direction
from .setups.registry import ALL_SETUPS, DEFAULT_RESEARCH_SETUPS
from .pipeline import (PipelineConfig, SECTOR_MAP, _load_universe_frames,
                       _sector_close_map)

EXIT_MODELS = ["target_1.5R", "target_2R", "target_2.5R",
               "breakeven_then_2R", "partial_1R_2R", "trail_after_1.5R"]
RISK_FILTERS = ["none", "spy_200d", "abs_momentum", "dual_momentum"]

# Each exit model's planned reward-to-risk, for the design-gate label. Trailing
# has no fixed target (it lets winners run), so it has no planned R.
_PLANNED_R = {"target_1.5R": 1.5, "target_2R": 2.0, "target_2.5R": 2.5,
              "breakeven_then_2R": 2.0, "partial_1R_2R": 2.0,
              "trail_after_1.5R": float("nan")}

# Lowered design gate for THIS research (the user asked to test 2R/2.5R exits).
MIN_PLANNED_R_DEFENSIVE = 2.0


@dataclass
class RiskControls:
    risk_pct: float = 0.01          # fixed-fractional account risk per trade
    max_open: int = 2               # max simultaneous open positions
    max_new_per_month: int = 1      # max new trades opened per calendar month
    position_cap_pct: float = 0.10  # a single position's notional cap (% equity)
    month_stop_r: Optional[float] = -2.0  # stop new trades the rest of a -2R month
    start_equity: float = 30_000.0


# --------------------------------------------------------------------------
# Single-trade exit simulation (the 6 exit models)
# --------------------------------------------------------------------------
def _simulate_variant(bars: pd.DataFrame, fill_pos: int, is_long: bool,
                      entry_ref: float, init_stop: float, time_stop_bars: int,
                      variant: str, cost: CostModel) -> Optional[dict]:
    """Simulate one entry under one exit model. Returns a result dict or None
    when there is not enough forward data to complete the trade (excluded)."""
    n = len(bars)
    if fill_pos >= n:
        return None
    R = abs(entry_ref - init_stop)
    if R <= 0:
        return None
    entry_fill = cost.effective_entry(float(bars["open"].iloc[fill_pos]), is_long)
    sgn = 1.0 if is_long else -1.0

    def lvl(k):  # price level k*R favorable from the reference entry
        return entry_ref + sgn * k * R

    # exit-model configuration
    fixed_target = {"target_1.5R": 1.5, "target_2R": 2.0, "target_2.5R": 2.5,
                    "breakeven_then_2R": 2.0, "partial_1R_2R": 2.0}.get(variant)
    target_price = lvl(fixed_target) if fixed_target is not None else None
    be_after = 1.0 if variant in ("breakeven_then_2R", "partial_1R_2R") else None
    trail_after = 1.5 if variant == "trail_after_1.5R" else None
    partial = variant == "partial_1R_2R"

    stop = init_stop
    be_armed = False
    trail_armed = False
    fav_extreme = entry_ref  # running most-favorable price (for trailing)
    partial_done = False
    partial_r = 0.0          # realized R already banked on the half that was sold
    weight = 1.0             # fraction of the position still open

    eval_last = min(fill_pos + time_stop_bars - 1, n - 1)
    mfe = 0.0
    mae = 0.0

    def _favR(price):
        return sgn * (price - entry_ref) / R

    def _close(exit_price, reason, exit_pos):
        exit_fill = cost.effective_exit(exit_price, is_long)
        leg_r = sgn * (exit_fill - entry_fill) / R
        realized_r = partial_r + weight * leg_r
        return {"entry_fill": entry_fill, "exit_fill": exit_fill,
                "exit_pos": exit_pos, "exit_reason": reason,
                "realized_r": realized_r}

    result = None
    for pos in range(fill_pos, eval_last + 1):
        bar = bars.iloc[pos]
        o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])
        hi_favR = _favR(h if is_long else l)   # most favorable excursion this bar
        lo_favR = _favR(l if is_long else h)   # most adverse excursion this bar
        mfe = max(mfe, hi_favR)
        mae = min(mae, lo_favR)

        # --- gap at the open against the CURRENT stop (actual loss recorded) ---
        gap_stop = (o <= stop) if is_long else (o >= stop)
        if gap_stop:
            result = _close(o, "gap_stop", pos)
            break
        if target_price is not None:
            gap_tgt = (o >= target_price) if is_long else (o <= target_price)
            if gap_tgt:
                result = _close(o, "gap_target", pos)
                break

        # --- intrabar: stop checked before target (conservative) ---
        stop_hit = (l <= stop) if is_long else (h >= stop)
        if stop_hit:
            result = _close(stop, "stop", pos)
            break
        if target_price is not None:
            tgt_hit = (h >= target_price) if is_long else (l <= target_price)
            if tgt_hit:
                result = _close(target_price, "target", pos)
                break

        # --- partial profit-take at +1R on the way up ---
        if partial and not partial_done:
            reached_1r = (h >= lvl(1.0)) if is_long else (l <= lvl(1.0))
            if reached_1r:
                half_exit = cost.effective_exit(lvl(1.0), is_long)
                partial_r = 0.5 * (sgn * (half_exit - entry_fill) / R)
                weight = 0.5
                partial_done = True
                be_armed = True  # move the remaining half's stop to breakeven

        # --- arm breakeven once +1R touched ---
        if be_after is not None and not be_armed:
            if (h >= lvl(be_after)) if is_long else (l <= lvl(be_after)):
                be_armed = True
        if be_armed:
            stop = entry_ref if is_long else entry_ref  # breakeven (reference)
            stop = max(stop, init_stop) if is_long else min(stop, init_stop)
            stop = entry_ref  # exact breakeven

        # --- arm / advance the trailing stop ---
        fav_extreme = max(fav_extreme, h) if is_long else min(fav_extreme, l)
        if trail_after is not None:
            if not trail_armed and ((h >= lvl(trail_after)) if is_long
                                    else (l <= lvl(trail_after))):
                trail_armed = True
            if trail_armed:
                trail_stop = (fav_extreme - R) if is_long else (fav_extreme + R)
                stop = max(stop, trail_stop) if is_long else min(stop, trail_stop)

    if result is None:
        # time stop -> exit at the open of the first bar after the holding window
        ts_pos = fill_pos + time_stop_bars
        if ts_pos >= n:
            return None  # not enough forward data: incomplete -> excluded
        result = _close(float(bars["open"].iloc[ts_pos]), "time", ts_pos)

    exit_pos = result["exit_pos"]
    realized_r = result["realized_r"]
    return {
        "entry_time": bars.index[fill_pos],
        "exit_time": bars.index[exit_pos],
        "entry_price": result["entry_fill"],
        "exit_price": result["exit_fill"],
        "bars_held": int(exit_pos - fill_pos),
        "exit_reason": result["exit_reason"],
        "realized_r": float(realized_r),
        "mfe_r": float(mfe), "mae_r": float(mae),
        "reached_1R": bool(mfe >= 1.0), "reached_1_5R": bool(mfe >= 1.5),
        "reached_2R": bool(mfe >= 2.0), "reached_2_5R": bool(mfe >= 2.5),
        "worse_than_1r": bool(realized_r < -1.0),
        "entry_ref": float(entry_ref), "risk_per_share": float(R),
    }


# --------------------------------------------------------------------------
# Risk-filter overlays (risk-on / risk-off series, no look-ahead)
# --------------------------------------------------------------------------
def _filter_series(name: str, bench: pd.DataFrame,
                   bond: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    """Boolean 'risk-on' series on the benchmark's index, or None for 'none'.
    Every condition uses only completed-bar data as of each date."""
    if name == "none":
        return None
    close = bench["close"]
    if name == "spy_200d":
        return close > close.rolling(200).mean()
    if name == "abs_momentum":  # 12-month (252-session) total return > 0
        return close > close.shift(252)
    if name == "dual_momentum":
        spy_mom = close / close.shift(252) - 1.0
        if bond is None or "close" not in bond:
            return spy_mom > 0
        bclose = bond["close"].reindex(close.index).ffill()
        bond_mom = bclose / bclose.shift(252) - 1.0
        return (spy_mom > 0) & (spy_mom > bond_mom)
    return None


# --------------------------------------------------------------------------
# R-level metrics on a list of trade dicts
# --------------------------------------------------------------------------
def _max_consec_losses(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        best = max(best, cur)
    return best


def _max_dd_r(r: np.ndarray) -> float:
    if len(r) == 0:
        return 0.0
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(eq)
    return float((peak - eq).max())


def _bootstrap_ci_low(r: np.ndarray, n_boot: int = 1000,
                      seed: int = 7) -> float:
    if len(r) < 2:
        return float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(r), size=(n_boot, len(r)))
    means = r[idx].mean(axis=1)
    return float(np.percentile(means, 2.5))


def _r_metrics(rows: List[dict]) -> dict:
    if not rows:
        return {"n": 0}
    df = pd.DataFrame(rows)
    r = df["realized_r"].to_numpy()
    wins = r[r > 0]
    losses = r[r <= 0]
    gl = -losses.sum()
    pf = float(wins.sum() / gl) if gl > 0 else float("inf")
    return {
        "n": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "expectancy_r": float(r.mean()),
        "avg_win_r": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": pf,
        "max_dd_r": _max_dd_r(r),
        "worst_streak": _max_consec_losses(r),
        "worst_loss_r": float(r.min()),
        "ci_low": _bootstrap_ci_low(r),
        "pct_reach_1R": float(df["reached_1R"].mean()),
        "pct_reach_1_5R": float(df["reached_1_5R"].mean()),
        "pct_reach_2R": float(df["reached_2R"].mean()),
        "pct_reach_2_5R": float(df["reached_2_5R"].mean()),
        "gap_tail_rate": float(df["worse_than_1r"].mean()),
        "n_gap_stops": int((df["exit_reason"] == "gap_stop").sum()),
        "worst_trades": [
            (str(t["symbol"]),
             pd.Timestamp(t["entry_time"]).date().isoformat(),
             round(float(t["realized_r"]), 2))
            for _, t in df.nsmallest(5, "realized_r").iterrows()],
    }


def _concentration(rows: List[dict]) -> dict:
    """Best-ticker share of gross profit and expectancy WITHOUT the best ticker.
    If dropping the single best ticker flips expectancy non-positive, the edge is
    concentration-driven -> fails."""
    if not rows:
        return {"best_ticker": "", "best_share": 0.0,
                "exp_without_best": 0.0, "passes": False}
    df = pd.DataFrame(rows)
    gross_by = df[df["realized_r"] > 0].groupby("symbol")["realized_r"].sum()
    total_gross = float(gross_by.sum())
    if total_gross <= 0:
        return {"best_ticker": "", "best_share": 0.0,
                "exp_without_best": float(df["realized_r"].mean()), "passes": False}
    best = gross_by.idxmax()
    best_share = float(gross_by.max() / total_gross)
    without = df[df["symbol"] != best]["realized_r"]
    exp_wo = float(without.mean()) if len(without) else 0.0
    passes = bool(exp_wo > 0 and best_share <= 0.40)
    return {"best_ticker": str(best), "best_share": best_share,
            "exp_without_best": exp_wo, "passes": passes,
            "n_without_best": int(len(without))}


# --------------------------------------------------------------------------
# Portfolio replay with risk controls (monthly P&L, drawdown %, etc.)
# --------------------------------------------------------------------------
def _month_key(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"{ts.year:04d}-{ts.month:02d}"


def portfolio_replay(rows: List[dict], rc: RiskControls) -> dict:
    """Sequentially apply the risk controls to the trade stream and return a
    $-level summary: total return, max drawdown %, monthly P&L, % profitable
    months. Sizing is fixed-fractional on planned risk, capped by position size;
    a -Xr month halts new entries for the rest of that month."""
    if not rows:
        return {"n_taken": 0}
    trades = sorted(rows, key=lambda x: pd.Timestamp(x["signal_time"]))
    equity = rc.start_equity
    open_book: List[dict] = []          # {exit_time, pnl, realized_r}
    realized: List[dict] = []           # {exit_time, pnl, realized_r}
    month_new: Dict[str, int] = {}
    month_realized_r: Dict[str, float] = {}
    blocked: set = set()
    eq_points: List[tuple] = [(None, equity)]

    def _realize_until(t):
        nonlocal equity
        open_book.sort(key=lambda x: pd.Timestamp(x["exit_time"]))
        while open_book and pd.Timestamp(open_book[0]["exit_time"]) <= pd.Timestamp(t):
            ev = open_book.pop(0)
            equity += ev["pnl"]
            realized.append(ev)
            mk = _month_key(ev["exit_time"])
            month_realized_r[mk] = month_realized_r.get(mk, 0.0) + ev["realized_r"]
            if rc.month_stop_r is not None and month_realized_r[mk] <= rc.month_stop_r:
                blocked.add(mk)
            eq_points.append((ev["exit_time"], equity))

    for tr in trades:
        st = tr["signal_time"]
        _realize_until(st)
        mk = _month_key(st)
        if len(open_book) >= rc.max_open:
            continue
        if month_new.get(mk, 0) >= rc.max_new_per_month:
            continue
        if mk in blocked:
            continue
        rps = tr["risk_per_share"]
        entry_ref = tr["entry_ref"]
        if rps <= 0 or entry_ref <= 0:
            continue
        shares = min(rc.risk_pct * equity / rps,
                     rc.position_cap_pct * equity / entry_ref)
        shares = int(shares)
        if shares <= 0:
            continue
        pnl = tr["realized_r"] * shares * rps
        open_book.append({"exit_time": tr["exit_time"], "pnl": pnl,
                          "realized_r": tr["realized_r"]})
        month_new[mk] = month_new.get(mk, 0) + 1

    _realize_until(pd.Timestamp.max.tz_localize("UTC")
                   if pd.Timestamp(trades[0]["signal_time"]).tz else pd.Timestamp.max)

    if not realized:
        return {"n_taken": 0}
    eq = np.array([p[1] for p in eq_points])
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    monthly = {}
    for ev in realized:
        monthly[_month_key(ev["exit_time"])] = \
            monthly.get(_month_key(ev["exit_time"]), 0.0) + ev["pnl"]
    months = sorted(monthly)
    pnl_vals = np.array([monthly[m] for m in months])
    return {
        "n_taken": len(realized),
        "start_equity": rc.start_equity,
        "end_equity": float(equity),
        "total_return_pct": float((equity / rc.start_equity - 1.0) * 100.0),
        "max_dd_pct": float(dd.max() * 100.0) if len(dd) else 0.0,
        "n_months": len(months),
        "pct_profitable_months": float((pnl_vals > 0).mean() * 100.0) if len(pnl_vals) else 0.0,
        "best_month": float(pnl_vals.max()) if len(pnl_vals) else 0.0,
        "worst_month": float(pnl_vals.min()) if len(pnl_vals) else 0.0,
        "monthly_pnl": {m: float(monthly[m]) for m in months},
    }


# --------------------------------------------------------------------------
# Labeling (the four honest labels the user asked for)
# --------------------------------------------------------------------------
def _label(m: dict, conc: dict, planned_r: float,
           min_planned_r: float = MIN_PLANNED_R_DEFENSIVE) -> tuple:
    """Return (label, reason). planned_r may be NaN (trailing has no fixed R)."""
    n = m.get("n", 0)
    if n <= 0:
        return "STATISTICALLY INCONCLUSIVE", "no out-of-sample trades"
    if planned_r == planned_r and planned_r < min_planned_r:
        return "REJECTED", (f"planned {planned_r:.1f}R < {min_planned_r:.1f}R "
                            "design floor")
    exp = m["expectancy_r"]
    pf = m["profit_factor"]
    if exp <= 0:
        return "REJECTED", f"OOS expectancy {exp:+.3f}R not positive"
    if pf < params.MIN_PROFIT_FACTOR:
        return "REJECTED", f"profit factor {pf:.2f} < {params.MIN_PROFIT_FACTOR}"
    if not conc.get("passes", False):
        return "REJECTED", (f"concentration: best ticker "
                            f"{conc.get('best_ticker','?')} "
                            f"{conc.get('best_share',0):.0%} of profit, "
                            f"exp without it {conc.get('exp_without_best',0):+.3f}R")
    if n < params.MIN_OOS_TRADES:
        return "STATISTICALLY INCONCLUSIVE", (f"only {n} OOS trades "
                                              f"(< {params.MIN_OOS_TRADES})")
    if m.get("ci_low", -1) <= 0:
        return "STATISTICALLY INCONCLUSIVE", "95% CI for expectancy includes zero"
    # passes the hard gates with an adequate, concentration-resilient sample
    soft = (m["win_rate"] <= 0.45 or n < params.PREFERRED_OOS_TRADES
            or m["gap_tail_rate"] > 0.10)
    if soft:
        return "TENTATIVE", "passes gates but has soft flags (sample/win-rate/gaps)"
    return "PAPER-TRACK ONLY", "passes every gate at this sample"


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
@dataclass
class DefensiveResult:
    combos: list = field(default_factory=list)   # list of dicts (one per exit×filter)
    best: Optional[dict] = None
    n_symbols: int = 0
    n_entries: int = 0
    suspects: list = field(default_factory=list)  # (symbol, date, R) excluded as bad bars
    max_abs_r: float = 0.0


def _oos_rows(rows: List[dict], frac: float = 0.4) -> List[dict]:
    """Most-recent `frac` of trades by signal time = out-of-sample slice (the
    development half is held back, mirroring the pipeline's time_splits)."""
    if not rows:
        return []
    ordered = sorted(rows, key=lambda x: pd.Timestamp(x["signal_time"]))
    cut = int(len(ordered) * (1.0 - frac))
    return ordered[cut:]


def run_defensive(adapter: DataAdapter, symbols: List[str],
                  cfg: Optional[PipelineConfig] = None,
                  as_of: Optional[pd.Timestamp] = None,
                  setup_names: Optional[List[str]] = None,
                  exits: Optional[List[str]] = None,
                  filters: Optional[List[str]] = None,
                  rc: Optional[RiskControls] = None,
                  bond_symbol: str = "AGG",
                  max_abs_r: float = 10.0) -> DefensiveResult:
    cfg = cfg or PipelineConfig()
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    setup_names = setup_names or list(DEFAULT_RESEARCH_SETUPS)
    exits = exits or list(EXIT_MODELS)
    filters = filters or list(RISK_FILTERS)
    rc = rc or RiskControls()
    cost = cfg.cost or DEFAULT_COSTS

    frames, _ = _load_universe_frames(adapter, symbols, cfg, as_of)
    if not frames:
        return DefensiveResult()

    start = as_of - pd.Timedelta(days=int(cfg.years * 365.25) + 320)
    bench_raw = adapter.get_bars(cfg.benchmark, "1d", start=start, end=as_of,
                                 as_of=as_of).df
    bench = ind.enrich_daily(bench_raw)
    bond = None
    try:
        bond_raw = adapter.get_bars(bond_symbol, "1d", start=start, end=as_of,
                                    as_of=as_of).df
        if len(bond_raw) > 252:
            bond = ind.enrich_daily(bond_raw)
    except Exception:
        bond = None
    reg_df = regime_mod.classify(bench_raw)
    context = {"benchmark": bench,
               "sector_close": _sector_close_map(adapter, list(frames), cfg, as_of)}
    regime_by_sym = {sym: reg_df["regime"].reindex(df.index).ffill().fillna("UNKNOWN")
                     for sym, df in frames.items()}

    # 1) Generate the (fixed) entries once per setup/symbol.
    entries = []  # (symbol, signal_time, is_long, entry_ref, init_stop, time_stop, setup)
    for name in setup_names:
        setup = ALL_SETUPS[name]()
        for sym, df in frames.items():
            for s in setup.generate(df, regime_by_sym.get(sym), sym, context):
                if s.signal_time not in df.index:
                    continue
                sig_pos = df.index.get_loc(s.signal_time)
                fill_pos = sig_pos + cost.delay_bars
                entries.append({
                    "symbol": sym, "signal_time": s.signal_time,
                    "is_long": s.direction is Direction.LONG,
                    "entry_ref": s.entry_ref, "init_stop": s.stop,
                    "time_stop_bars": s.time_stop_bars, "setup": name,
                    "fill_pos": fill_pos,
                })

    # 2) Pre-compute each risk filter as a risk-on boolean on the bench index.
    filt_series = {f: _filter_series(f, bench, bond) for f in filters}

    # Data-quality guard: a single trade whose realized loss/gain exceeds
    # `max_abs_r` (default 10R) on a liquid ETF is almost certainly a corrupt
    # bar (an unadjusted split / bad print), not a real fill. We EXCLUDE such
    # trades from the statistics and disclose them, rather than let one phantom
    # -51R trade distort every result.
    suspect_map = {}   # (symbol, date) -> worst R seen (for disclosure)
    combos = []
    for filt in filters:
        ro = filt_series[filt]
        if ro is not None:
            ro = ro.reindex(bench.index).ffill().fillna(False)
        for variant in exits:
            rows = []
            for e in entries:
                if ro is not None and not bool(ro.get(e["signal_time"], False)):
                    continue
                df = frames[e["symbol"]]
                res = _simulate_variant(
                    df, e["fill_pos"], e["is_long"], e["entry_ref"],
                    e["init_stop"], e["time_stop_bars"], variant, cost)
                if res is None:
                    continue
                if abs(res["realized_r"]) > max_abs_r:
                    key = (e["symbol"], pd.Timestamp(e["signal_time"]).date().isoformat())
                    prev = suspect_map.get(key, 0.0)
                    if abs(res["realized_r"]) > abs(prev):
                        suspect_map[key] = round(float(res["realized_r"]), 2)
                    continue
                res.update({"symbol": e["symbol"], "setup": e["setup"],
                            "direction": "long" if e["is_long"] else "short",
                            "signal_time": e["signal_time"],
                            "sector": SECTOR_MAP.get(e["symbol"].upper(), "UNKNOWN"),
                            "year": pd.Timestamp(e["signal_time"]).year,
                            "exit_model": variant, "filter": filt})
                rows.append(res)

            oos = _oos_rows(rows)
            m = _r_metrics(oos)
            conc = _concentration(oos)
            port = portfolio_replay(oos, rc)
            planned_r = _PLANNED_R.get(variant, float("nan"))
            label, reason = _label(m, conc, planned_r)
            combos.append({
                "exit_model": variant, "filter": filt,
                "metrics": m, "concentration": conc, "portfolio": port,
                "planned_r": planned_r, "label": label, "reason": reason,
                "trades": oos, "all_trades": rows,
            })

    # Rank the candidates that are not REJECTED by the defensive objective:
    # positive expectancy first, then low drawdown, then low worst-loss.
    def _objective(c):
        m = c["metrics"]
        if m.get("n", 0) == 0:
            return (1, 0, 0, 0)
        not_rejected = c["label"] != "REJECTED"
        return (0 if not_rejected else 1,
                -m["expectancy_r"], m["max_dd_r"], -m.get("worst_loss_r", -9))
    ranked = sorted(combos, key=_objective)
    best = next((c for c in ranked if c["metrics"].get("n", 0) > 0), None)

    suspects = sorted(((s, d, r) for (s, d), r in suspect_map.items()),
                      key=lambda x: abs(x[2]), reverse=True)
    return DefensiveResult(combos=combos, best=best,
                           n_symbols=len(frames), n_entries=len(entries),
                           suspects=suspects, max_abs_r=max_abs_r)
