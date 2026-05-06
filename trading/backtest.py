import os, math, datetime
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
ACCOUNT_SIZE   = float(os.getenv("ACCOUNT_SIZE", 1673.00))
YEARS_BACK     = 7
SLIPPAGE       = 0.03        # $ per share, both sides
OPTION_SLIP    = 0.05        # $ per share on options premium
RISK_FREE_RATE = 0.045       # ~4.5% annual (approximate 10yr Treasury)
RISK_PCT       = 0.02        # 2% account risk per stock trade
MAX_POS_PCT    = 0.25        # max 25% of account in one position
OPTION_RISK    = 0.02        # 2% of account per options trade
OPT_DTE        = 40          # buy options with ~40 days to expiration
OPT_OTM        = 0.02        # 2% out-of-the-money calls

RESULTS_FILE = "backtest_results.csv"
OPTIONS_FILE = "options_results.csv"
EQUITY_FILE  = "equity_curve.csv"
SUMMARY_FILE = "backtest_summary.txt"

ETF_WATCHLIST = [
    "SPY", "QQQ", "IWM", "VTI",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLRE",
    "GLD", "SLV", "TLT", "HYG", "ARKK", "SMH", "IBB", "EEM", "EFA",
]


# ─── Data ─────────────────────────────────────────────────────────────────────
def fetch_history(symbol, extra_days=250):
    try:
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=365 * YEARS_BACK + extra_days)
        df    = yf.Ticker(symbol).history(start=start, end=end, interval="1d")
        if df is None or df.empty or len(df) < 200:
            return None
        df.columns = [c.lower() for c in df.columns]
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        return df[cols].copy()
    except Exception as e:
        print(f"  [fetch error] {symbol}: {e}")
        return None


# ─── Indicators ───────────────────────────────────────────────────────────────
def compute_indicators(df):
    d = df.copy()
    d["sma20"]       = d["close"].rolling(20).mean()
    d["sma50"]       = d["close"].rolling(50).mean()
    d["sma200"]      = d["close"].rolling(200).mean()
    d["avg_vol"]     = d["volume"].rolling(20).mean()
    d["vol_ratio"]   = d["volume"] / (d["avg_vol"] + 1e-9)
    d["spread"]      = (d["high"] - d["low"]) / (d["close"] + 1e-9)
    d["close_pos"]   = (d["close"] - d["low"]) / (d["high"] - d["low"] + 1e-9)
    d["dollar_vol"]  = d["volume"] * d["close"]
    d["momentum_20"] = d["close"].pct_change(20)
    d["momentum_60"] = d["close"].pct_change(60)
    # RSI 14
    delta      = d["close"].diff()
    gain       = delta.clip(lower=0).rolling(14).mean()
    loss       = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    # ATR 14
    hl        = d["high"] - d["low"]
    hpc       = (d["high"] - d["close"].shift(1)).abs()
    lpc       = (d["low"]  - d["close"].shift(1)).abs()
    d["atr14"] = pd.concat([hl, hpc, lpc], axis=1).max(axis=1).rolling(14).mean()
    # Annualised 20-day historical vol for options pricing
    d["hist_vol"] = d["close"].pct_change().rolling(20).std() * math.sqrt(252)
    return d.dropna()


# ─── VPA ──────────────────────────────────────────────────────────────────────
def vpa_signal(row):
    if row["dollar_vol"] < 50_000_000:
        return "LOW_LIQUIDITY"
    high_vol  = row["vol_ratio"] > 1.3
    low_vol   = row["vol_ratio"] < 0.7
    wide_up   = row["spread"] > 0.01 and row["close_pos"] > 0.6
    wide_down = row["spread"] > 0.01 and row["close_pos"] < 0.4
    narrow    = row["spread"] < 0.005
    if low_vol and narrow and row["close"] > row["sma20"]:
        return "NO_SUPPLY"
    if high_vol and wide_up:
        return "STOPPING_VOLUME"
    if low_vol and wide_down:
        return "NO_DEMAND"
    if high_vol and wide_down:
        return "BUYING_CLIMAX"
    return "NORMAL"


def should_enter(row, spy_bullish):
    """VPA signal + RSI filter + dual-SMA trend + market regime."""
    if not spy_bullish:
        return False
    if vpa_signal(row) not in ("NO_SUPPLY", "STOPPING_VOLUME"):
        return False
    if row["momentum_20"] <= 0 or row["momentum_60"] <= 0:
        return False
    if row["close"] < row["sma20"] or row["close"] < row["sma50"]:
        return False
    # RSI 40-70: not overbought, not deeply oversold
    if not (40 <= row["rsi14"] <= 70):
        return False
    return True


# ─── Black-Scholes (no scipy dependency) ─────────────────────────────────────
def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S, K, T, r, sigma, direction="call"):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0) if direction == "call" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if direction == "call":
        return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def price_option(S, direction, vol, dte=40, otm_pct=0.02):
    """Returns (premium_per_share, strike)."""
    T = max(dte, 1) / 252
    K = S * (1 + otm_pct) if direction == "call" else S * (1 - otm_pct)
    px = bs_price(S, K, T, RISK_FREE_RATE, max(vol, 0.10), direction)
    return round(px, 2), round(K, 2)


# ─── Position sizer (compounding) ─────────────────────────────────────────────
def size_position(equity, entry, stop):
    risk = entry - stop
    if risk <= 0:
        return 0
    s1 = int((equity * RISK_PCT) / risk)
    s2 = int((equity * MAX_POS_PCT) / entry)
    return max(min(s1, s2), 0)


# ─── SPY market regime ────────────────────────────────────────────────────────
def build_spy_regime():
    """date -> bool: True = SPY above 200-day SMA (bullish regime)."""
    df = fetch_history("SPY", extra_days=250)
    if df is None:
        return {}
    df = compute_indicators(df)
    return {idx.date(): bool(row["close"] > row["sma200"]) for idx, row in df.iterrows()}


# ─── Single-symbol backtest ───────────────────────────────────────────────────
def backtest_symbol(symbol, spy_regime, equity_ref):
    df = fetch_history(symbol)
    if df is None:
        return [], []
    df = compute_indicators(df)
    if df.empty:
        return [], []

    stock_trades  = []
    option_trades = []
    in_pos        = False
    in_option     = False
    entry = stop = target1 = target2 = 0.0
    shares = shares_remain = 0
    entry_date   = None
    partial_done = False
    opt_entry_px   = opt_contracts = 0
    opt_direction  = ""
    opt_entry_date = None
    opt_dte_start  = OPT_DTE

    for i in range(1, len(df)):
        row        = df.iloc[i]
        prev       = df.iloc[i - 1]
        date       = df.index[i].date()
        spy_ok     = spy_regime.get(date, False)
        cur_equity = equity_ref["value"]

        # ── Entry ─────────────────────────────────────────────────────────
        if not in_pos and should_enter(prev, spy_ok):
            entry   = float(row["open"]) + SLIPPAGE
            atr     = float(prev["atr14"])
            stop    = round(entry - 2.0 * atr, 2)          # ATR-based stop
            target1 = round(entry * 1.04, 2)
            target2 = round(entry * 1.08, 2)
            shares  = size_position(cur_equity, entry, stop)
            if shares < 1:
                continue
            shares_remain = shares
            partial_done  = False
            in_pos        = True
            entry_date    = date

            # Options: buy 2% OTM call, 40 DTE, budget = 2% of equity
            vol = float(prev["hist_vol"])
            opt_px, _ = price_option(entry, "call", vol, dte=OPT_DTE, otm_pct=OPT_OTM)
            budget = cur_equity * OPTION_RISK
            opt_contracts = int(budget / ((opt_px + OPTION_SLIP) * 100 + 1e-9))
            if opt_contracts >= 1:
                opt_entry_px   = opt_px + OPTION_SLIP
                opt_direction  = "call"
                opt_entry_date = date
                opt_dte_start  = OPT_DTE
                in_option      = True

        elif in_pos:
            hold_days  = (date - entry_date).days
            lo, hi     = float(row["low"]), float(row["high"])
            exit_price = None
            reason     = ""

            # Partial exit at target1 — sell half, trail stop to breakeven
            if not partial_done and hi >= target1:
                half   = max(shares_remain // 2, 1)
                p_exit = target1 - SLIPPAGE
                stock_trades.append({
                    "symbol":     symbol,
                    "entry_date": entry_date.isoformat(),
                    "exit_date":  date.isoformat(),
                    "hold_days":  hold_days,
                    "entry":      round(entry, 2),
                    "exit":       round(p_exit, 2),
                    "shares":     half,
                    "pnl":        round((p_exit - entry) * half, 2),
                    "pnl_pct":    round((p_exit - entry) / entry * 100, 2),
                    "reason":     "TARGET1_PARTIAL",
                })
                shares_remain -= half
                stop          = entry  # trail to breakeven — now risk-free
                partial_done  = True

            # Full exit
            if lo <= stop:
                exit_price = stop - SLIPPAGE;          reason = "STOP"
            elif hi >= target2:
                exit_price = target2 - SLIPPAGE;       reason = "TARGET2"
            elif hold_days >= 10:
                exit_price = float(row["close"]) - SLIPPAGE; reason = "TIMEOUT"

            if exit_price is not None and shares_remain > 0:
                stock_trades.append({
                    "symbol":     symbol,
                    "entry_date": entry_date.isoformat(),
                    "exit_date":  date.isoformat(),
                    "hold_days":  hold_days,
                    "entry":      round(entry, 2),
                    "exit":       round(exit_price, 2),
                    "shares":     shares_remain,
                    "pnl":        round((exit_price - entry) * shares_remain, 2),
                    "pnl_pct":    round((exit_price - entry) / entry * 100, 2),
                    "reason":     reason,
                })
                in_pos = False

        # ── Options exit ──────────────────────────────────────────────────
        if in_option:
            days_held     = (date - opt_entry_date).days
            remaining_dte = max(opt_dte_start - days_held, 1)
            close_option  = (not in_pos) or (days_held >= opt_dte_start)
            if close_option:
                S   = float(row["close"])
                vol = float(row["hist_vol"])
                cur_px, _ = price_option(S, opt_direction, vol,
                                         dte=remaining_dte, otm_pct=OPT_OTM)
                exit_px  = max(cur_px - OPTION_SLIP, 0.0)
                opt_pnl  = (exit_px - opt_entry_px) * opt_contracts * 100
                option_trades.append({
                    "symbol":         symbol,
                    "direction":      opt_direction,
                    "entry_date":     opt_entry_date.isoformat(),
                    "exit_date":      date.isoformat(),
                    "entry_premium":  round(opt_entry_px, 2),
                    "exit_premium":   round(exit_px, 2),
                    "contracts":      opt_contracts,
                    "pnl":            round(opt_pnl, 2),
                    "pnl_pct":        round((exit_px - opt_entry_px) /
                                           (opt_entry_px + 1e-9) * 100, 1),
                })
                in_option = False

    return stock_trades, option_trades


# ─── Risk metrics ─────────────────────────────────────────────────────────────
def calc_metrics(pnls, equity_series, account_size):
    if not pnls:
        return {}
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    pf     = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 999.0
    eq     = pd.Series(equity_series)
    peak   = eq.cummax()
    max_dd = ((eq - peak) / peak).min() * 100
    dr     = eq.pct_change().dropna()
    sharpe  = (dr.mean() / (dr.std() + 1e-9)) * math.sqrt(252)
    dn      = dr[dr < 0].std()
    sortino = (dr.mean() / (dn + 1e-9)) * math.sqrt(252)
    total_pnl = sum(pnls)
    final_eq  = account_size + total_pnl
    return {
        "trades":        len(pnls),
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      round(len(wins) / len(pnls) * 100, 1),
        "profit_factor": round(pf, 2),
        "total_pnl":     round(total_pnl, 2),
        "final_equity":  round(final_eq, 2),
        "total_return":  round((final_eq - account_size) / account_size * 100, 1),
        "max_drawdown":  round(max_dd, 1),
        "sharpe":        round(sharpe, 2),
        "sortino":       round(sortino, 2),
    }


# ─── Buy-and-hold SPY benchmark ───────────────────────────────────────────────
def buy_and_hold_spy(equity):
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=365 * YEARS_BACK)
    df    = yf.Ticker("SPY").history(start=start, end=end)
    if df is None or df.empty:
        return {}
    sp, ep = float(df["Close"].iloc[0]), float(df["Close"].iloc[-1])
    sh     = int(equity / sp)
    pnl    = (ep - sp) * sh
    return {
        "start_price":  round(sp, 2),
        "end_price":    round(ep, 2),
        "shares":       sh,
        "pnl":          round(pnl, 2),
        "total_return": round((ep - sp) / sp * 100, 1),
        "final_equity": round(equity + pnl, 2),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────
def run_backtest():
    print("=" * 64)
    print(f"  BACKTEST v2 — {YEARS_BACK} yrs | {len(ETF_WATCHLIST)} ETFs | VPA + Options overlay")
    print(f"  Account: ${ACCOUNT_SIZE:,.2f}  |  Slippage: ${SLIPPAGE}/share")
    print(f"  Options: {OPT_OTM*100:.0f}% OTM calls | {OPT_DTE} DTE | 2% equity budget")
    print("=" * 64)

    print("  Loading SPY regime filter...")
    spy_regime = build_spy_regime()
    bullish_days = sum(spy_regime.values())
    print(f"  Regime: {bullish_days}/{len(spy_regime)} days bullish ({bullish_days/max(len(spy_regime),1)*100:.0f}%)\n")

    equity_ref = {"value": ACCOUNT_SIZE}
    all_stock  = []
    all_opts   = []

    for symbol in ETF_WATCHLIST:
        print(f"  {symbol:<6} ...", end=" ", flush=True)
        s_trades, o_trades = backtest_symbol(symbol, spy_regime, equity_ref)
        all_stock.extend(s_trades)
        all_opts.extend(o_trades)

        # Compound after each symbol — later symbols size off accumulated equity
        sym_pnl = (sum(t["pnl"] for t in s_trades) +
                   sum(t["pnl"] for t in o_trades))
        equity_ref["value"] = max(equity_ref["value"] + sym_pnl, 1.0)

        n     = len(s_trades)
        w     = sum(1 for t in s_trades if t["pnl"] > 0)
        s_pl  = sum(t["pnl"] for t in s_trades)
        o_pl  = sum(t["pnl"] for t in o_trades)
        print(f"{n:3d} trades | {w}W/{n-w}L | stock ${s_pl:+8.2f} | opts ${o_pl:+7.2f}")

    if not all_stock:
        print("\nNo trades generated.")
        return

    # Equity curve by exit date
    date_pnl = {}
    for t in all_stock + all_opts:
        date_pnl[t["exit_date"]] = date_pnl.get(t["exit_date"], 0) + t["pnl"]

    eq_rows = []
    running = ACCOUNT_SIZE
    for d in sorted(date_pnl):
        running += date_pnl[d]
        eq_rows.append({"date": d, "equity": round(running, 2)})

    pd.DataFrame(eq_rows).to_csv(EQUITY_FILE, index=False)
    pd.DataFrame(all_stock).to_csv(RESULTS_FILE, index=False)
    pd.DataFrame(all_opts).to_csv(OPTIONS_FILE, index=False)

    # Per-symbol summary
    print(f"\n  {'Symbol':<6} {'Trades':>6} {'WR%':>6} {'Stock P&L':>12} {'Opt P&L':>10}")
    print("  " + "─" * 46)
    for sym in ETF_WATCHLIST:
        st = [t for t in all_stock if t["symbol"] == sym]
        ot = [t for t in all_opts  if t["symbol"] == sym]
        if not st:
            continue
        pnls = [t["pnl"] for t in st]
        wr   = sum(1 for p in pnls if p > 0) / len(pnls) * 100
        opt_pl = sum(t["pnl"] for t in ot)
        print(f"  {sym:<6} {len(pnls):>6} {wr:>5.1f}% ${sum(pnls):>+11.2f} ${opt_pl:>+9.2f}")

    # Overall metrics
    all_pnls   = [t["pnl"] for t in all_stock]
    eq_vals    = [ACCOUNT_SIZE] + [r["equity"] for r in eq_rows]
    m          = calc_metrics(all_pnls, eq_vals, ACCOUNT_SIZE)
    opt_total  = sum(t["pnl"] for t in all_opts)
    bnh        = buy_and_hold_spy(ACCOUNT_SIZE)
    combined   = m["total_pnl"] + opt_total
    combo_ret  = combined / ACCOUNT_SIZE * 100
    diff       = combo_ret - bnh.get("total_return", 0)
    verdict    = (f"BEAT buy-and-hold by +{diff:.1f}%"
                  if diff > 0 else f"Buy-and-hold beat strategy by {abs(diff):.1f}%")

    print(f"\n  STOCK STRATEGY")
    print(f"  Trades:         {m['trades']}")
    print(f"  Win rate:       {m['win_rate']}%")
    print(f"  Profit factor:  {m['profit_factor']}")
    print(f"  P&L:            ${m['total_pnl']:,.2f}")
    print(f"  Return:         {m['total_return']}%")
    print(f"  Max drawdown:   {m['max_drawdown']}%")
    print(f"  Sharpe ratio:   {m['sharpe']}")
    print(f"  Sortino ratio:  {m['sortino']}")

    print(f"\n  OPTIONS OVERLAY ({OPT_OTM*100:.0f}% OTM calls, {OPT_DTE} DTE)")
    print(f"  Trades:         {len(all_opts)}")
    print(f"  P&L:            ${opt_total:,.2f}")
    if all_opts:
        ow = sum(1 for t in all_opts if t["pnl"] > 0)
        print(f"  Win rate:       {ow / len(all_opts) * 100:.1f}%")

    print(f"\n  COMBINED")
    print(f"  Total P&L:      ${combined:,.2f}")
    print(f"  Final equity:   ${ACCOUNT_SIZE + combined:,.2f}")
    print(f"  Return:         {combo_ret:.1f}%")

    print(f"\n  BUY & HOLD SPY")
    print(f"  P&L:            ${bnh.get('pnl', 0):,.2f}")
    print(f"  Equity:         ${bnh.get('final_equity', 0):,.2f}")
    print(f"  Return:         {bnh.get('total_return', 0)}%")

    print(f"\n  VERDICT: {verdict}")

    summary = (
        f"BACKTEST v2\n"
        f"Stock return:    {m['total_return']}%\n"
        f"Options P&L:     ${opt_total:,.2f}\n"
        f"Combined return: {combo_ret:.1f}%\n"
        f"Sharpe:          {m['sharpe']}  |  Sortino: {m['sortino']}\n"
        f"Max drawdown:    {m['max_drawdown']}%\n"
        f"Profit factor:   {m['profit_factor']}\n"
        f"Buy-hold return: {bnh.get('total_return', 0)}%\n"
        f"Verdict:         {verdict}\n"
    )
    with open(SUMMARY_FILE, "w") as f:
        f.write(summary)

    print(f"\n  Saved: {RESULTS_FILE}, {OPTIONS_FILE}, {EQUITY_FILE}, {SUMMARY_FILE}")


if __name__ == "__main__":
    run_backtest()
