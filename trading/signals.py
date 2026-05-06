"""
Daily Signal Scanner — same logic as backtest v3
Run this each morning to get today's trade signals.
Output: a table of ETFs with ENTER / WATCH / AVOID ratings.
"""
import os, math, datetime
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SIZE       = float(os.getenv("ACCOUNT_SIZE", 1673.00))
RISK_FREE_RATE     = 0.045
TARGET_VOL_CONTRIB = 0.007
MAX_POS_PCT        = 0.20
OPT_DTE            = 40
OPT_OTM            = 0.02
GANN_LOOKBACK      = 60

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

SIGNAL_FILE = "signals_today.csv"


# ─── Fetch + indicators (last 300 bars is enough for signals) ─────────────────
def fetch(symbol, days=300):
    try:
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=days)
        df    = yf.Ticker(symbol).history(start=start, end=end, interval="1d")
        if df is None or df.empty or len(df) < 60:
            return None
        df.columns = [c.lower() for c in df.columns]
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        return df[cols].copy()
    except Exception as e:
        print(f"  [fetch error] {symbol}: {e}")
        return None


def indicators(df):
    d = df.copy()
    d["sma20"]        = d["close"].rolling(20).mean()
    d["sma50"]        = d["close"].rolling(50).mean()
    d["sma150"]       = d["close"].rolling(150).mean()
    d["sma200"]       = d["close"].rolling(200).mean()
    d["sma150_slope"] = d["sma150"].diff(5)
    d["avg_vol"]      = d["volume"].rolling(20).mean()
    d["vol_ratio"]    = d["volume"] / (d["avg_vol"] + 1e-9)

    atr_raw   = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift(1)).abs(),
        (d["low"]  - d["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    d["atr14"]     = atr_raw.rolling(14).mean()
    d["atr_pct"]   = d["atr14"] / (d["close"] + 1e-9)
    d["spread"]    = (d["high"] - d["low"]) / (d["close"] + 1e-9)
    d["close_pos"] = (d["close"] - d["low"]) / (d["high"] - d["low"] + 1e-9)
    d["dollar_vol"]= d["volume"] * d["close"]
    d["mom20"]     = d["close"].pct_change(20)
    d["mom60"]     = d["close"].pct_change(60)

    delta      = d["close"].diff()
    gain       = delta.clip(lower=0).rolling(14).mean()
    loss       = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    d["pivot_hi"]  = d["high"].rolling(20).max().shift(1)
    d["hist_vol"]  = d["close"].pct_change().rolling(20).std() * math.sqrt(252)
    return d.dropna()


# ─── Couling VPA ──────────────────────────────────────────────────────────────
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
    wide      = spread > atr_pct * 1.0
    narrow    = spread < atr_pct * 0.4
    normal_sp = atr_pct * 0.4 <= spread <= atr_pct * 1.0
    price_move= abs(float(row["close"]) - float(row["open"])) / (float(row["close"]) + 1e-9)
    effort_ok = price_move > atr_pct * 0.35

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
    if mod_high and normal_sp and cp > 0.65:
        return "BULLISH_CONFIRMATION", "BULL"
    return "NORMAL", "NEUTRAL"


# ─── Gann ─────────────────────────────────────────────────────────────────────
def gann_angle_ok(df):
    closes      = df["close"].values
    sw_slice    = closes[-GANN_LOOKBACK:]
    sw_rel      = int(sw_slice.argmin())
    sw_price    = float(sw_slice[sw_rel])
    bars_since  = len(sw_slice) - 1 - sw_rel
    angle_level = sw_price * (1 + 0.001 * bars_since)
    return float(closes[-1]) >= angle_level, round(angle_level, 2)


def gann_sq9_targets(price):
    root = math.sqrt(max(price, 0.01))
    return round((root + 0.5) ** 2, 2), round((root + 1.0) ** 2, 2)


# ─── Weinstein Stage 2 ────────────────────────────────────────────────────────
def weinstein_stage2(row):
    return (float(row["close"]) > float(row["sma150"])) and (float(row["sma150_slope"]) > 0)


# ─── Livermore breakout ───────────────────────────────────────────────────────
def livermore_ok(prev, prev_prev):
    return (float(prev["close"]) > float(prev_prev["pivot_hi"]) and
            float(prev["vol_ratio"]) > 1.05)


# ─── Dalio regime ─────────────────────────────────────────────────────────────
def get_dalio_regime():
    spy_df = fetch("SPY")
    tlt_df = fetch("TLT")
    if spy_df is None or tlt_df is None:
        return "UNKNOWN"
    spy_roc = float(spy_df["close"].pct_change(60).iloc[-1])
    tlt_roc = float(tlt_df["close"].pct_change(60).iloc[-1])
    growth    = spy_roc > 0
    inflation = tlt_roc < 0
    if growth and not inflation:   return "GROWTH_DEFLATION"
    if growth and inflation:       return "GROWTH_INFLATION"
    if not growth and not inflation: return "RECESSION_DEFLATION"
    return "RECESSION_INFLATION"


# ─── Options pricer ───────────────────────────────────────────────────────────
def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)


def call_premium(price, vol):
    K  = price * (1 + OPT_OTM)
    T  = OPT_DTE / 252
    px = bs_call(price, K, T, RISK_FREE_RATE, max(vol, 0.10))
    return round(px, 2), round(K, 2)


# ─── SPY macro check ──────────────────────────────────────────────────────────
def spy_is_bullish():
    df = fetch("SPY")
    if df is None:
        return False
    df = indicators(df)
    return bool(df["close"].iloc[-1] > df["sma200"].iloc[-1])


# ─── Main scanner ─────────────────────────────────────────────────────────────
def scan():
    today = datetime.date.today().isoformat()
    print("=" * 72)
    print(f"  DAILY SIGNAL SCAN  —  {today}")
    print(f"  Strategy: Couling VPA · Gann · Dalio · Weinstein · Livermore")
    print("=" * 72)

    print("\n  Checking macro conditions...")
    bull_market = spy_is_bullish()
    regime      = get_dalio_regime()
    print(f"  SPY vs 200-SMA:  {'BULLISH ✓' if bull_market else 'BEARISH — no longs today'}")
    print(f"  Dalio regime:    {regime}")
    print(f"  Preferred ETFs:  {', '.join(REGIME_ETFS.get(regime, ['ALL']))}\n")

    results = []

    for symbol in ETF_WATCHLIST:
        df = fetch(symbol)
        if df is None or len(df) < 60:
            continue
        df = indicators(df)
        if len(df) < 3:
            continue

        row       = df.iloc[-1]
        prev      = df.iloc[-2]
        prev_prev = df.iloc[-3]
        price     = float(row["close"])

        # Run all checks
        vpa_sig, vpa_sent = couling_vpa(prev, prev_prev)
        stage2    = weinstein_stage2(prev)
        liv_ok    = livermore_ok(prev, prev_prev)
        angle_ok, angle_lvl = gann_angle_ok(df)
        regime_ok = symbol in REGIME_ETFS.get(regime, ETF_WATCHLIST)
        mom_ok    = float(prev["mom20"]) > 0 and float(prev["mom60"]) > 0
        rsi       = float(prev["rsi14"])
        rsi_ok    = 35 <= rsi <= 72

        # Count how many gates pass
        gates = [bull_market, regime_ok, stage2, vpa_sent == "BULL",
                 angle_ok, liv_ok, mom_ok, rsi_ok]
        score = sum(gates)

        # Entry signal: ALL gates must pass
        entry = all(gates)

        # Position sizing if entering
        atr   = float(prev["atr14"])
        stop  = round(price - 2.0 * atr, 2)
        shares = 0
        opt_contracts = 0
        opt_px = 0.0
        opt_strike = 0.0
        if entry and atr > 0:
            by_vol  = int((ACCOUNT_SIZE * TARGET_VOL_CONTRIB) / atr)
            by_cap  = int((ACCOUNT_SIZE * MAX_POS_PCT) / price)
            shares  = max(min(by_vol, by_cap), 0)
            vol     = float(prev["hist_vol"])
            opt_px, opt_strike = call_premium(price, vol)
            budget  = ACCOUNT_SIZE * 0.015
            opt_contracts = int(budget / ((opt_px + 0.05) * 100 + 1e-9))

        r1, r2 = gann_sq9_targets(price)
        target1 = round(max(r1, price * 1.03), 2)
        target2 = round(max(r2, price * 1.06), 2)

        # Signal label
        if entry:
            signal = "★ ENTER"
        elif score >= 6:
            signal = "◆ WATCH"
        elif vpa_sent == "BEAR":
            signal = "✕ AVOID (bearish VPA)"
        else:
            signal = "– SKIP"

        results.append({
            "symbol":    symbol,
            "signal":    signal,
            "score":     f"{score}/8",
            "price":     round(price, 2),
            "vpa":       vpa_sig,
            "stage2":    "✓" if stage2 else "✗",
            "gann_angle":"✓" if angle_ok else "✗",
            "livermore": "✓" if liv_ok else "✗",
            "regime":    "✓" if regime_ok else "✗",
            "rsi":       round(rsi, 1),
            "stop":      stop,
            "target1":   target1,
            "target2":   target2,
            "shares":    shares if entry else 0,
            "opt_contracts": opt_contracts if entry else 0,
            "opt_strike":    opt_strike if entry else 0,
            "opt_premium":   opt_px if entry else 0,
            "entry":     entry,
        })

    # Sort: ENTER first, then by score
    results.sort(key=lambda r: (0 if r["entry"] else 1, -int(r["score"].split("/")[0])))

    # Print signal table
    enter = [r for r in results if r["entry"]]
    watch = [r for r in results if r["signal"].startswith("◆")]

    if enter:
        print("  ┌─ ENTER SIGNALS ──────────────────────────────────────────────────┐")
        for r in enter:
            print(f"  │  {r['symbol']:<5}  ${r['price']:>7.2f}  VPA: {r['vpa']:<22} RSI:{r['rsi']:>5.1f}")
            print(f"  │         Stop: ${r['stop']:<8}  T1: ${r['target1']:<8}  T2: ${r['target2']:<8}")
            if r["shares"] > 0:
                cost = r["shares"] * r["price"]
                print(f"  │         Shares: {r['shares']}  Cost: ${cost:,.2f}  Risk: ${round((r['price']-r['stop'])*r['shares'],2)}")
            if r["opt_contracts"] > 0:
                print(f"  │         Options: {r['opt_contracts']} call contract(s) @ ${r['opt_premium']} "
                      f"(strike ${r['opt_strike']})")
        print("  └──────────────────────────────────────────────────────────────────┘\n")
    else:
        print("  No ENTER signals today.\n")

    if watch:
        print("  ◆ WATCH (6-7/8 gates pass — set alert):")
        for r in watch:
            missing = []
            if not (35 <= r["rsi"] <= 72): missing.append("RSI")
            if r["stage2"] == "✗":         missing.append("Stage2")
            if r["gann_angle"] == "✗":     missing.append("Gann")
            if r["livermore"] == "✗":      missing.append("Livermore")
            if r["vpa"] not in ("NO_SUPPLY","TEST_OF_SUPPLY","STOPPING_VOLUME","BULLISH_CONFIRMATION"):
                missing.append("VPA")
            print(f"     {r['symbol']:<5} ${r['price']:>7.2f}  Score:{r['score']}  "
                  f"Missing: {', '.join(missing) or 'none'}")
        print()

    # Avoid list
    avoid = [r for r in results if "AVOID" in r["signal"]]
    if avoid:
        print(f"  ✕ AVOID (bearish VPA): {', '.join(r['symbol'] for r in avoid)}\n")

    # Full scan table
    print(f"  {'SYM':<5} {'SIGNAL':<22} {'SCORE':>5}  {'VPA':<22} {'S2':>2} {'Gann':>4} {'Liv':>3} {'Reg':>3} {'RSI':>5}")
    print("  " + "─" * 72)
    for r in results:
        print(f"  {r['symbol']:<5} {r['signal']:<22} {r['score']:>5}  "
              f"{r['vpa']:<22} {r['stage2']:>2} {r['gann_angle']:>4} "
              f"{r['livermore']:>3} {r['regime']:>3} {r['rsi']:>5.1f}")

    # Save CSV
    pd.DataFrame(results).to_csv(SIGNAL_FILE, index=False)
    print(f"\n  Saved: {SIGNAL_FILE}")

    # Summary for posting
    print("\n" + "=" * 72)
    print(f"  DAILY SIGNAL SUMMARY  —  {today}")
    print(f"  Regime: {regime}  |  Market: {'BULL' if bull_market else 'BEAR'}")
    print("=" * 72)
    if enter:
        for r in enter:
            risk_per_share = round(r["price"] - r["stop"], 2)
            rr = round((r["target2"] - r["price"]) / (risk_per_share + 1e-9), 1)
            print(f"  BUY  {r['symbol']:<5}  @ ${r['price']}  "
                  f"Stop: ${r['stop']}  T1: ${r['target1']}  T2: ${r['target2']}  "
                  f"R:R {rr}:1  ({r['shares']} shares)")
            if r["opt_contracts"] > 0:
                print(f"       + {r['opt_contracts']} call @ ${r['opt_premium']} "
                      f"strike ${r['opt_strike']}")
    else:
        print("  No signals today. Cash is a position.")
    print("=" * 72)


if __name__ == "__main__":
    scan()
