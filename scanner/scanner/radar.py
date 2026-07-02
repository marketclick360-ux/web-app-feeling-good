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
        # a bar in the last 5 broke below ITS OWN prior 20-day low (comparing
        # against today's lo20_prev is impossible: the break low is inside it)
        lows = df["low"].iloc[i - 5:i].to_numpy()
        lo20s = df["lo20_prev"].iloc[i - 5:i].to_numpy()
        recent_break = bool((lows < lo20s).any())
        return recent_break and c > float(df["lo20_prev"].iloc[i]) and c > o
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


# Strategies that survived validation on BOTH universes (see RADAR_BACKTEST):
# the two breakouts are PAPER-TRACK; the RSI2 pullback passed only thinly and
# is flagged as such in the live list.
LIVE_STRATEGIES = ["breakout_20d", "breakout_55d", "pullback_rsi2_200d"]
_THIN = {"pullback_rsi2_200d"}

_EXIT_RULE = {
    "breakout_20d": ("lo10_prev", "daily close < prior 10-day low"),
    "breakout_55d": ("lo20_prev", "daily close < prior 20-day low"),
    "pullback_rsi2_200d": ("sma5", "daily close > 5-day average (sell strength)"),
}


def radar_signal(adapter, tickers: List[str], as_of=None, years: int = 3):
    """Fresh Radar signals on the most recent COMPLETED bar, for the weekly
    paper-trading list. Only the strategies that survived validation. Entry is
    the NEXT session open; each row carries the 2*ATR hard stop and the
    channel/strength exit level. Honors the SPY momentum risk-on gate."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    start = as_of - pd.Timedelta(days=int(max(years, 3) * 365.25) + 320)

    spy = adapter.get_bars("SPY", "1d", start=start, end=as_of, as_of=as_of).df
    risk_on = bool(len(spy) > 260 and
                   float(spy["close"].iloc[-1]) > float(spy["close"].iloc[-253]))

    rows = []
    data_date = None
    for tk in tickers:
        try:
            raw = adapter.get_bars(tk, "1d", start=start, end=as_of, as_of=as_of).df
        except Exception:
            continue
        if len(raw) < 300:
            continue
        df = _prep(raw)
        if len(df) < 60:
            continue
        i = len(df) - 1
        data_date = max(data_date, df.index[i]) if data_date is not None else df.index[i]
        for strat in LIVE_STRATEGIES:
            if not _signal(df, i, strat):
                continue
            close = float(df["close"].iloc[i])
            atr = float(df["atr14"].iloc[i])
            exit_col, exit_txt = _EXIT_RULE[strat]
            rows.append({
                "ticker": tk, "strategy": strat,
                "thin": strat in _THIN,
                "date": str(df.index[i].date()),
                "close": round(close, 2),
                "entry_next_open": round(close, 2),      # proxy until the bar exists
                "stop_2atr": round(close - 2.0 * atr, 2),
                "risk_pct": round(2.0 * atr / close * 100.0, 1),
                "exit_level": round(float(df[exit_col].iloc[i]), 2),
                "exit_rule": exit_txt,
                "atr": round(atr, 2),
                "volume_m": round(float(df["volume"].iloc[i]) / 1e6, 1),
            })
    return {"risk_on": risk_on, "rows": rows,
            "data_date": str(data_date.date()) if data_date is not None else "?"}


def key_levels(adapter, tickers: List[str], as_of=None, years: int = 2):
    """Per-ticker movement profile + the levels that matter RIGHT NOW:
    how many $ it typically moves per day (ATR) and per week (median 5-bar
    move), the 20d/55d highs (buy triggers), the 10d/20d lows (exits), the
    2*ATR stop distance, and the 200-day trend line. Computed on completed
    bars only."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    start = as_of - pd.Timedelta(days=int(max(years, 2) * 365.25) + 320)
    out = []
    for tk in tickers:
        try:
            raw = adapter.get_bars(tk, "1d", start=start, end=as_of, as_of=as_of).df
        except Exception:
            continue
        if len(raw) < 300:
            continue
        df = _prep(raw)
        if len(df) < 60:
            continue
        last = df.iloc[-1]
        close = float(last["close"])
        atr = float(last["atr14"])
        # typical 5-day move: median absolute close-to-close change over ~1y
        c = df["close"].tail(260)
        week_move = float((c.diff(5).abs().dropna()).median())
        hi20, hi55 = float(last["hi20_prev"]), float(last["hi55_prev"])
        lo10, lo20 = float(last["lo10_prev"]), float(last["lo20_prev"])
        sma200 = float(last["sma200"])
        out.append({
            "ticker": tk, "date": str(df.index[-1].date()),
            "close": round(close, 2),
            "day_move_$": round(atr, 2),
            "day_move_pct": round(atr / close * 100, 1),
            "week_move_$": round(week_move, 2),
            "buy_trigger_20d": round(hi20, 2),
            "dist_20d_pct": round((hi20 - close) / close * 100, 1),
            "buy_trigger_55d": round(hi55, 2),
            "dist_55d_pct": round((hi55 - close) / close * 100, 1),
            "exit_10d_low": round(lo10, 2),
            "exit_20d_low": round(lo20, 2),
            "stop_2atr_$": round(2 * atr, 2),
            "sma200": round(sma200, 2),
            "trend_up": bool(close > sma200),
        })
    # closest to triggering first
    out.sort(key=lambda r: r["dist_20d_pct"])
    return out


def ticker_profile(adapter, tickers: List[str], as_of=None, years: int = 10,
                   benchmark: str = "SPY"):
    """Deep personality profile per ticker, from price/volume history only:
    momentum-vs-chop (next-day follow-through), volatility mood (current ATR%
    vs its own past year), coiled-spring meter (range-compression percentile),
    beta/correlation to SPY, relative strength vs SPY (3/6/12mo), typical
    pullback depth inside uptrends, max drawdown + recovery time, and position
    in the 52-week range. Descriptive history — not a forecast."""
    as_of = as_of or pd.Timestamp.now("UTC").normalize()
    start = as_of - pd.Timedelta(days=int(years * 365.25) + 320)

    spy_raw = adapter.get_bars(benchmark, "1d", start=start, end=as_of,
                               as_of=as_of).df
    spy_close = spy_raw["close"] if len(spy_raw) else None

    out = []
    for tk in tickers:
        try:
            raw = adapter.get_bars(tk, "1d", start=start, end=as_of, as_of=as_of).df
        except Exception:
            continue
        if len(raw) < 300:
            continue
        df = ind.enrich_daily(raw).dropna(subset=["sma200", "atr14"])
        if len(df) < 260:
            continue
        close = df["close"]
        r = close.pct_change()

        # 1) momentum vs mean-reversion: does an up day follow through?
        up = (r > 0)
        follow = float((up & up.shift(1)).sum() / max(up.shift(1).sum(), 1))
        base = float(up.mean())
        edge = (follow - base) * 100.0
        momo = "MOMO" if edge > 0.5 else ("CHOP" if edge < -0.5 else "NEUTRAL")

        # 2) volatility mood: today's ATR% vs its own trailing year
        atr_pct = (df["atr14"] / close * 100.0)
        window = atr_pct.tail(252)
        vol_pctile = float((window < window.iloc[-1]).mean() * 100.0)
        mood = "SLEEPY" if vol_pctile < 30 else ("WILD" if vol_pctile > 70 else "NORMAL")

        # 3) coiled spring: 20d Bollinger bandwidth percentile (low = tight coil)
        coil = float(df["bb_bw_pctile"].iloc[-1]) if "bb_bw_pctile" in df else float("nan")
        coiled = bool(coil == coil and coil <= 20)

        # 4) beta / correlation to SPY (1 year of daily returns)
        beta = corr = float("nan")
        if spy_close is not None:
            sr = spy_close.reindex(close.index).ffill().pct_change()
            pair = pd.DataFrame({"t": r, "s": sr}).dropna().tail(252)
            if len(pair) > 60 and float(pair["s"].var()) > 0:
                corr = float(pair["t"].corr(pair["s"]))
                beta = float(pair["t"].cov(pair["s"]) / pair["s"].var())

        # 5) relative strength vs SPY over 3/6/12 months (percentage points)
        rs = []
        if spy_close is not None:
            sc = spy_close.reindex(close.index).ffill()
            for n in (63, 126, 252):
                if len(close) > n and len(sc) > n:
                    rs.append(((close.iloc[-1] / close.iloc[-1 - n]) -
                               (sc.iloc[-1] / sc.iloc[-1 - n])) * 100.0)
        rs_avg = float(np.mean(rs)) if rs else float("nan")

        # 6) typical pullback inside uptrends (close > 200d): median depth of
        #    >=2% dips from the running high within each above-200d regime
        depths = []
        peak, in_up, trough = None, False, None
        for c, s in zip(close.to_numpy(), df["sma200"].to_numpy()):
            if c > s:
                if not in_up:
                    in_up, peak, trough = True, c, c
                peak = max(peak, c)
                trough = min(trough, c) if c < peak else c
                dd = (c - peak) / peak * 100.0
                if dd <= -2.0:
                    depths.append(dd)
            else:
                in_up = False
        typ_pullback = float(np.percentile(depths, 50)) if depths else 0.0

        # 7) max drawdown + recovery time (full window)
        cv = close.to_numpy()
        peaks = np.maximum.accumulate(cv)
        dd = cv / peaks - 1.0
        i_tr = int(dd.argmin())
        max_dd = float(dd[i_tr] * 100.0)
        peak_val = float(peaks[i_tr])
        rec = None
        for j in range(i_tr + 1, len(cv)):
            if cv[j] >= peak_val:
                rec = j - i_tr
                break

        # 8) position in the 52-week range
        yr = close.tail(252)
        lo, hi = float(yr.min()), float(yr.max())
        pos52 = float((close.iloc[-1] - lo) / (hi - lo) * 100.0) if hi > lo else 50.0

        out.append({
            "ticker": tk, "date": str(df.index[-1].date()),
            "followthrough_pct": round(follow * 100, 1),
            "momo_edge_pp": round(edge, 1), "personality": momo,
            "vol_pctile": round(vol_pctile, 0), "vol_mood": mood,
            "coil_pctile": round(coil, 0) if coil == coil else "",
            "coiled": coiled,
            "beta": round(beta, 2) if beta == beta else "",
            "corr_spy": round(corr, 2) if corr == corr else "",
            "rs_avg_pp": round(rs_avg, 1) if rs_avg == rs_avg else "",
            "leader": bool(rs_avg == rs_avg and rs_avg > 0),
            "typical_pullback_pct": round(typ_pullback, 1),
            "max_dd_pct": round(max_dd, 1),
            "recovery_days": rec if rec is not None else "not yet",
            "pos_52w_pct": round(pos52, 0),
        })
    out.sort(key=lambda x: -(x["rs_avg_pp"] if isinstance(x["rs_avg_pp"], float) else -999))
    return out


def breakout_report_card(trades_csv_path: str):
    """Per-ticker report card of the VALIDATED breakout strategies, computed
    from the committed backtest spreadsheet: n trades, win rate, avg %, total
    per $1k position, best trade. Ranks which names have actually followed
    through on breakouts for 15 years."""
    df = pd.read_csv(trades_csv_path)
    bo = df[df["strategy"].isin(["breakout_20d", "breakout_55d"])]
    rows = []
    for tk, g in bo.groupby("ticker"):
        r = g["ret_pct"]
        rows.append({
            "ticker": tk, "n": int(len(g)),
            "win_rate": round(float((r > 0).mean() * 100), 0),
            "avg_pct": round(float(r.mean()), 2),
            "total_per_$1k": round(float(r.sum() * 10), 0),
            "best_pct": round(float(r.max()), 1),
            "worst_pct": round(float(r.min()), 1),
        })
    rows.sort(key=lambda x: -x["total_per_$1k"])
    return rows


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
