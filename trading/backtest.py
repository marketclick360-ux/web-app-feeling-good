"""
Backtest v3 — Multi-Legend Strategy
Anna Couling / Gann / Dalio / Weinstein / Livermore
Risk objective: minimise drawdown first, then maximise Sharpe.
"""
import os, math, datetime
import pandas as pd
from dotenv import load_dotenv
from schwab_client import fetch_history, get_account_balance

load_dotenv()

_env_size    = os.getenv("ACCOUNT_SIZE")
ACCOUNT_SIZE = float(_env_size) if _env_size else (get_account_balance() or 1673.00)
YEARS_BACK         = 7
SLIPPAGE           = 0.03
OPTION_SLIP        = 0.05
RISK_FREE_RATE     = 0.045
TARGET_VOL_CONTRIB = 0.007
MAX_POS_PCT        = 0.20
OPTION_RISK        = 0.015
OPT_DTE            = 40
OPT_OTM            = 0.02
GANN_LOOKBACK      = 60
SWING_WINDOW       = 10

RESULTS_FILE = "backtest_results.csv"
OPTIONS_FILE = "options_results.csv"
EQUITY_FILE  = "equity_curve.csv"
SUMMARY_FILE = "backtest_summary.txt"

ETF_WATCHLIST = [
    "SPY", "QQQ", "IWM", "VTI",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLRE",
    "GLD", "SLV", "TLT", "HYG", "ARKK", "SMH", "IBB", "EEM", "EFA",
]

REGIME_ETFS = {
    "GROWTH_DEFLATION":    ["QQQ", "XLK", "SPY", "VTI", "IWM", "XLY", "SMH",
                            "IBB", "XLC", "XLF", "ARKK", "EFA"],
    "GROWTH_INFLATION":    ["GLD", "SLV", "XLE", "XLB", "XLI", "EEM", "EFA",
                            "SMH", "IBB", "XLF"],
    "RECESSION_DEFLATION": ["TLT", "GLD", "XLV", "XLP", "XLRE", "HYG", "EFA"],
    "RECESSION_INFLATION": ["GLD", "SLV", "XLE", "TLT", "XLV", "XLP", "XLB"],
}


def compute_indicators(df):
    d = df.copy()
    d["sma20"]        = d["close"].rolling(20).mean()
    d["sma50"]        = d["close"].rolling(50).mean()
    d["sma150"]       = d["close"].rolling(150).mean()
    d["sma200"]       = d["close"].rolling(200).mean()
    d["sma150_slope"] = d["sma150"].diff(5)
    d["avg_vol"]   = d["volume"].rolling(20).mean()
    d["vol_ratio"] = d["volume"] / (d["avg_vol"] + 1e-9)
    atr_raw = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift(1)).abs(),
        (d["low"]  - d["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    d["atr14"]     = atr_raw.rolling(14).mean()
    d["atr_pct"]   = d["atr14"] / (d["close"] + 1e-9)
    d["spread"]    = (d["high"] - d["low"]) / (d["close"] + 1e-9)
    d["close_pos"] = (d["close"] - d["low"]) / (d["high"] - d["low"] + 1e-9)
    d["dollar_vol"]= d["volume"] * d["close"]
    d["mom10"] = d["close"].pct_change(10)
    d["mom20"] = d["close"].pct_change(20)
    d["mom60"] = d["close"].pct_change(60)
    delta      = d["close"].diff()
    gain       = delta.clip(lower=0).rolling(14).mean()
    loss       = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    d["pivot_hi"] = d["high"].rolling(20).max().shift(1)
    d["hist_vol"] = d["close"].pct_change().rolling(20).std() * math.sqrt(252)
    return d.dropna()


def couling_vpa(row, prev):
    if row["dollar_vol"] < 50_000_000:
        return "LOW_LIQUIDITY", "NEUTRAL"
    atr_pct   = max(float(row["atr_pct"]), 0.01)
    spread    = float(row["spread"])
    cp        = float(row["close_pos"])
    vr        = float(row["vol_ratio"])
    very_high = vr > 2.0
    high_vol  = vr > 1.5
    mod_high  = 1.1 < vr <= 1.5
    low_vol   = vr < 0.75
    very_low  = vr < 0.50
    wide          = spread > atr_pct * 1.0
    normal_spread = atr_pct * 0.4 <= spread <= atr_pct * 1.0
    narrow        = spread < atr_pct * 0.4
    price_move    = abs(float(row["close"]) - float(row["open"])) / (float(row["close"]) + 1e-9)
    effort_ok     = price_move > atr_pct * 0.35
    if (high_vol or very_high) and not effort_ok:
        return ("EFFORT_NO_RESULT_UP" if cp > 0.55 else "EFFORT_NO_RESULT_DOWN"), "NEUTRAL"
    if (high_vol or very_high) and wide and cp < 0.35:
        if float(prev["close"]) > float(prev["sma20"]):
            return "UPTHRUST", "BEAR"
    if mod_high and wide and cp < 0.40:
        return "PSEUDO_UPTHRUST", "BEAR"
    if low_vol and narrow and cp < 0.50:
        return "NO_DEMAND", "BEAR"
    if very_high and wide and cp < 0.30:
        return "BUYING_CLIMAX", "BEAR"
    if low_vol and narrow and cp > 0.55:
        return "NO_SUPPLY", "BULL"
    if very_low and cp > 0.60 and float(prev["vol_ratio"]) >= 0.9:
        return "TEST_OF_SUPPLY", "BULL"
    if (high_vol or very_high) and wide and cp > 0.65:
        return "STOPPING_VOLUME", "BULL"
    if mod_high and normal_spread and cp > 0.65:
        return "BULLISH_CONFIRMATION", "BULL"
    return "NORMAL", "NEUTRAL"


def gann_1x1_bullish(close, bar_idx, swing_low_price, swing_low_idx):
    bars = bar_idx - swing_low_idx
    if bars <= 0:
        return True
    return close >= swing_low_price * (1 + 0.001 * bars)


def gann_sq9_targets(entry_price):
    root = math.sqrt(max(entry_price, 0.01))
    return round((root + 0.5) ** 2, 2), round((root + 1.0) ** 2, 2)


def find_confirmed_swings(df):
    closes, swings, w = df["close"].values, [], SWING_WINDOW
    for i in range(w, len(closes) - w):
        if closes[i] == closes[i - w: i + w + 1].min():
            swings.append(i)
    return swings


def is_weinstein_stage2(row):
    return (float(row["close"]) > float(row["sma150"])) and (float(row["sma150_slope"]) > 0)


def is_livermore_breakout(prev, prev_prev):
    return (float(prev["close"]) > float(prev_prev["pivot_hi"]) and
            float(prev["vol_ratio"]) > 1.05)


def build_dalio_regime():
    spy_df = fetch_history("SPY", years=YEARS_BACK, extra_days=300)
    tlt_df = fetch_history("TLT", years=YEARS_BACK, extra_days=300)
    if spy_df is None or tlt_df is None:
        return {}
    spy_roc = spy_df["close"].pct_change(60)
    tlt_roc = tlt_df["close"].pct_change(60)
    spy_by_date = {d.date(): v for d, v in spy_roc.items() if not math.isnan(v)}
    tlt_by_date = {d.date(): v for d, v in tlt_roc.items() if not math.isnan(v)}
    regime = {}
    for d in set(spy_by_date) & set(tlt_by_date):
        growth    = spy_by_date[d] > 0
        inflation = tlt_by_date[d] < 0
        if growth and not inflation:       regime[d] = "GROWTH_DEFLATION"
        elif growth and inflation:         regime[d] = "GROWTH_INFLATION"
        elif not growth and not inflation: regime[d] = "RECESSION_DEFLATION"
        else:                              regime[d] = "RECESSION_INFLATION"
    return regime


def etf_fits_regime(symbol, regime_str):
    if not regime_str:
        return True
    return symbol in REGIME_ETFS.get(regime_str, [])


def size_riskparity(equity, atr, price):
    if atr <= 0 or price <= 0:
        return 0
    return max(min(int((equity * TARGET_VOL_CONTRIB) / atr),
                   int((equity * MAX_POS_PCT) / price)), 0)


def build_spy_regime():
    df = fetch_history("SPY", years=YEARS_BACK, extra_days=300)
    if df is None:
        return {}
    df = compute_indicators(df)
    return {idx.date(): bool(row["close"] > row["sma200"]) for idx, row in df.iterrows()}


BULLISH_VPA = {"NO_SUPPLY", "TEST_OF_SUPPLY", "STOPPING_VOLUME", "BULLISH_CONFIRMATION"}
BEARISH_VPA = {"UPTHRUST", "PSEUDO_UPTHRUST", "BUYING_CLIMAX", "NO_DEMAND"}


def should_enter(prev, prev_prev, spy_bullish, dalio_regime, symbol,
                 bar_idx, swing_low_price, swing_low_idx, confirmed_swings):
    if not spy_bullish:                          return False
    if not etf_fits_regime(symbol, dalio_regime): return False
    if not is_weinstein_stage2(prev):            return False
    sig, sentiment = couling_vpa(prev, prev_prev)
    if sentiment != "BULL":                      return False
    if not gann_1x1_bullish(float(prev["close"]), bar_idx - 1,
                             swing_low_price, swing_low_idx): return False
    if not is_livermore_breakout(prev, prev_prev): return False
    if float(prev["mom20"]) <= 0 or float(prev["mom60"]) <= 0: return False
    if not (35 <= float(prev["rsi14"]) <= 72):  return False
    return True


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
    T  = max(dte, 1) / 252
    K  = S * (1 + otm_pct) if direction == "call" else S * (1 - otm_pct)
    px = bs_price(S, K, T, RISK_FREE_RATE, max(vol, 0.10), direction)
    return round(px, 2), round(K, 2)


def backtest_symbol(symbol, spy_regime, dalio_regime, equity_ref):
    df = fetch_history(symbol, years=YEARS_BACK, extra_days=300)
    if df is None:
        return [], []
    df = compute_indicators(df)
    if len(df) < 200:
        return [], []
    confirmed_swings = find_confirmed_swings(df)
    closes = df["close"].values
    stock_trades, option_trades = [], []
    in_pos = in_option = False
    entry = stop = target1 = target2 = 0.0
    shares = shares_remain = 0
    entry_date = None
    partial_done = False
    opt_entry_px = 0.0
    opt_contracts = 0
    opt_direction = opt_entry_date = None
    opt_dte_start = OPT_DTE

    for i in range(2, len(df)):
        row       = df.iloc[i]
        prev      = df.iloc[i - 1]
        prev_prev = df.iloc[i - 2]
        date      = df.index[i].date()
        spy_ok    = spy_regime.get(date, False)
        d_regime  = dalio_regime.get(date, "")
        cur_eq    = equity_ref["value"]
        sw_start        = max(0, i - GANN_LOOKBACK)
        sw_slice        = closes[sw_start:i]
        sw_rel_idx      = int(sw_slice.argmin())
        swing_low_price = float(sw_slice[sw_rel_idx])
        swing_low_idx   = sw_start + sw_rel_idx

        if not in_pos:
            if should_enter(prev, prev_prev, spy_ok, d_regime, symbol,
                            i, swing_low_price, swing_low_idx, confirmed_swings):
                entry = float(row["open"]) + SLIPPAGE
                atr   = float(prev["atr14"])
                stop  = round(entry - 2.0 * atr, 2)
                sq9_r1, sq9_r2 = gann_sq9_targets(entry)
                target1 = round(max(sq9_r1, entry * 1.03), 2)
                target2 = round(max(sq9_r2, entry * 1.06), 2)
                shares  = size_riskparity(cur_eq, atr, entry)
                if shares < 1:
                    continue
                shares_remain = shares
                partial_done  = False
                in_pos        = True
                entry_date    = date
                vol = float(prev["hist_vol"])
                opt_px, _ = price_option(entry, "call", vol, dte=OPT_DTE, otm_pct=OPT_OTM)
                budget        = cur_eq * OPTION_RISK
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
            sig, sentiment = couling_vpa(row, prev)
            if sig in BEARISH_VPA and sentiment == "BEAR":
                exit_price = float(row["close"]) - SLIPPAGE
                reason     = f"VPA_{sig}"
            if exit_price is None and not partial_done and hi >= target1:
                half   = max(shares_remain // 2, 1)
                p_exit = target1 - SLIPPAGE
                stock_trades.append({
                    "symbol": symbol, "entry_date": entry_date.isoformat(),
                    "exit_date": date.isoformat(), "hold_days": hold_days,
                    "entry": round(entry, 2), "exit": round(p_exit, 2),
                    "shares": half, "pnl": round((p_exit - entry) * half, 2),
                    "pnl_pct": round((p_exit - entry) / entry * 100, 2),
                    "reason": "TARGET1_PARTIAL", "vpa_signal": "",
                })
                shares_remain -= half
                stop          = entry
                partial_done  = True
            if exit_price is None:
                if lo <= stop:
                    exit_price = stop - SLIPPAGE;            reason = "STOP"
                elif hi >= target2:
                    exit_price = target2 - SLIPPAGE;         reason = "TARGET2"
                elif hold_days >= 12:
                    exit_price = float(row["close"]) - SLIPPAGE; reason = "TIMEOUT"
            if exit_price is not None and shares_remain > 0:
                stock_trades.append({
                    "symbol": symbol, "entry_date": entry_date.isoformat(),
                    "exit_date": date.isoformat(), "hold_days": hold_days,
                    "entry": round(entry, 2), "exit": round(exit_price, 2),
                    "shares": shares_remain,
                    "pnl": round((exit_price - entry) * shares_remain, 2),
                    "pnl_pct": round((exit_price - entry) / entry * 100, 2),
                    "reason": reason, "vpa_signal": sig,
                })
                in_pos = False
        if in_option:
            days_held     = (date - opt_entry_date).days
            remaining_dte = max(opt_dte_start - days_held, 1)
            if (not in_pos) or (days_held >= opt_dte_start):
                S   = float(row["close"])
                vol = float(row["hist_vol"])
                cur_px, _ = price_option(S, opt_direction, vol,
                                         dte=remaining_dte, otm_pct=OPT_OTM)
                exit_px  = max(cur_px - OPTION_SLIP, 0.0)
                option_trades.append({
                    "symbol": symbol, "direction": opt_direction,
                    "entry_date": opt_entry_date.isoformat(),
                    "exit_date": date.isoformat(),
                    "entry_premium": round(opt_entry_px, 2),
                    "exit_premium":  round(exit_px, 2),
                    "contracts": opt_contracts,
                    "pnl": round((exit_px - opt_entry_px) * opt_contracts * 100, 2),
                    "pnl_pct": round((exit_px - opt_entry_px) / (opt_entry_px + 1e-9) * 100, 1),
                })
                in_option = False
    return stock_trades, option_trades


def calc_metrics(pnls, equity_series, account_size):
    if not pnls:
        return {}
    wins      = [p for p in pnls if p > 0]
    losses    = [p for p in pnls if p <= 0]
    pf        = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 999.0
    eq        = pd.Series(equity_series)
    peak      = eq.cummax()
    max_dd    = ((eq - peak) / peak).min() * 100
    dr        = eq.pct_change().dropna()
    sharpe    = (dr.mean() / (dr.std() + 1e-9)) * math.sqrt(252)
    sortino   = (dr.mean() / (dr[dr < 0].std() + 1e-9)) * math.sqrt(252)
    total_pnl = sum(pnls)
    final_eq  = account_size + total_pnl
    return {
        "trades": len(pnls), "wins": len(wins), "losses": len(losses),
        "win_rate":      round(len(wins) / len(pnls) * 100, 1),
        "profit_factor": round(pf, 2),
        "total_pnl":     round(total_pnl, 2),
        "final_equity":  round(final_eq, 2),
        "total_return":  round((final_eq - account_size) / account_size * 100, 1),
        "max_drawdown":  round(max_dd, 1),
        "sharpe":        round(sharpe, 2),
        "sortino":       round(sortino, 2),
    }


def buy_and_hold_spy(equity):
    df = fetch_history("SPY", years=YEARS_BACK, extra_days=0)
    if df is None or df.empty:
        return {}
    sp, ep = float(df["close"].iloc[0]), float(df["close"].iloc[-1])
    sh     = int(equity / sp)
    return {
        "pnl":          round((ep - sp) * sh, 2),
        "total_return": round((ep - sp) / sp * 100, 1),
        "final_equity": round(equity + (ep - sp) * sh, 2),
    }


def run_backtest():
    print("=" * 68)
    print("  BACKTEST v3 - Multi-Legend Strategy")
    print("  Couling VPA / Gann / Dalio / Weinstein / Livermore")
    print(f"  Account: ${ACCOUNT_SIZE:,.2f}  |  {YEARS_BACK} yrs  |  {len(ETF_WATCHLIST)} ETFs")
    print("=" * 68)
    print("\n  [1/3] SPY macro regime...")
    spy_regime = build_spy_regime()
    bull_days  = sum(spy_regime.values())
    print(f"        Bullish: {bull_days}/{len(spy_regime)} days")
    print("  [2/3] Dalio regime...")
    dalio_regime = build_dalio_regime()
    print(f"        {len(dalio_regime)} days mapped")
    print("\n  [3/3] Running backtests...\n")
    equity_ref = {"value": ACCOUNT_SIZE}
    all_stock, all_opts = [], []
    for symbol in ETF_WATCHLIST:
        print(f"  {symbol:<6} ...", end=" ", flush=True)
        s_trades, o_trades = backtest_symbol(symbol, spy_regime, dalio_regime, equity_ref)
        all_stock.extend(s_trades)
        all_opts.extend(o_trades)
        sym_pnl = sum(t["pnl"] for t in s_trades) + sum(t["pnl"] for t in o_trades)
        equity_ref["value"] = max(equity_ref["value"] + sym_pnl, 1.0)
        n = len(s_trades)
        w = sum(1 for t in s_trades if t["pnl"] > 0)
        print(f"{n} trades | {w}W/{n-w}L | ${sum(t['pnl'] for t in s_trades):+.2f}")
    if not all_stock:
        print("\n  No trades generated. See README for tuning tips.")
        return
    date_pnl = {}
    for t in all_stock + all_opts:
        date_pnl[t["exit_date"]] = date_pnl.get(t["exit_date"], 0) + t["pnl"]
    eq_rows, running = [], ACCOUNT_SIZE
    for d in sorted(date_pnl):
        running += date_pnl[d]
        eq_rows.append({"date": d, "equity": round(running, 2)})
    pd.DataFrame(eq_rows).to_csv(EQUITY_FILE, index=False)
    pd.DataFrame(all_stock).to_csv(RESULTS_FILE, index=False)
    pd.DataFrame(all_opts).to_csv(OPTIONS_FILE, index=False)
    all_pnls  = [t["pnl"] for t in all_stock]
    eq_vals   = [ACCOUNT_SIZE] + [r["equity"] for r in eq_rows]
    m         = calc_metrics(all_pnls, eq_vals, ACCOUNT_SIZE)
    opt_total = sum(t["pnl"] for t in all_opts)
    bnh       = buy_and_hold_spy(ACCOUNT_SIZE)
    combined  = m["total_pnl"] + opt_total
    combo_ret = combined / ACCOUNT_SIZE * 100
    diff      = combo_ret - bnh.get("total_return", 0)
    verdict   = (f"BEAT buy-and-hold by +{diff:.1f}%" if diff > 0
                 else f"Buy-and-hold beat strategy by {abs(diff):.1f}%")
    print(f"""
  STOCK STRATEGY
  Trades: {m['trades']}  Win rate: {m['win_rate']}%  Profit factor: {m['profit_factor']}
  P&L: ${m['total_pnl']:,.2f}  Return: {m['total_return']}%
  Max drawdown: {m['max_drawdown']}%  Sharpe: {m['sharpe']}  Sortino: {m['sortino']}

  OPTIONS OVERLAY
  Trades: {len(all_opts)}  P&L: ${opt_total:,.2f}

  COMBINED return: {combo_ret:.1f}%  Final equity: ${ACCOUNT_SIZE + combined:,.2f}

  BUY & HOLD SPY: {bnh.get('total_return', 0)}%

  VERDICT: {verdict}
""")
    summary = (
        f"BACKTEST v3\nStock return: {m['total_return']}%\n"
        f"Options P&L: ${opt_total:,.2f}\nCombined: {combo_ret:.1f}%\n"
        f"Sharpe: {m['sharpe']} | Sortino: {m['sortino']}\n"
        f"Max drawdown: {m['max_drawdown']}%\nBuy-hold: {bnh.get('total_return',0)}%\n"
        f"Verdict: {verdict}\n"
    )
    with open(SUMMARY_FILE, "w") as f:
        f.write(summary)
    print(f"  Saved: {RESULTS_FILE}, {OPTIONS_FILE}, {EQUITY_FILE}, {SUMMARY_FILE}")


if __name__ == "__main__":
    run_backtest()
