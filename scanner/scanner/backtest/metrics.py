"""
Performance metrics on a list/DataFrame of trades.

Everything is expressed in R units (planned-risk multiples) so results are
comparable across symbols and price levels. Crucially this module separates:
  * planned target R (a constant input, e.g. 3.0)
  * average realized WINNER (R)
  * average realized LOSER (R)
  * net expectancy (R) after costs
so a "3R target" is never confused with the average realized winner.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .engine import Trade, trades_to_frame


def _as_frame(trades) -> pd.DataFrame:
    if isinstance(trades, pd.DataFrame):
        return trades
    return trades_to_frame(trades)


def summary(trades) -> Dict[str, float]:
    df = _as_frame(trades)
    n = len(df)
    if n == 0:
        return {"n_trades": 0}
    r = df["realized_r"].to_numpy()
    wins = r[r > 0]
    losses = r[r <= 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf

    total_pnl = float(df["pnl_dollars"].sum())
    return {
        "n_trades": int(n),
        "win_rate": float((r > 0).mean()),               # net profit > 0 after costs
        "expectancy_r": float(r.mean()),                 # mean R multiple
        "median_r": float(np.median(r)),
        "profit_factor": float(profit_factor),           # gross profit / gross loss
        "avg_winner_r": float(wins.mean()) if len(wins) else 0.0,
        "avg_loser_r": float(losses.mean()) if len(losses) else 0.0,
        "planned_target_r": float(df["planned_r_multiple"].mean()),
        "std_r": float(r.std(ddof=1)) if n > 1 else 0.0,
        "max_drawdown_r": float(max_drawdown_r(r)),
        "max_consec_losses": int(max_consecutive_losses(r)),
        "gap_tail_rate": float(df["worse_than_1r"].mean()),
        "worst_loss_r": float(r.min()),
        "pct_target_exits": float((df["exit_reason"] == "target").mean()),
        "pct_time_exits": float((df["exit_reason"] == "time").mean()),
        "gross_profit": float(df.loc[df["realized_r"] > 0, "pnl_dollars"].sum()),
        "gross_loss": float(-df.loc[df["realized_r"] <= 0, "pnl_dollars"].sum()),
        "total_pnl": total_pnl,
        "expectancy_currency": total_pnl / n,            # avg $ profit per trade
    }


def equity_curve(trades, starting_equity: float = 100_000.0) -> np.ndarray:
    """Cumulative equity after costs, in chronological signal-time order."""
    df = _as_frame(trades)
    if df.empty:
        return np.array([starting_equity])
    ordered = df.sort_values("signal_time")["pnl_dollars"].to_numpy()
    return starting_equity + np.cumsum(ordered)


def max_drawdown_pct(trades, starting_equity: float = 100_000.0) -> float:
    """Largest peak-to-trough drawdown of the equity curve, as a fraction."""
    eq = equity_curve(trades, starting_equity)
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    return float(dd.max()) if len(dd) else 0.0


def max_drawdown_r(r: np.ndarray) -> float:
    eq = np.cumsum(r)
    peak = np.maximum.accumulate(eq)
    return float((peak - eq).max()) if len(r) else 0.0


def max_consecutive_losses(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        cur = cur + 1 if x <= 0 else 0
        best = max(best, cur)
    return best


def breakdown(trades, by: str) -> pd.DataFrame:
    """Per-group expectancy/win-rate/profit-factor/n for by in
    {regime, year, symbol, sector, direction, setup, exit_reason}."""
    df = _as_frame(trades)
    if df.empty or by not in df.columns:
        return pd.DataFrame()
    rows = []
    for key, g in df.groupby(by):
        s = summary(g)
        rows.append({by: key, "n": s["n_trades"], "win_rate": s["win_rate"],
                     "expectancy_r": s["expectancy_r"],
                     "profit_factor": s["profit_factor"]})
    return pd.DataFrame(rows).sort_values(by).reset_index(drop=True)
