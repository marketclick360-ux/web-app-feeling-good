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
