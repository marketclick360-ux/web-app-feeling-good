"""
Tactical Signal Radar — honest backtest of the user's five entry strategies,
each with its CANONICAL published exit (not a forced 3R target, which we
already proved kills them):

  pullback_rsi2_200d   : close>SMA200, close<SMA20, RSI(2)<=10.
                         Exit: close > SMA5 (Connors-style), 10-bar time stop.
  sma50_bullish_bounce : close>SMA200, low touches SMA50, closes back above it,
                         green candle. Exit: close < SMA50 (thesis broken),
                         15-bar time stop.
  breakout_20d         : close>SMA200 and close > prior 20-day high.
                         Exit: close < prior 10-day low (Donchian 20/10).
  breakout_55d         : close>SMA200 and close > prior 55-day high.
                         Exit: close < prior 20-day low (Turtle 55/20).
  oversold_reclaim_20d : close>SMA200, dipped below the prior 20-day low within
                         the last 5 bars, now closes back above it, green.
                         Exit: close > SMA5, 10-bar time stop.

All entries fill at the NEXT session open (no look-ahead). Every trade also
carries a 2*ATR hard stop from entry (the Radar's own risk plan), with
gap-through handling (fill at the open when it gaps past the stop). Costs are
0.10% per side. Optional SPY absolute-momentum filter (SPY close > its close
252 bars earlier, on completed bars) — the Radar's risk-on gate.

Output is trade-level truth: expectancy after costs, win rate, profit factor,
OOS split (most recent 40% of trades), best-ticker concentration, hold time,
and trade FREQUENCY (signals/week across the universe). Labels follow the
project's honesty rules: REJECTED / STATISTICALLY INCONCLUSIVE / TENTATIVE /
PAPER-TRACK ONLY. Nothing here is a live-trading green light.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from . import indicators as ind

COST_PER_SIDE = 0.001  # 0.10%

STRATEGIES = ["pullback_rsi2_200d", "sma50_bullish_bounce", "breakout_20d",
              "breakout_55d", "oversold_reclaim_20d"]

# family -> (strength-exit, time-stop bars)
_MR = {"pullback_rsi2_200d", "oversold_reclaim_20d"}


@dataclass
class RadarTrade:
    ticker: str
    strategy: str
    entry_date: str
    exit_date: str
    entry: float
    exit: float
    ret_pct: float          # net of costs
    bars_held: int
    exit_reason: str        # strength | thesis | channel | time | stop | gap_stop
    year: int


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    ru = up.ewm(alpha=1.0 / period, adjust=False).mean()
    rd = down.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = ru / rd.replace(0.0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi = rsi.where(rd > 0, np.where(ru > 0, 100.0, 50.0))  # no down-moves -> 100
    return rsi.fillna(50.0)


def _prep(df: pd.DataFrame) -> pd.DataFrame:
    out = ind.enrich_daily(df)
    out["sma5"] = out["close"].rolling(5).mean()
    out["rsi2"] = _rsi(out["close"], 2)
    return out.dropna(subset=["sma200", "sma50", "sma20", "sma5", "atr14",
                              "hi20_prev", "hi55_prev", "lo10_prev", "lo20_prev"])


def _signal(df: pd.DataFrame, i: int, strategy: str) -> bool:
    c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
    if c <= float(df["sma200"].iloc[i]):
        return False
    if strategy == "pullback_rsi2_200d":
        return c < float(df["sma20"].iloc[i]) and float(df["rsi2"].iloc[i]) <= 10
    if strategy == "sma50_bullish_bounce":
        s50 = float(df["sma50"].iloc[i])
        return (float(df["low"].iloc[i]) <= s50 * 1.005 and c > s50 and c > o)
    if strategy == "breakout_20d":
        return c > float(df["hi20_prev"].iloc[i])
    if strategy == "breakout_55d":
        return c > float(df["hi55_prev"].iloc[i])
    if strategy == "oversold_reclaim_20d":
        if i < 6:
            return False
        lo20 = float(df["lo20_prev"].iloc[i])
        recent_break = float(df["low"].iloc[i - 5:i].min()) < lo20
        return recent_break and c > lo20 and c > o
    return False


def _exit_hit(df: pd.DataFrame, j: int, strategy: str, bars_held: int):
    """Exit decision on bar j (evaluated on its close). Returns reason or None."""
    c = float(df["close"].iloc[j])
    if strategy in _MR:
        if c > float(df["sma5"].iloc[j]):
            return "strength"
        if bars_held >= 10:
            return "time"
    elif strategy == "sma50_bullish_bounce":
        if c < float(df["sma50"].iloc[j]):
            return "thesis"
        if bars_held >= 15:
            return "time"
    elif strategy == "breakout_20d":
        if c < float(df["lo10_prev"].iloc[j]):
            return "channel"
        if bars_held >= 60:
            return "time"
    elif strategy == "breakout_55d":
        if c < float(df["lo20_prev"].iloc[j]):
            return "channel"
        if bars_held >= 100:
            return "time"
    return None


def _simulate(df: pd.DataFrame, ticker: str, strategy: str,
              risk_on: Optional[pd.Series]) -> List[RadarTrade]:
    trades: List[RadarTrade] = []
    n = len(df)
    i = 0
    while i < n - 1:
        if not _signal(df, i, strategy):
            i += 1
            continue
        if risk_on is not None and not bool(risk_on.get(df.index[i], False)):
            i += 1
            continue
        entry_pos = i + 1
        raw_entry = float(df["open"].iloc[entry_pos])
        entry = raw_entry * (1 + COST_PER_SIDE)
        stop = raw_entry - 2.0 * float(df["atr14"].iloc[i])
        exit_pos, exit_px, reason = None, None, None
        for j in range(entry_pos, n):
            o, lo = float(df["open"].iloc[j]), float(df["low"].iloc[j])
            if o <= stop:                       # gapped through the stop
                exit_pos, exit_px, reason = j, o, "gap_stop"
                break
            if lo <= stop:                      # intraday stop touch
                exit_pos, exit_px, reason = j, stop, "stop"
                break
            r = _exit_hit(df, j, strategy, j - entry_pos)
            if r:
                exit_pos, exit_px, reason = j, float(df["close"].iloc[j]), r
                break
        if exit_pos is None:
            break                               # still open at data end -> drop
        exit_net = exit_px * (1 - COST_PER_SIDE)
        trades.append(RadarTrade(
            ticker=ticker, strategy=strategy,
            entry_date=str(df.index[entry_pos].date()),
            exit_date=str(df.index[exit_pos].date()),
            entry=round(entry, 4), exit=round(exit_net, 4),
            ret_pct=(exit_net / entry - 1.0) * 100.0,
            bars_held=exit_pos - entry_pos, exit_reason=reason,
            year=df.index[entry_pos].year))
        i = exit_pos + 1                        # one position per ticker at a time
    return trades


def _stats(trades: List[RadarTrade]) -> dict:
    if not trades:
        return {"n": 0}
    r = np.array([t.ret_pct for t in trades])
    wins, losses = r[r > 0], r[r <= 0]
    gl = -losses.sum()
    return {"n": len(r), "win_rate": float((r > 0).mean()),
            "expectancy": float(r.mean()),
            "avg_win": float(wins.mean()) if len(wins) else 0.0,
            "avg_loss": float(losses.mean()) if len(losses) else 0.0,
            "profit_factor": float(wins.sum() / gl) if gl > 0 else float("inf"),
            "median_hold": float(np.median([t.bars_held for t in trades])),
            "worst": float(r.min())}


def _concentration(trades: List[RadarTrade]) -> dict:
    df = pd.DataFrame([t.__dict__ for t in trades])
    gross = df[df.ret_pct > 0].groupby("ticker")["ret_pct"].sum()
    if gross.empty or gross.sum() <= 0:
        return {"best": "", "share": 0.0, "exp_without": 0.0, "passes": False}
    best = gross.idxmax()
    share = float(gross.max() / gross.sum())
    rest = df[df.ticker != best]["ret_pct"]
    exp_wo = float(rest.mean()) if len(rest) else 0.0
    return {"best": str(best), "share": share, "exp_without": exp_wo,
            "passes": bool(exp_wo > 0 and share <= 0.40)}


def _label(oos: dict, conc: dict) -> tuple:
    n = oos.get("n", 0)
    if n == 0:
        return "NO SAMPLE", "no out-of-sample trades"
    if oos["expectancy"] <= 0:
        return "REJECTED", f"OOS expectancy {oos['expectancy']:+.2f}%/trade not positive"
    if oos["profit_factor"] < 1.10:
        return "REJECTED", f"OOS profit factor {oos['profit_factor']:.2f} too thin"
    if not conc["passes"]:
        return "REJECTED", (f"concentration: {conc['best']} carries "
                            f"{conc['share']:.0%}; exp without it {conc['exp_without']:+.2f}%")
    if n < 100:
        return "STATISTICALLY INCONCLUSIVE", f"only {n} OOS trades (<100)"
    if oos["profit_factor"] < 1.30:
        return "TENTATIVE", "positive but PF < 1.30 — fragile"
    return "PAPER-TRACK ONLY", "passes every gate at this sample"


def run_radar(adapter, tickers: List[str], years: int = 15, as_of=None,
              spy_filter: bool = True, strategies: Optional[List[str]] = None):
    """Backtest all Radar strategies across the universe. Returns
    {strategy: {stats, oos, concentration, label, reason, trades,
                per_week, years_covered}}."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    start = as_of - pd.Timedelta(days=int(years * 365.25) + 320)
    strategies = strategies or list(STRATEGIES)

    risk_on = None
    if spy_filter:
        spy = adapter.get_bars("SPY", "1d", start=start, end=as_of, as_of=as_of).df
        if len(spy) > 260:
            risk_on = (spy["close"] > spy["close"].shift(252)).fillna(False)

    frames = {}
    for tk in tickers:
        try:
            raw = adapter.get_bars(tk, "1d", start=start, end=as_of, as_of=as_of).df
        except Exception:
            continue
        if len(raw) < 300:
            continue
        df = _prep(raw)
        if len(df) > 260:
            frames[tk] = df
    if not frames:
        return {}

    span_days = max((df.index[-1] - df.index[0]).days for df in frames.values())
    weeks = max(span_days / 7.0, 1.0)

    out = {}
    for strat in strategies:
        all_trades: List[RadarTrade] = []
        for tk, df in frames.items():
            ro = (risk_on.reindex(df.index).ffill().fillna(False)
                  if risk_on is not None else None)
            all_trades.extend(_simulate(df, tk, strat, ro))
        all_trades.sort(key=lambda t: t.entry_date)
        cut = int(len(all_trades) * 0.6)
        oos_trades = all_trades[cut:]
        stats, oos = _stats(all_trades), _stats(oos_trades)
        conc = _concentration(oos_trades) if oos_trades else _concentration(all_trades) \
            if all_trades else {"best": "", "share": 0, "exp_without": 0, "passes": False}
        label, reason = _label(oos, conc) if all_trades else ("NO SAMPLE", "no trades")
        out[strat] = {"stats": stats, "oos": oos, "concentration": conc,
                      "label": label, "reason": reason, "trades": all_trades,
                      "per_week": len(all_trades) / weeks,
                      "years_covered": round(span_days / 365.25, 1),
                      "n_tickers": len(frames)}
    return out
