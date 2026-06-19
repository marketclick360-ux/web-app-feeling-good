"""
Beat-SPY tester — compares low-risk, small-account-friendly strategies against
SPY buy-and-hold on real (or synthetic) data, and reports the truth side by
side: return, MAX DRAWDOWN, Sharpe, Calmar, trades/year, % time in market.

It is built around ONE honest question: can a simple rule give you roughly
SPY-like returns with much smaller crashes? Beating SPY on raw return is rare;
beating it on drawdown/risk is achievable and well documented.

Strategies (all objective, low-frequency, monthly-rebalanced, no look-ahead):
  * buy_hold_SPY      — the benchmark
  * SPY_200d_timing   — hold SPY when above its 200-day average, else CASH (T-bills)
  * SPY_abs_momentum  — hold SPY when its 200-day return is positive, else CASH
  * SPY_or_BONDS      — hold SPY when above 200-day avg, else BONDS (AGG)
  * dual_momentum     — pick the best of {SPY, BONDS} by 200-day momentum, else CASH

Realism: signals use only data through the rebalance date and act on the NEXT
day's open-equivalent (1-day lag); a cost is charged whenever the holding
changes; CASH accrues a configurable T-bill yield; SPY/BONDS accrue a
configurable dividend yield (the price data is price-return, so dividends are
added back equally for benchmark and strategy — a fair comparison).

USAGE
    python3 beat_spy.py --source schwab --years 12
    python3 beat_spy.py --source synthetic            # offline demo

This estimates HISTORICAL behavior under stated assumptions. It does NOT prove
future results. A result that beats SPY only in-sample, or only by a hair, or
only in one period, is not a real edge.
"""
from __future__ import annotations

import argparse
import os
import numpy as np
import pandas as pd

from scanner.data import get_adapter

TRADING_DAYS = 252


# ----------------------------- data -----------------------------------------
def load(adapter, symbol, years, as_of):
    start = as_of - pd.Timedelta(days=int(365.25 * years) + 60)
    df = adapter.get_bars(symbol, "1d", start=start, end=as_of, as_of=as_of).df
    return df if len(df) > 220 else None


# ------------------------- strategy signals ---------------------------------
# Each returns a daily Series of the asset to HOLD: 'EQ' | 'BOND' | 'CASH'.
# Decisions are made monthly (month-end), then held; the runner lags by 1 day.
def _month_end_ffill(daily_pos: pd.Series) -> pd.Series:
    me = daily_pos.resample("ME").last()
    return me.reindex(daily_pos.index, method="ffill")


def strat_buy_hold(eq, bond):
    return pd.Series("EQ", index=eq.index)


def strat_200d_timing(eq, bond):
    sma = eq["close"].rolling(200).mean()
    pos = pd.Series("CASH", index=eq.index)
    pos[eq["close"] > sma] = "EQ"
    return _month_end_ffill(pos)


def strat_abs_momentum(eq, bond, lookback=200):
    mom = eq["close"] / eq["close"].shift(lookback) - 1
    pos = pd.Series("CASH", index=eq.index)
    pos[mom > 0] = "EQ"
    return _month_end_ffill(pos)


def strat_spy_or_bonds(eq, bond):
    if bond is None:
        return None
    sma = eq["close"].rolling(200).mean()
    pos = pd.Series("BOND", index=eq.index)
    pos[eq["close"] > sma] = "EQ"
    return _month_end_ffill(pos)


def strat_dual_momentum(eq, bond, lookback=200):
    if bond is None:
        return None
    em = eq["close"] / eq["close"].shift(lookback) - 1
    bm = bond["close"].reindex(eq.index).ffill() / \
        bond["close"].reindex(eq.index).ffill().shift(lookback) - 1
    choose_eq = (em > 0) & (em >= bm)
    choose_bond = (~choose_eq) & (bm > 0)
    pos = np.where(choose_eq, "EQ", np.where(choose_bond, "BOND", "CASH"))
    return _month_end_ffill(pd.Series(pos, index=eq.index))


STRATEGIES = {
    "buy_hold_SPY": strat_buy_hold,
    "SPY_200d_timing": strat_200d_timing,
    "SPY_abs_momentum": strat_abs_momentum,
    "SPY_or_BONDS": strat_spy_or_bonds,
    "dual_momentum": strat_dual_momentum,
}


# ------------------------------ engine --------------------------------------
def run(pos, eq, bond, cash_yield, div_yield, bond_div_yield, cost_bps):
    """Turn a daily target-asset series into an equity curve, net of costs."""
    pos = pos.shift(1).ffill().fillna("CASH")          # act next day, no look-ahead
    eq_ret = eq["close"].pct_change().fillna(0) + div_yield / TRADING_DAYS
    if bond is not None:
        bond_ret = bond["close"].reindex(eq.index).ffill().pct_change().fillna(0) \
            + bond_div_yield / TRADING_DAYS
    else:
        bond_ret = pd.Series(0.0, index=eq.index)
    cash_ret = pd.Series(cash_yield / TRADING_DAYS, index=eq.index)

    daily = pd.Series(0.0, index=eq.index)
    daily[pos == "EQ"] = eq_ret[pos == "EQ"]
    daily[pos == "BOND"] = bond_ret[pos == "BOND"]
    daily[pos == "CASH"] = cash_ret[pos == "CASH"]

    switches = (pos != pos.shift(1)) & (pos.index != pos.index[0])
    daily[switches] -= cost_bps / 10_000.0

    equity = (1 + daily).cumprod()
    n_trades = int(switches.sum())
    pct_in_market = float((pos == "EQ").mean())
    return equity, n_trades, pct_in_market


def metrics(equity, cash_yield):
    rets = equity.pct_change().dropna()
    n = len(equity)
    yrs = max((n - 1) / TRADING_DAYS, 1e-9)
    cagr = equity.iloc[-1] ** (1 / yrs) - 1
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    dd = equity / equity.cummax() - 1
    maxdd = dd.min()
    sharpe = ((rets.mean() * TRADING_DAYS) - cash_yield) / (vol + 1e-9)
    calmar = cagr / abs(maxdd) if maxdd < 0 else float("inf")
    return {"total_return": equity.iloc[-1] - 1, "cagr": cagr, "vol": vol,
            "max_drawdown": maxdd, "sharpe": sharpe, "calmar": calmar}


def _fmt(m, n_trades, pct_in, yrs):
    return (f"{m['cagr']*100:6.2f}%  {m['max_drawdown']*100:7.2f}%  "
            f"{m['sharpe']:5.2f}  {m['calmar']:5.2f}  "
            f"{m['total_return']*100:8.1f}%  {n_trades/max(yrs,1e-9):5.1f}  "
            f"{pct_in*100:5.0f}%")


def evaluate(eq, bond, args, label, idx=None):
    e = eq if idx is None else eq.loc[idx]
    b = None if bond is None else bond.loc[bond.index.intersection(e.index)]
    yrs = max((len(e) - 1) / TRADING_DAYS, 1e-9)
    print(f"\n  {label}  ({e.index[0].date()} → {e.index[-1].date()}, {yrs:.1f}y)")
    print(f"  {'strategy':<18} {'CAGR':>7} {'MaxDD':>8} {'Sharpe':>6} "
          f"{'Calmar':>6} {'TotRet':>9} {'tr/yr':>6} {'%inMkt':>6}")
    print("  " + "-" * 74)
    rows = {}
    for name, fn in STRATEGIES.items():
        pos = fn(e, b)
        if pos is None:
            continue
        equity, n_tr, pin = run(pos, e, b, args.cash_yield, args.div_yield,
                                args.bond_div_yield, args.cost_bps)
        m = metrics(equity, args.cash_yield)
        rows[name] = m
        print(f"  {name:<18} {_fmt(m, n_tr, pin, yrs)}")
    return rows


def main():
    ap = argparse.ArgumentParser(description="Compare low-risk strategies vs SPY buy-and-hold")
    ap.add_argument("--source", default="synthetic",
                    choices=["synthetic", "csv", "polygon", "schwab", "stooq"])
    ap.add_argument("--equity", default="SPY")
    ap.add_argument("--bond", default="AGG")
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--cash-yield", type=float, default=0.04, dest="cash_yield",
                    help="annual T-bill/cash yield earned when out of the market")
    ap.add_argument("--div-yield", type=float, default=0.017, dest="div_yield",
                    help="equity dividend yield added back (price-return data)")
    ap.add_argument("--bond-div-yield", type=float, default=0.03, dest="bond_div_yield")
    ap.add_argument("--cost-bps", type=float, default=5.0, dest="cost_bps",
                    help="per-switch cost (spread+slippage+commission), bps")
    args = ap.parse_args()

    adapter = get_adapter(args.source)
    as_of = pd.Timestamp.now("UTC").normalize()
    eq = load(adapter, args.equity, args.years, as_of)
    if eq is None:
        raise SystemExit(f"No data for {args.equity} from {args.source}.")
    bond = load(adapter, args.bond, args.years, as_of)

    real = args.source in ("polygon", "csv", "schwab", "stooq")
    print("=" * 80)
    print("  BEAT-SPY TESTER — low-risk strategies vs buy-and-hold")
    print("=" * 80)
    print(f"  Source: {args.source}   Equity: {args.equity}   Bond: {args.bond}"
          f"   Cash yield: {args.cash_yield:.1%}")
    print(f"  Live data: {'YES' if real else 'NO — synthetic/offline (illustrative only)'}")
    print(f"  Assumptions: monthly rebalance, 1-day lag, {args.cost_bps:.0f}bps/switch, "
          f"div added back ({args.div_yield:.1%}); PRICE-RETURN data; "
          "NOT survivorship/dividend-exact. Estimates history, not the future.")

    full = evaluate(eq, bond, args, "FULL PERIOD")

    # in-sample / out-of-sample split (first 60% / last 40%)
    split = eq.index[int(len(eq) * 0.6)]
    evaluate(eq, bond, args, "IN-SAMPLE (first 60%)", idx=eq.index[eq.index <= split])
    oos = evaluate(eq, bond, args, "OUT-OF-SAMPLE (last 40%)",
                   idx=eq.index[eq.index > split])

    # honest verdict
    print("\n" + "=" * 80)
    print("  VERDICT (out-of-sample vs buy_hold_SPY)")
    print("=" * 80)
    base = oos.get("buy_hold_SPY")
    if base:
        for name, m in oos.items():
            if name == "buy_hold_SPY":
                continue
            ret_beat = m["cagr"] > base["cagr"]
            dd_beat = m["max_drawdown"] > base["max_drawdown"]  # less negative = smaller crash
            calmar_beat = m["calmar"] > base["calmar"]
            tag = []
            tag.append("higher return" if ret_beat else "lower return")
            tag.append("smaller drawdown" if dd_beat else "bigger drawdown")
            tag.append("better Calmar" if calmar_beat else "worse Calmar")
            print(f"  {name:<18}: " + ", ".join(tag))
    print("\n  Reminder: 'smaller drawdown with similar return' IS beating buy-and-hold")
    print("  on risk — the achievable kind. Higher raw return out-of-sample is rare;")
    print("  treat any single win skeptically until it holds across periods and costs.")


if __name__ == "__main__":
    main()
