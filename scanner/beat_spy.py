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


def strat_200d_timing(eq, bond, ma=200):
    sma = eq["close"].rolling(ma).mean()
    pos = pd.Series("CASH", index=eq.index)
    pos[eq["close"] > sma] = "EQ"
    return _month_end_ffill(pos)


def strat_200d_buffer(eq, bond, band=0.015, ma=200):
    """200-day timing with a confirmation BUFFER + hysteresis: only go to cash
    when price is band% BELOW the MA, only re-enter when band% ABOVE it; hold
    the prior state in the dead zone. This cuts the whipsaws that hurt the plain
    200-day rule in choppy markets."""
    sma = eq["close"].rolling(ma).mean()
    pos, cur = [], "CASH"
    for c, m in zip(eq["close"], sma):
        if m != m:                       # NaN warmup
            cur = "CASH"
        elif c > m * (1 + band):
            cur = "EQ"
        elif c < m * (1 - band):
            cur = "CASH"
        pos.append(cur)                  # dead zone -> keep current
    return _month_end_ffill(pd.Series(pos, index=eq.index))


def strat_abs_momentum(eq, bond, lookback=200):
    mom = eq["close"] / eq["close"].shift(lookback) - 1
    pos = pd.Series("CASH", index=eq.index)
    pos[mom > 0] = "EQ"
    return _month_end_ffill(pos)


def strat_spy_or_bonds(eq, bond, ma=200):
    if bond is None:
        return None
    sma = eq["close"].rolling(ma).mean()
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
    "SPY_200d_buffer": strat_200d_buffer,
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
    trpy = "    —" if (n_trades is None) else f"{n_trades/max(yrs,1e-9):5.1f}"
    pin = "    —" if (pct_in != pct_in) else f"{pct_in*100:4.0f}%"
    return (f"{m['cagr']*100:6.2f}%  {m['max_drawdown']*100:7.2f}%  "
            f"{m['sharpe']:5.2f}  {m['calmar']:5.2f}  "
            f"{m['total_return']*100:8.1f}%  {trpy:>5}  {pin:>5}")


SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"]


def _load_basket(adapter, syms, years, as_of):
    start = as_of - pd.Timedelta(days=int(365.25 * years) + 220)
    out = {}
    for s in syms:
        df = adapter.get_bars(s, "1d", start=start, end=as_of, as_of=as_of).df
        if len(df) > 250:
            out[s] = df["close"]
    return out


def sector_rotation_returns(basket, index, lookback=126, top_n=3,
                            cash_yield=0.04, div_yield=0.017, cost_bps=5.0):
    """Monthly relative-momentum sector rotation: each month hold the top-N
    sector ETFs by `lookback`-day return that are also positive (absolute
    filter), else cash. Equal weight. 1-day lag, turnover cost. Returns a daily
    return series aligned to `index`. Documented strategy, tested OOS like the
    rest — not curve-fit."""
    if len(basket) < top_n + 1:
        return None
    closes = pd.DataFrame({s: c.reindex(index).ffill() for s, c in basket.items()})
    asset_ret = closes.pct_change().fillna(0) + div_yield / TRADING_DAYS
    mom = closes / closes.shift(lookback) - 1
    cash_daily = cash_yield / TRADING_DAYS

    daily = pd.Series(0.0, index=index)
    holdings, prev = [], []
    cur_month = None
    for i, dt in enumerate(index):
        m = (dt.year, dt.month)
        if m != cur_month:
            cur_month = m
            row = mom.iloc[i - 1] if i > 0 else mom.iloc[i]
            ranked = row.dropna().sort_values(ascending=False)
            holdings = [s for s in ranked.index if ranked[s] > 0][:top_n]
            turnover = len(set(holdings) ^ set(prev)) / max(len(holdings) or 1, 1)
            daily.iloc[i] -= turnover * cost_bps / 10_000.0
            prev = holdings
        daily.iloc[i] += (asset_ret.iloc[i][holdings].mean() if holdings else cash_daily)
    return daily


def build_strategies(ma=200, band=0.015, mom=200):
    """Assemble the strategy set with the chosen knobs so they're tweakable
    from the command line (MA length, buffer %, momentum lookback)."""
    from functools import partial
    return {
        "buy_hold_SPY": strat_buy_hold,
        f"SPY_{ma}d_timing": partial(strat_200d_timing, ma=ma),
        f"SPY_{ma}d_buffer": partial(strat_200d_buffer, band=band, ma=ma),
        f"SPY_abs_momentum": partial(strat_abs_momentum, lookback=mom),
        f"SPY_or_BONDS": partial(strat_spy_or_bonds, ma=ma),
        "dual_momentum": partial(strat_dual_momentum, lookback=mom),
    }


def _avg_hold_days(pos):
    """Average length (in trading days) of an IN-MARKET stretch — i.e. how long
    you typically stay in a position before the rule flips you out."""
    import itertools
    vals = [v for v in pos.tolist() if isinstance(v, str)]
    runs = [(k, len(list(g))) for k, g in itertools.groupby(vals)]
    held = [n for k, n in runs if k in ("EQ", "BOND")]
    return (sum(held) / len(held)) if held else 0.0


def evaluate(eq, bond, args, label, idx=None, extra=None, strategies=None):
    e = eq if idx is None else eq.loc[idx]
    b = None if bond is None else bond.loc[bond.index.intersection(e.index)]
    yrs = max((len(e) - 1) / TRADING_DAYS, 1e-9)
    print(f"\n  {label}  ({e.index[0].date()} → {e.index[-1].date()}, {yrs:.1f}y)")
    print(f"  {'strategy':<18} {'CAGR':>7} {'MaxDD':>8} {'Sharpe':>6} "
          f"{'Calmar':>6} {'TotRet':>9} {'tr/yr':>6} {'%inMkt':>6}")
    print("  " + "-" * 74)
    rows = {}
    for name, fn in (strategies or STRATEGIES).items():
        pos = fn(e, b)
        if pos is None:
            continue
        equity, n_tr, pin = run(pos, e, b, args.cash_yield, args.div_yield,
                                args.bond_div_yield, args.cost_bps)
        m = metrics(equity, args.cash_yield)
        m["trades_per_year"] = n_tr / yrs
        m["pct_in_market"] = pin
        m["avg_hold_days"] = _avg_hold_days(pos)
        rows[name] = m
        print(f"  {name:<18} {_fmt(m, n_tr, pin, yrs)}")
    # extra strategies supplied as precomputed daily-return series (e.g. rotation)
    for name, dret in (extra or {}).items():
        dr = dret.reindex(e.index).fillna(0.0)
        equity = (1 + dr).cumprod()
        m = metrics(equity, args.cash_yield)
        rows[name] = m
        print(f"  {name:<18} {_fmt(m, None, float('nan'), yrs)}")
    return rows


def _alloc_action(alloc, args):
    if alloc == "EQ":
        return f"IN — hold {args.equity} (stocks)", "✅"
    if alloc == "BOND":
        return f"DEFENSIVE — hold {args.bond} (bonds)", "🟡"
    return "OUT — hold cash (e.g. SGOV)", "🛑"


def _raw_daily(key, eq, bond, args):
    """Daily in/out (EQ|BOND|CASH) from each rule's LATEST reading — no monthly
    smoothing — so the live signal reflects today's actual price, not a stale
    month-end decision."""
    c = eq["close"]
    if key in ("200d_timing", "spy_or_bonds"):
        sma = c.rolling(args.ma).mean()
        alt = "CASH" if key == "200d_timing" else "BOND"
        return pd.Series(np.where(c > sma, "EQ", alt), index=c.index)
    if key == "200d_buffer":
        sma = c.rolling(args.ma).mean()
        band = args.buffer / 100.0
        out, cur = [], "CASH"
        for px, m in zip(c, sma):
            if m != m:
                cur = "CASH"
            elif px > m * (1 + band):
                cur = "EQ"
            elif px < m * (1 - band):
                cur = "CASH"
            out.append(cur)
        return pd.Series(out, index=c.index)
    if key == "abs_momentum":
        r = c / c.shift(args.mom) - 1
        return pd.Series(np.where(r > 0, "EQ", "CASH"), index=c.index)
    if key == "dual_momentum":
        if bond is None:
            return None
        bc = bond["close"].reindex(c.index).ffill()
        em = c / c.shift(args.mom) - 1
        bm = bc / bc.shift(args.mom) - 1
        choose_eq = (em > 0) & (em >= bm)
        choose_bond = (~choose_eq) & (bm > 0)
        return pd.Series(np.where(choose_eq, "EQ", np.where(choose_bond, "BOND", "CASH")),
                         index=c.index)
    return None


def _one_signal(key, eq, bond, args):
    """Compute ONE strategy's CURRENT allocation (from the latest close) + the
    exact rule and numbers it used, and whether it flipped since last month."""
    raw = _raw_daily(key, eq, bond, args)
    if raw is None:
        return None
    c = eq["close"]
    close = float(c.iloc[-1])
    last_bar = eq.index[-1].date()

    if key in ("200d_timing", "200d_buffer", "spy_or_bonds"):
        sma = float(c.rolling(args.ma).mean().iloc[-1])
        pct = (close / sma - 1) * 100
        detail = f"close ${close:,.2f}  vs  {args.ma}-day avg ${sma:,.2f}  ({pct:+.1f}%)"
        if key == "200d_timing":
            rule = f"{args.equity} close vs its {args.ma}-day moving average"
        elif key == "200d_buffer":
            rule = (f"{args.equity} vs {args.ma}-day MA with a ±{args.buffer:.1f}% "
                    "buffer (only flips once it clears the buffer)")
        else:
            rule = (f"hold {args.equity} when above its {args.ma}-day MA, "
                    f"else {args.bond} (bonds)")
    elif key == "abs_momentum":
        prev = float(c.shift(args.mom).iloc[-1])
        ret = (close / prev - 1) * 100 if prev else float("nan")
        rule = (f"{args.equity}'s return over the last {args.mom} trading days "
                "vs 0% (go to cash if negative)")
        detail = f"{args.mom}-day return {ret:+.1f}%   (threshold 0% = cash)"
    elif key == "dual_momentum":
        bc = bond["close"].reindex(eq.index).ffill()
        em = (close / float(c.shift(args.mom).iloc[-1]) - 1) * 100
        bm = (float(bc.iloc[-1]) / float(bc.shift(args.mom).iloc[-1]) - 1) * 100
        win = (args.equity if (em > 0 and em >= bm)
               else (args.bond if bm > 0 else "cash"))
        rule = (f"hold the STRONGER of {args.equity}/{args.bond} by {args.mom}-day "
                "momentum, if it's positive (else cash)")
        detail = (f"{args.equity} {em:+.1f}%  vs  {args.bond} {bm:+.1f}%  "
                  f"→ current winner: {win}")
    else:
        return None

    alloc = str(raw.iloc[-1])
    me = raw.resample("ME").last().dropna()
    changed = bool(len(me) >= 2 and me.iloc[-1] != me.iloc[-2])
    return dict(key=key, alloc=alloc, rule=rule, detail=detail,
                last_bar=last_bar, changed=changed)


def _print_signal_report(keys, eq, bond, args):
    nxt = pd.Timestamp(eq.index[-1]).tz_localize(None) + pd.offsets.MonthBegin(1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    print("=" * 66)
    print(f"  MONTHLY SIGNAL(S) — {args.equity}   (as of last close "
          f"{eq.index[-1].date()})")
    print("=" * 66)
    print("  ⚠ These are ETF TIMING / REGIME signals (in-market vs defensive),")
    print("    NOT 3R trade setups. Paper-trade first; history, not the future.")
    sigs = []
    for k in keys:
        s = _one_signal(k, eq, bond, args)
        if s is None:
            continue
        sigs.append(s)
        action, icon = _alloc_action(s["alloc"], args)
        flip = "  ⟳ CHANGED since last month — ACT" if s["changed"] else \
               "  (no change — do nothing)"
        print("\n  " + "-" * 62)
        print(f"  {icon} {s['key']:<14}  →  {action}{flip}")
        print(f"     rule : {s['rule']}")
        print(f"     now  : {s['detail']}")
    print("\n  " + "-" * 62)
    if len(sigs) > 1:
        ineq = [s["key"] for s in sigs if s["alloc"] == "EQ"]
        n_on = len(ineq)
        if n_on == len(sigs):
            print("  GREEN LIGHT: every strategy is risk-ON (in stocks). Cleanest signal.")
        elif n_on == 0:
            print("  RED LIGHT: every strategy is DEFENSIVE/cash. Stay out.")
        else:
            print(f"  MIXED: {n_on}/{len(sigs)} say risk-ON. Be cautious — they "
                  "disagree, so the trend is borderline.")
    print(f"  Next check: ~{nxt.date()} (about a month out). Only ACT when a "
          "signal flips.")
    print("  Reminder: the backtest's best framework was abs_momentum, but "
          "200d_timing is the steadier defensive overlay — watch them together.")


def main():
    ap = argparse.ArgumentParser(description="Compare low-risk strategies vs SPY buy-and-hold")
    ap.add_argument("--source", default="synthetic",
                    choices=["synthetic", "csv", "polygon", "massive",
                             "massive_files", "schwab", "stooq", "yahoo"])
    ap.add_argument("--equity", default="SPY")
    ap.add_argument("--bond", default="AGG")
    ap.add_argument("--years", type=int, default=12)
    ap.add_argument("--ma", type=int, default=200,
                    help="moving-average length for the timing rules (default 200; "
                         "try 150 or 250 — judge on OUT-OF-SAMPLE, not in-sample)")
    ap.add_argument("--buffer", type=float, default=1.5,
                    help="buffer %% around the MA before switching (default 1.5)")
    ap.add_argument("--mom", type=int, default=200,
                    help="momentum lookback in days for the momentum rules (default 200)")
    ap.add_argument("--cash-yield", type=float, default=0.04, dest="cash_yield",
                    help="annual T-bill/cash yield earned when out of the market")
    ap.add_argument("--div-yield", type=float, default=0.017, dest="div_yield",
                    help="equity dividend yield added back (price-return data)")
    ap.add_argument("--bond-div-yield", type=float, default=0.03, dest="bond_div_yield")
    ap.add_argument("--cost-bps", type=float, default=5.0, dest="cost_bps",
                    help="per-switch cost (spread+slippage+commission), bps")
    ap.add_argument("--signal", action="store_true",
                    help="print today's timing signal(s) for the monthly check")
    ap.add_argument("--strategy", default=None,
                    choices=["200d_timing", "200d_buffer", "abs_momentum",
                             "dual_momentum", "spy_or_bonds", "all"],
                    help="which strategy's signal to show (default 200d_timing); "
                         "'all' shows every strategy side by side")
    args = ap.parse_args()

    adapter = get_adapter(args.source)
    as_of = pd.Timestamp.now("UTC").normalize()

    if args.signal:
        eq = load(adapter, args.equity, max(args.years, 2), as_of)
        if eq is None:
            raise SystemExit(
            f"\n  No price data for {args.equity} from {args.source}.\n"
            f"  • {args.source} may not carry that ticker. Try a common one:\n"
            f"      python3 beat_spy.py --source yahoo --equity SPY\n")
        bond = load(adapter, args.bond, max(args.years, 2), as_of)
        keys = (["200d_timing", "200d_buffer", "abs_momentum",
                 "dual_momentum", "spy_or_bonds"]
                if args.strategy == "all"
                else [args.strategy or "200d_timing"])
        _print_signal_report(keys, eq, bond, args)
        return

    eq = load(adapter, args.equity, args.years, as_of)
    if eq is None:
        raise SystemExit(
            f"\n  No price data for {args.equity} from {args.source}.\n"
            f"  • {args.source} may not carry that ticker. Try a common one:\n"
            f"      python3 beat_spy.py --source stooq --equity SPY --years 12\n"
            f"  • or use your Massive key:  --source massive --equity SPLG\n")
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

    # sector-rotation momentum (relative-strength across sector ETFs)
    extra = {}
    basket = _load_basket(adapter, SECTOR_ETFS, args.years, as_of)
    rot = sector_rotation_returns(basket, eq.index, cash_yield=args.cash_yield,
                                  div_yield=args.div_yield, cost_bps=args.cost_bps)
    if rot is not None:
        extra["sector_rotation"] = rot
        print(f"  Sector rotation: top-3 of {len(basket)} sector ETFs by 6-mo momentum")

    strategies = build_strategies(ma=args.ma, band=args.buffer / 100.0, mom=args.mom)
    full = evaluate(eq, bond, args, "FULL PERIOD", extra=extra, strategies=strategies)

    # in-sample / out-of-sample split (first 60% / last 40%)
    split = eq.index[int(len(eq) * 0.6)]
    evaluate(eq, bond, args, "IN-SAMPLE (first 60%)",
             idx=eq.index[eq.index <= split], extra=extra, strategies=strategies)
    oos = evaluate(eq, bond, args, "OUT-OF-SAMPLE (last 40%)",
                   idx=eq.index[eq.index > split], extra=extra, strategies=strategies)

    # honest verdict
    _plain_bottom_line(oos)


def _how_to_trade(label, m):
    """Plain-English 'how you'd actually run this': instrument, how often you
    trade, how long you hold. These timing rules are ETF swaps, NOT options."""
    tpy = m.get("trades_per_year")
    hold = m.get("avg_hold_days")
    pin = m.get("pct_in_market")
    print(f"\n     HOW YOU'D TRADE '{label}' (the practical details):")
    print("       • What you trade: PLAIN ETF SHARES — buy/sell a fund "
          "(e.g. SPLG for stocks, AGG for bonds, SGOV for cash). NO options.")
    if tpy is not None:
        permo = tpy / 12.0
        unit = "time" if round(tpy) == 1 else "times"
        if permo < 0.5:
            freq = f"about {tpy:.0f} {unit} a YEAR (less than once a month)"
        else:
            freq = f"about {tpy:.0f} {unit} a year (~{permo:.1f} a month)"
        print(f"       • How often you trade: {freq}. You CHECK once a month, "
              "but only actually buy/sell when the signal flips.")
    if hold:
        months = hold / 21.0
        print(f"       • How long you stay in: typically ~{months:.0f} month(s) "
              f"per position (~{hold:.0f} trading days) before it flips you out.")
    if pin is not None and pin == pin:
        print(f"       • Time invested: about {pin:.0%} of the time in the market; "
              "the rest you sit safely in cash/bonds (that's what dodges crashes).")
    print("       • Effort: ~5 minutes, once a month. This is slow, low-stress "
          "investing — the opposite of day-trading.")


def _plain_bottom_line(oos):
    """Plain-English summary of the OUT-OF-SAMPLE results: what beat buy-and-hold,
    HOW it beat it, and what didn't — sorted so the best is on top."""
    print("\n" + "=" * 80)
    print("  BOTTOM LINE — did anything beat just holding the market? (plain English)")
    print("  (out-of-sample = the honest test, on data the rules never saw)")
    print("=" * 80)
    base = oos.get("buy_hold_SPY")
    if not base:
        print("  Not enough data to judge.")
        return
    b_ret, b_dd = base["total_return"] * 100, base["max_drawdown"] * 100
    print(f"\n  Just holding the market (buy & hold): grew {b_ret:+.0f}% overall, "
          f"but its worst drop along the way was {b_dd:.0f}%.")

    wins, risk_only, worse = [], [], []
    for name, m in oos.items():
        if name == "buy_hold_SPY":
            continue
        ret, dd = m["total_return"] * 100, m["max_drawdown"] * 100
        smaller_crash = dd > b_dd                       # less negative
        comparable_return = ret >= 0.8 * b_ret          # within 20% of the market
        better_return = ret >= b_ret
        item = (name, ret, dd, better_return)
        if smaller_crash and comparable_return:
            wins.append(item)
        elif smaller_crash:
            risk_only.append(item)
        else:
            worse.append(item)

    # best = biggest crash reduction among the genuine wins
    wins.sort(key=lambda x: x[2], reverse=True)         # least-negative dd first
    risk_only.sort(key=lambda x: x[2], reverse=True)

    def _name(n):  # friendlier label
        return n.replace("SPY_", "").replace("_", " ")

    if wins:
        print("\n  ✅ THESE BEAT BUY-AND-HOLD (smoother ride — the win you want):")
        for n, ret, dd, better in wins:
            how = ("grew MORE and crashed less" if better
                   else "kept up with the market but crashed less")
            print(f"     • {_name(n):<16} {how}: "
                  f"worst drop {dd:.0f}% vs the market's {b_dd:.0f}%, "
                  f"growth {ret:+.0f}%.")
        best = wins[0]
        print(f"\n     BEST: '{_name(best[0])}' cut your worst crash from "
              f"{b_dd:.0f}% to {best[2]:.0f}% — that is how it beats buy-and-hold: "
              "less pain for similar gain.")
        _how_to_trade(_name(best[0]), oos.get(best[0], {}))
    else:
        print("\n  ✅ Cleanly beat buy-and-hold: NONE this run. That's normal — "
              "don't force it.")

    if risk_only:
        print("\n  🟡 SAFER BUT SLOWER (smaller crash, but gave up too much growth):")
        for n, ret, dd, _ in risk_only:
            print(f"     • {_name(n):<16} worst drop {dd:.0f}% (vs {b_dd:.0f}%), "
                  f"but growth only {ret:+.0f}%.")

    if worse:
        names = ", ".join(_name(n) for n, *_ in worse)
        print(f"\n  ❌ DID NOT HELP (bigger crash — skip): {names}")

    print("\n  WHAT 'BEAT' MEANS HERE: a smaller worst-drop with similar growth is")
    print("  the realistic win for a small, low-risk account. Beating raw growth is")
    print("  rare and usually luck — only trust a winner that holds up here, out-of-")
    print("  sample, across different time periods. Paper-trade before real money.")


if __name__ == "__main__":
    main()
