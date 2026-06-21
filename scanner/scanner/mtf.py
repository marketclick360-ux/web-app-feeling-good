"""
Single-ticker, multi-timeframe TREND-ALIGNMENT model.

This is a deliberate pivot away from "one scanner for the whole market." It
backtests ONE instrument (e.g. SPY) the way the user actually traded
profitably: only be in the market when several timeframes agree, and step
aside (to cash) the moment they stop agreeing. It is long/flat — never short,
never leveraged, never holding something that can gap you to zero overnight
(the gold blow-up). The whole point is a SMOOTHER ride: keep most of the
upside while cutting the deep drawdowns of buy-and-hold.

"Three timeframes aligned" is approximated from daily bars with three trend
horizons:
  * short  : close > 20-day EMA
  * medium : close > 50-day SMA
  * long   : close > 200-day SMA
Aligned-long = all three true. We go long at the NEXT open after alignment
turns on, and exit to cash at the next open after it turns off. An optional
wide ATR catastrophe-stop models a real overnight gap as the ACTUAL loss.

Honesty rules: signals act on completed bars only, fills are next-open and
cost-adjusted (slippage+spread), gap-through-stop is recorded at the gap (not a
tidy stop price), and every result is compared head-to-head with simply buying
and holding the same ticker. Nothing here is a live-trading green light.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from . import indicators as ind
from .costs import CostModel, DEFAULT_COSTS


def _support_zones(df, window: int = 5, tol_pct: float = 2.0,
                   lookback=None):
    """Pivot-low support zones over the available history (or the last
    `lookback` bars). A pivot low is a bar whose low is the lowest in a +/-
    `window` neighbourhood; nearby pivots (within `tol_pct`) are clustered into
    one zone. For each zone we keep the touch count AND the dates of the first
    and last touch, so we can tell a fresh dip from a floor that has held for
    YEARS or decades. Returns a list of dicts:
    {level, touches, first, last}."""
    sub = df if lookback is None else df.tail(lookback)
    lows = sub["low"].to_numpy()
    idx = sub.index
    n = len(lows)
    pivots = [(float(lows[i]), idx[i]) for i in range(window, n - window)
              if lows[i] == lows[i - window:i + window + 1].min()]
    zones = []
    for p, ts in sorted(pivots, key=lambda x: x[0]):
        for z in zones:
            if abs(p - z["level"]) / z["level"] <= tol_pct / 100.0:
                z["prices"].append(p)
                z["times"].append(ts)
                z["level"] = sum(z["prices"]) / len(z["prices"])
                break
        else:
            zones.append({"level": p, "prices": [p], "times": [ts]})
    out = []
    for z in zones:
        ts = sorted(z["times"])
        out.append({"level": round(z["level"], 2), "touches": len(z["prices"]),
                    "first": ts[0], "last": ts[-1]})
    return out


def _nearest_support(df, price, near_pct: float = 3.0, min_touches: int = 2,
                     lookback=None):
    """Nearest support at/below `price` over full history, with how STRONG and
    how OLD it is. Returns a dict or None:
    {level, touches, dist_pct, near_strong, span_years, years_since_last}.
    span_years = first-to-last touch (how long the floor has held);
    years_since_last = how long since price last visited it before now."""
    zones = _support_zones(df, lookback=lookback)
    below = [z for z in zones if z["level"] <= price * 1.005]
    if not below or price <= 0:
        return None
    z = max(below, key=lambda z: z["level"])
    dist = (price - z["level"]) / price * 100.0
    last_bar = df.index[-1]
    span_years = (z["last"] - z["first"]).days / 365.25
    years_since_last = (last_bar - z["last"]).days / 365.25
    near_strong = bool(0 <= dist <= near_pct and z["touches"] >= min_touches)
    return {"level": z["level"], "touches": z["touches"],
            "dist_pct": round(dist, 1), "near_strong": near_strong,
            "span_years": round(span_years, 1),
            "years_since_last": round(years_since_last, 1)}


def mtf_signal(adapter, ticker: str, as_of: Optional[pd.Timestamp] = None,
               years: int = 2):
    """Today's status for one ticker under the patient multi-timeframe rule, for
    a weekly paper-trading watchlist. Returns a dict or None (no data).

    status:
      BUY        -> alignment just turned ON (enter next open) — a fresh trigger
      IN_UPTREND -> all three timeframes aligned (hold if you're in)
      HOLD_200   -> above the 200-day but not fully aligned (trend not broken)
      FLAT       -> below the 200-day; stand aside

    A signal is STRONG when the trend is up (above the 200-day) AND price is
    pulling back to a multi-touch support zone — a low-risk entry near a floor.
    It is DEEP (the strongest kind) when that floor has held for YEARS: many
    touches spread over a long span. We pull the FULL available history so a
    decades-old floor can be recognised.
    """
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    # pull deep history (up to ~25y) so support that has held for years/decades
    # is visible — yfinance returns whatever exists for younger tickers
    start = as_of - pd.Timedelta(days=int(max(years, 25) * 365.25) + 320)
    raw = adapter.get_bars(ticker, "1d", start=start, end=as_of, as_of=as_of).df
    if len(raw) < 220:
        return None
    df = ind.enrich_daily(raw).dropna(subset=["ema20", "sma50", "sma200"])
    if len(df) < 2:
        return None
    last, prev = df.iloc[-1], df.iloc[-2]

    def _aligned(row):
        return bool(row["close"] > row["ema20"] and row["close"] > row["sma50"]
                    and row["close"] > row["sma200"])
    aligned_now, aligned_prev = _aligned(last), _aligned(prev)
    above200 = bool(last["close"] > last["sma200"])
    close = float(last["close"])
    sma200 = float(last["sma200"])
    if aligned_now and not aligned_prev:
        status = "BUY"
    elif aligned_now:
        status = "IN_UPTREND"
    elif above200:
        status = "HOLD_200"
    else:
        status = "FLAT"
    dist_to_exit = (close - sma200) / close * 100.0 if close else float("nan")
    sup = _nearest_support(df, close)
    near_strong = bool(sup and sup["near_strong"])
    # STRONG = trend intact (above the 200-day) AND pressed against real support
    strong = bool(above200 and near_strong)
    span_years = sup["span_years"] if sup else 0.0
    touches = sup["touches"] if sup else 0
    dist_sup = sup["dist_pct"] if sup else float("nan")
    deep_floor = bool(sup and touches >= 3 and span_years >= 3.0)
    # DEEP = a STRONG setup whose floor has held for YEARS (>=3y span and >=3
    # touches) — the super-strong, long-standing support the user wants
    deep = bool(strong and deep_floor)
    # WATCH = a beaten-down name (below its 200-day, so NOT a buy yet) that is
    # parked ON a multi-year floor. Early heads-up: if it reclaims the trend
    # while holding this floor it becomes a prime DEEP buy. Allow price to sit
    # just below the floor (-2%) since these are testing it.
    watch = bool((not above200) and deep_floor
                 and dist_sup == dist_sup and -2.0 <= dist_sup <= 3.0)
    # Suggested stop: a daily CLOSE below the floor by ~1.5x ATR (a volatility
    # buffer so a normal dip doesn't shake you out). No floor near -> fall back
    # to ~2x ATR below price. risk% is entry-to-stop, what you'd lose if hit.
    atr = float(last["atr14"]) if last["atr14"] == last["atr14"] else float("nan")
    floor_ref = sup["level"] if sup else float("nan")
    if floor_ref == floor_ref and floor_ref < close and atr == atr:
        stop = floor_ref - 1.5 * atr
    elif atr == atr:
        stop = close - 2.0 * atr
    else:
        stop = float("nan")
    risk_pct = (close - stop) / close * 100.0 if (stop == stop and close) else float("nan")
    vol_shares = float(last["volume"]) if last["volume"] == last["volume"] else float("nan")
    dvol = float(last["adv20"]) if "adv20" in last and last["adv20"] == last["adv20"] \
        else float("nan")
    return {
        "ticker": ticker, "status": status, "strong": strong, "deep": deep,
        "watch": watch,
        "date": str(df.index[-1].date()),
        "close": round(close, 2),
        "entry_next_open": round(close, 2),   # proxy until the bar exists
        "exit_below": round(sma200, 2),       # exit when daily close < 200-day
        "dist_to_exit_pct": round(dist_to_exit, 1),
        "suggested_stop": round(stop, 2) if stop == stop else "",
        "risk_pct": round(risk_pct, 1) if risk_pct == risk_pct else "",
        "atr": round(atr, 2) if atr == atr else "",
        "volume_m": round(vol_shares / 1e6, 1) if vol_shares == vol_shares else "",
        "dollar_vol_m": round(dvol / 1e6, 0) if dvol == dvol else "",
        "support": sup["level"] if sup else "",
        "support_touches": sup["touches"] if sup else 0,
        "support_span_years": span_years,
        "support_years_since_last": sup["years_since_last"] if sup else "",
        "dist_to_support_pct": sup["dist_pct"] if sup else "",
        "ema20": round(float(last["ema20"]), 2),
        "sma50": round(float(last["sma50"]), 2),
        "sma200": round(sma200, 2),
    }


def support_history(adapter, ticker: str, as_of=None, years: int = 25,
                    forward: int = 60, min_touches: int = 3,
                    min_span_years: float = 3.0, window: int = 5,
                    tol_pct: float = 2.0):
    """How a ticker has historically behaved at its strongest multi-year floor.
    Finds the anchor floor (a support zone touched >= min_touches over >=
    min_span_years), then for every touch measures the forward `forward`-bar
    behavior: how far it bounced, how long to the peak, the dip first, and
    whether volume was above normal. Returns a stats dict (or None / has_floor
    False). Descriptive history, NOT a prediction — samples are small."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    start = as_of - pd.Timedelta(days=int(years * 365.25) + 320)
    raw = adapter.get_bars(ticker, "1d", start=start, end=as_of, as_of=as_of).df
    if len(raw) < 300:
        return None
    df = ind.enrich_daily(raw)
    # drop warmup / any trailing rows with missing indicators so the latest-bar
    # ATR / liquidity readings are valid (this is what caused the "nan" rows)
    df = df.dropna(subset=["close", "atr14", "adv20"])
    if len(df) < 300:
        return None
    close = df["close"]
    price = float(close.iloc[-1])
    lows = df["low"].to_numpy()
    vol = df["volume"].to_numpy()
    idx = df.index
    n = len(df)
    atr_pct = (float(df["atr14"].iloc[-1]) / price * 100.0) if price else float("nan")
    adv_dollar = float(df["adv20"].iloc[-1])

    pivots = [(float(lows[i]), i) for i in range(window, n - window)
              if lows[i] == lows[i - window:i + window + 1].min()]
    zones = []
    for p, i in sorted(pivots, key=lambda x: x[0]):
        for z in zones:
            if abs(p - z["level"]) / z["level"] <= tol_pct / 100.0:
                z["idx"].append(i)
                z["level"] = sum(float(lows[j]) for j in z["idx"]) / len(z["idx"])
                break
        else:
            zones.append({"level": p, "idx": [i]})

    def _span(z):
        ts = [idx[j] for j in z["idx"]]
        return (max(ts) - min(ts)).days / 365.25
    strong = [z for z in zones
              if len(z["idx"]) >= min_touches and _span(z) >= min_span_years]
    base = {"ticker": ticker, "has_floor": False, "price": round(price, 2),
            "atr_pct": round(atr_pct, 1),
            "adv_dollar_m": round(adv_dollar / 1e6, 0) if adv_dollar == adv_dollar else None}
    if not strong:
        return base

    # Only anchor to a floor price could realistically be trading against right
    # now: within ~25% below to ~5% above today's price. This ignores ancient,
    # dividend-adjusted lows (e.g. a bond ETF's $38 print from 20 years ago)
    # that price is nowhere near. If nothing qualifies, there is no nearby floor.
    cand = [z for z in strong if price * 0.75 <= z["level"] <= price * 1.05]
    if not cand:
        base["nearest_floor_pct"] = round(
            min((price - z["level"]) / price * 100.0 for z in strong), 1)
        return base
    anchor = min(cand, key=lambda z: abs(z["level"] - price))
    level = anchor["level"]

    ev = []
    for i in sorted(anchor["idx"]):
        if i + forward >= n or i < 20:
            continue
        entry = float(close.iloc[i])
        win = df.iloc[i + 1:i + 1 + forward]
        highs = win["high"].to_numpy()
        max_gain = (float(highs.max()) - entry) / entry * 100.0
        max_dd = (float(win["low"].min()) - entry) / entry * 100.0
        days_to_peak = int(highs.argmax()) + 1
        base_vol = vol[i - 20:i].mean()
        vol_ratio = float(vol[i] / base_vol) if base_vol > 0 else float("nan")
        ev.append({"date": idx[i].date().isoformat(), "max_gain": max_gain,
                   "max_dd": max_dd, "days_to_peak": days_to_peak,
                   "vol_ratio": vol_ratio})
    if not ev:
        return base

    g = np.array([e["max_gain"] for e in ev])
    d = np.array([e["days_to_peak"] for e in ev])
    dd = np.array([e["max_dd"] for e in ev])
    vr = np.array([e["vol_ratio"] for e in ev if e["vol_ratio"] == e["vol_ratio"]])
    base.update({
        "has_floor": True, "floor": round(level, 2),
        "touches": len(anchor["idx"]), "span_years": round(_span(anchor), 1),
        "n_events": len(ev),
        "median_gain": round(float(np.median(g)), 1),
        "best_gain": round(float(g.max()), 1),
        "worst_gain": round(float(g.min()), 1),
        "median_days_to_peak": int(np.median(d)),
        "median_dip": round(float(np.median(dd)), 1),
        "pct_bounced_5": round(float((g >= 5).mean()) * 100.0, 0),
        "pct_broke_8": round(float((dd <= -8).mean()) * 100.0, 0),
        "median_vol_ratio": round(float(np.median(vr)), 1) if len(vr) else None,
        "dist_to_floor_pct": round((price - level) / price * 100.0, 1),
        "events": ev,
    })
    return base


def volume_study(adapter, ticker: str, as_of=None, years: int = 12):
    """How much volume it takes to move a ticker. Buckets every day by relative
    volume (that day's volume / its 20-day average) and reports the typical
    absolute daily move in each bucket, the 'needle-mover' volume level (where
    the move clearly jumps), the volume that big up-days happen on, and whether
    breakouts follow through more on heavy volume. Descriptive history."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    start = as_of - pd.Timedelta(days=int(years * 365.25) + 60)
    raw = adapter.get_bars(ticker, "1d", start=start, end=as_of, as_of=as_of).df
    if len(raw) < 300:
        return None
    df = ind.enrich_daily(raw).dropna(subset=["close", "volume", "atr14", "vol_sma20"])
    if len(df) < 250:
        return None
    close = df["close"]
    relvol = (df["volume"] / df["vol_sma20"]).to_numpy()
    ret = close.pct_change().to_numpy() * 100.0
    aret = np.abs(ret)
    atrp = (df["atr14"] / close * 100.0).to_numpy()
    valid = ~np.isnan(ret)

    edges = [0.0, 0.7, 1.0, 1.5, 2.0, 3.0, np.inf]
    labels = ["<0.7x", "0.7-1x", "1-1.5x", "1.5-2x", "2-3x", ">3x"]
    buckets = []
    for lo, hi, lab in zip(edges[:-1], edges[1:], labels):
        m = valid & (relvol >= lo) & (relvol < hi)
        if m.sum() >= 10:
            buckets.append({"bucket": lab, "n": int(m.sum()),
                            "median_move": round(float(np.median(aret[m])), 2),
                            "median_signed": round(float(np.median(ret[m])), 2)})
    low = valid & (relvol < 1.0)
    base_move = float(np.median(aret[low])) if low.sum() else float("nan")
    needle = None
    for b in buckets:
        if base_move == base_move and b["median_move"] >= 1.5 * base_move:
            needle = b
            break
    big_up = valid & (ret > atrp)               # up more than ~1 ATR
    med_relvol_bigup = (round(float(np.median(relvol[big_up])), 1)
                        if big_up.sum() >= 10 else None)

    hi20 = close.rolling(20).max().shift(1).to_numpy()
    fwd = np.full(len(close), np.nan)
    cv = close.to_numpy()
    fwd[:-10] = cv[10:] / cv[:-10] - 1.0
    bo = valid & (cv > hi20) & ~np.isnan(fwd)

    def _bo(mask):
        if mask.sum() < 5:
            return None
        return {"n": int(mask.sum()),
                "pct_pos": round(float((fwd[mask] > 0).mean() * 100.0), 0),
                "median_fwd": round(float(np.median(fwd[mask])) * 100.0, 1)}
    return {"ticker": ticker, "base_move": round(base_move, 2),
            "buckets": buckets, "needle": needle,
            "med_relvol_bigup": med_relvol_bigup,
            "breakout_heavy": _bo(bo & (relvol >= 1.5)),
            "breakout_light": _bo(bo & (relvol < 1.5))}


@dataclass
class RoundTrip:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    days_held: int
    return_pct: float
    exit_reason: str   # trend_break | atr_stop | gap_stop | still_open


@dataclass
class MTFResult:
    ticker: str
    years: float
    n_bars: int
    # strategy
    strat_total_return: float
    strat_cagr: float
    strat_max_dd: float
    strat_vol: float
    strat_sharpe: float
    pct_time_invested: float
    n_trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    worst_trade_pct: float
    worst_hold_gap_pct: float
    # buy & hold
    bh_total_return: float
    bh_cagr: float
    bh_max_dd: float
    bh_vol: float
    bh_sharpe: float
    trips: list = field(default_factory=list)


def _max_dd(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    return float(((peak - equity) / peak).max())


def _ann_stats(equity: np.ndarray):
    """Annualized volatility and Sharpe (rf=0) from a daily equity curve."""
    if len(equity) < 3:
        return 0.0, 0.0
    rets = np.diff(equity) / equity[:-1]
    vol = float(np.std(rets, ddof=1) * np.sqrt(252))
    mean_ann = float(np.mean(rets) * 252)
    sharpe = mean_ann / vol if vol > 0 else 0.0
    return vol, sharpe


def run_mtf(adapter, ticker: str, years: int = 12,
            as_of: Optional[pd.Timestamp] = None,
            cost: Optional[CostModel] = None,
            atr_stop_mult: Optional[float] = 3.0,
            slow_exit: bool = True,
            start_equity: float = 10_000.0) -> Optional[MTFResult]:
    """Backtest the long/flat multi-timeframe model on a single ticker and
    compare it to buy-and-hold. `atr_stop_mult=None` disables the catastrophe
    stop (pure trend-break exits).

    Exit asymmetry (the anti-whipsaw fix):
      * slow_exit=True  (default): ENTER only when all three timeframes align,
        but EXIT only when the LONG-term trend breaks (close < 200-SMA). You
        ride through normal pullbacks instead of getting chopped out on them.
      * slow_exit=False: exit the moment alignment breaks (twitchy; whipsaws)."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    cost = cost or DEFAULT_COSTS
    start = as_of - pd.Timedelta(days=int(years * 365.25) + 300)
    raw = adapter.get_bars(ticker, "1d", start=start, end=as_of, as_of=as_of).df
    if len(raw) < 260:
        return None
    df = ind.enrich_daily(raw)
    df = df.dropna(subset=["ema20", "sma50", "sma200", "atr14"])
    if len(df) < 60:
        return None

    close = df["close"].to_numpy()
    openp = df["open"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    atr = df["atr14"].to_numpy()
    aligned = ((df["close"] > df["ema20"]) & (df["close"] > df["sma50"])
               & (df["close"] > df["sma200"])).to_numpy()
    # the slow regime: stay long until the long-term trend itself breaks
    regime_ok = (df["close"] > df["sma200"]).to_numpy()
    dates = df.index

    n = len(df)
    pos = 0
    shares = 0.0
    cash = start_equity
    entry_price = 0.0
    entry_i = 0
    stop_level = -np.inf
    equity_curve = np.empty(n)
    trips: List[RoundTrip] = []
    worst_hold_gap = 0.0
    invested_days = 0

    for i in range(1, n):
        # decided on the PRIOR completed bar (no look-ahead)
        entry_ok = bool(aligned[i - 1])                 # strict: all timeframes agree
        stay_ok = bool(regime_ok[i - 1]) if slow_exit else entry_ok  # patient exit

        # --- catastrophe / gap protection while holding ---
        if pos == 1 and atr_stop_mult is not None:
            o = openp[i]
            if o <= stop_level:            # gapped through the stop overnight
                exit_fill = cost.effective_exit(o, True)
                gap = (o - close[i - 1]) / close[i - 1]
                worst_hold_gap = min(worst_hold_gap, gap)
                cash = shares * exit_fill
                trips.append(RoundTrip(
                    str(dates[entry_i].date()), str(dates[i].date()),
                    entry_price, exit_fill, i - entry_i,
                    (exit_fill / entry_price - 1.0) * 100.0, "gap_stop"))
                pos, shares = 0, 0.0
            elif low[i] <= stop_level:     # intrabar stop touch
                exit_fill = cost.effective_exit(stop_level, True)
                cash = shares * exit_fill
                trips.append(RoundTrip(
                    str(dates[entry_i].date()), str(dates[i].date()),
                    entry_price, exit_fill, i - entry_i,
                    (exit_fill / entry_price - 1.0) * 100.0, "atr_stop"))
                pos, shares = 0, 0.0

        # --- trend-driven entries/exits at this bar's open ---
        if pos == 0 and entry_ok:
            entry_price = cost.effective_entry(openp[i], True)
            shares = cash / entry_price
            entry_i = i
            stop_level = (openp[i] - atr_stop_mult * atr[i]) \
                if atr_stop_mult is not None else -np.inf
            pos = 1
        elif pos == 1 and not stay_ok:
            exit_fill = cost.effective_exit(openp[i], True)
            cash = shares * exit_fill
            trips.append(RoundTrip(
                str(dates[entry_i].date()), str(dates[i].date()),
                entry_price, exit_fill, i - entry_i,
                (exit_fill / entry_price - 1.0) * 100.0, "trend_break"))
            pos, shares = 0, 0.0
        elif pos == 1:
            # raise the trailing catastrophe-stop as price advances (never lower)
            if atr_stop_mult is not None:
                stop_level = max(stop_level, close[i] - atr_stop_mult * atr[i])

        equity_curve[i] = shares * close[i] if pos == 1 else cash
        invested_days += pos
        if pos == 1 and i > entry_i:
            gap = (openp[i] - close[i - 1]) / close[i - 1]
            worst_hold_gap = min(worst_hold_gap, gap)
    equity_curve[0] = start_equity

    # close any still-open position at the last close (mark-out)
    if pos == 1:
        exit_fill = cost.effective_exit(close[-1], True)
        cash = shares * exit_fill
        trips.append(RoundTrip(str(dates[entry_i].date()), str(dates[-1].date()),
                               entry_price, exit_fill, n - 1 - entry_i,
                               (exit_fill / entry_price - 1.0) * 100.0, "still_open"))

    # buy & hold on the same window
    bh_entry = cost.effective_entry(openp[1], True)
    bh_shares = start_equity / bh_entry
    bh_curve = bh_shares * close
    bh_curve[0] = start_equity

    yrs = n / 252.0
    strat_tr = cash / start_equity - 1.0
    bh_tr = bh_curve[-1] / start_equity - 1.0
    s_vol, s_sharpe = _ann_stats(equity_curve)
    b_vol, b_sharpe = _ann_stats(bh_curve)
    wins = [t for t in trips if t.return_pct > 0]
    losses = [t for t in trips if t.return_pct <= 0]

    return MTFResult(
        ticker=ticker, years=yrs, n_bars=n,
        strat_total_return=strat_tr * 100.0,
        strat_cagr=((cash / start_equity) ** (1 / yrs) - 1.0) * 100.0 if yrs > 0 else 0.0,
        strat_max_dd=_max_dd(equity_curve) * 100.0,
        strat_vol=s_vol * 100.0, strat_sharpe=s_sharpe,
        pct_time_invested=float(invested_days / max(n - 1, 1) * 100.0),
        n_trades=len(trips),
        win_rate=(len(wins) / len(trips) * 100.0) if trips else 0.0,
        avg_win_pct=float(np.mean([t.return_pct for t in wins])) if wins else 0.0,
        avg_loss_pct=float(np.mean([t.return_pct for t in losses])) if losses else 0.0,
        worst_trade_pct=float(min([t.return_pct for t in trips])) if trips else 0.0,
        worst_hold_gap_pct=worst_hold_gap * 100.0,
        bh_total_return=bh_tr * 100.0,
        bh_cagr=((bh_curve[-1] / start_equity) ** (1 / yrs) - 1.0) * 100.0 if yrs > 0 else 0.0,
        bh_max_dd=_max_dd(bh_curve) * 100.0,
        bh_vol=b_vol * 100.0, bh_sharpe=b_sharpe,
        trips=trips)
