"""
Daily Signal Scanner - run each morning for today's trade signals.
Same 8-gate strategy as backtest v3.
"""
import os, math, datetime
import pandas as pd
from dotenv import load_dotenv
from schwab_client import fetch_history, fetch_quote, get_account_balance

load_dotenv()

_env_size    = os.getenv("ACCOUNT_SIZE")
ACCOUNT_SIZE = float(_env_size) if _env_size else (get_account_balance() or 1673.00)
RISK_FREE_RATE     = 0.045
TARGET_VOL_CONTRIB = 0.007
MAX_POS_PCT        = 0.20
OPT_DTE            = 40
OPT_OTM            = 0.02
GANN_LOOKBACK      = 60
SIGNAL_FILE        = "signals_today.csv"

ETF_WATCHLIST = [
    "SPY", "QQQ", "IWM", "VTI",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLRE",
    "GLD", "SLV", "TLT", "HYG", "ARKK", "SMH", "IBB", "EEM", "EFA",
]

REGIME_ETFS = {
    "GROWTH_DEFLATION":    ["QQQ","XLK","SPY","VTI","IWM","XLY","SMH","IBB","XLC","XLF","ARKK","EFA"],
    "GROWTH_INFLATION":    ["GLD","SLV","XLE","XLB","XLI","EEM","EFA","SMH","IBB","XLF"],
    "RECESSION_DEFLATION": ["TLT","GLD","XLV","XLP","XLRE","HYG","EFA"],
    "RECESSION_INFLATION": ["GLD","SLV","XLE","TLT","XLV","XLP","XLB"],
}


def fetch(symbol, days=300):
    return fetch_history(symbol, years=max(days // 365, 1), extra_days=days % 365)


def indicators(df):
    d = df.copy()
    d["sma20"]        = d["close"].rolling(20).mean()
    d["sma50"]        = d["close"].rolling(50).mean()
    d["sma150"]       = d["close"].rolling(150).mean()
    d["sma200"]       = d["close"].rolling(200).mean()
    d["sma150_slope"] = d["sma150"].diff(5)
    d["avg_vol"]      = d["volume"].rolling(20).mean()
    d["vol_ratio"]    = d["volume"] / (d["avg_vol"] + 1e-9)
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
    d["mom20"]     = d["close"].pct_change(20)
    d["mom60"]     = d["close"].pct_change(60)
    delta      = d["close"].diff()
    gain       = delta.clip(lower=0).rolling(14).mean()
    loss       = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    d["pivot_hi"]  = d["high"].rolling(20).max().shift(1)
    d["hist_vol"]  = d["close"].pct_change().rolling(20).std() * math.sqrt(252)
    return d.dropna()


def couling_vpa(row, prev):
    if row["dollar_vol"] < 50_000_000:
        return "LOW_LIQUIDITY", "NEUTRAL"
    atr_pct   = max(float(row["atr_pct"]), 0.01)
    spread, cp, vr = float(row["spread"]), float(row["close_pos"]), float(row["vol_ratio"])
    very_high = vr > 2.0; high_vol = vr > 1.5; mod_high = 1.1 < vr <= 1.5
    low_vol   = vr < 0.75; very_low = vr < 0.50
    wide = spread > atr_pct; narrow = spread < atr_pct * 0.4
    normal_sp = atr_pct * 0.4 <= spread <= atr_pct
    price_move = abs(float(row["close"]) - float(row["open"])) / (float(row["close"]) + 1e-9)
    effort_ok  = price_move > atr_pct * 0.35
    if (high_vol or very_high) and not effort_ok:
        return ("EFFORT_NO_RESULT_UP" if cp > 0.55 else "EFFORT_NO_RESULT_DOWN"), "NEUTRAL"
    if (high_vol or very_high) and wide and cp < 0.35 and float(prev["close"]) > float(prev["sma20"]):
        return "UPTHRUST", "BEAR"
    if mod_high and wide and cp < 0.40: return "PSEUDO_UPTHRUST", "BEAR"
    if low_vol and narrow and cp < 0.50: return "NO_DEMAND", "BEAR"
    if very_high and wide and cp < 0.30: return "BUYING_CLIMAX", "BEAR"
    if low_vol and narrow and cp > 0.55: return "NO_SUPPLY", "BULL"
    if very_low and cp > 0.60 and float(prev["vol_ratio"]) >= 0.9: return "TEST_OF_SUPPLY", "BULL"
    if (high_vol or very_high) and wide and cp > 0.65: return "STOPPING_VOLUME", "BULL"
    if mod_high and normal_sp and cp > 0.65: return "BULLISH_CONFIRMATION", "BULL"
    return "NORMAL", "NEUTRAL"


def gann_angle_ok(df):
    closes = df["close"].values
    sw = closes[-GANN_LOOKBACK:]
    rel = int(sw.argmin())
    angle = sw[rel] * (1 + 0.001 * (len(sw) - 1 - rel))
    return float(closes[-1]) >= angle, round(angle, 2)


def gann_sq9_targets(price):
    root = math.sqrt(max(price, 0.01))
    return round((root + 0.5) ** 2, 2), round((root + 1.0) ** 2, 2)


def weinstein_stage2(row):
    return float(row["close"]) > float(row["sma150"]) and float(row["sma150_slope"]) > 0


def livermore_ok(prev, prev_prev):
    return float(prev["close"]) > float(prev_prev["pivot_hi"]) and float(prev["vol_ratio"]) > 1.05


def get_dalio_regime():
    spy_df = fetch_history("SPY", years=1, extra_days=120)
    tlt_df = fetch_history("TLT", years=1, extra_days=120)
    if spy_df is None or tlt_df is None: return "UNKNOWN"
    spy_roc = float(spy_df["close"].pct_change(60).iloc[-1])
    tlt_roc = float(tlt_df["close"].pct_change(60).iloc[-1])
    growth = spy_roc > 0; inflation = tlt_roc < 0
    if growth and not inflation:   return "GROWTH_DEFLATION"
    if growth and inflation:       return "GROWTH_INFLATION"
    if not growth and not inflation: return "RECESSION_DEFLATION"
    return "RECESSION_INFLATION"


def _ncdf(x): return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def bs_call(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0: return max(S - K, 0.0)
    d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
    return S*_ncdf(d1) - K*math.exp(-r*T)*_ncdf(d1 - sigma*math.sqrt(T))

def call_premium(price, vol):
    K = price*(1+OPT_OTM); T = OPT_DTE/252
    return round(bs_call(price, K, T, RISK_FREE_RATE, max(vol, 0.10)), 2), round(K, 2)


def spy_is_bullish():
    df = fetch_history("SPY", years=2, extra_days=60)
    if df is None: return False
    df = indicators(df)
    return bool(df["close"].iloc[-1] > df["sma200"].iloc[-1])


def scan():
    today = datetime.date.today().isoformat()
    print("=" * 72)
    print(f"  DAILY SIGNAL SCAN  -  {today}")
    print(f"  Couling VPA / Gann / Dalio / Weinstein / Livermore")
    print("=" * 72)
    bull_market = spy_is_bullish()
    regime      = get_dalio_regime()
    print(f"\n  SPY: {'BULLISH' if bull_market else 'BEARISH - no longs today'}")
    print(f"  Dalio regime: {regime}")
    print(f"  Preferred: {', '.join(REGIME_ETFS.get(regime, ['ALL']))}\n")
    results = []
    for symbol in ETF_WATCHLIST:
        df = fetch(symbol)
        if df is None or len(df) < 60: continue
        df = indicators(df)
        if len(df) < 3: continue
        row, prev, prev_prev = df.iloc[-1], df.iloc[-2], df.iloc[-3]
        price = float(row["close"])
        vpa_sig, vpa_sent = couling_vpa(prev, prev_prev)
        stage2     = weinstein_stage2(prev)
        liv        = livermore_ok(prev, prev_prev)
        angle_ok, angle_lvl = gann_angle_ok(df)
        regime_ok  = symbol in REGIME_ETFS.get(regime, ETF_WATCHLIST)
        mom_ok     = float(prev["mom20"]) > 0 and float(prev["mom60"]) > 0
        rsi        = float(prev["rsi14"])
        rsi_ok     = 35 <= rsi <= 72
        gates      = [bull_market, regime_ok, stage2, vpa_sent=="BULL", angle_ok, liv, mom_ok, rsi_ok]
        score      = sum(gates)
        entry      = all(gates)
        atr        = float(prev["atr14"])
        stop       = round(price - 2.0 * atr, 2)
        shares = opt_contracts = 0; opt_px = opt_strike = 0.0
        if entry and atr > 0:
            shares = max(min(int((ACCOUNT_SIZE*TARGET_VOL_CONTRIB)/atr),
                             int((ACCOUNT_SIZE*MAX_POS_PCT)/price)), 0)
            opt_px, opt_strike = call_premium(price, float(prev["hist_vol"]))
            opt_contracts = int((ACCOUNT_SIZE*0.015) / ((opt_px+0.05)*100 + 1e-9))
        r1, r2   = gann_sq9_targets(price)
        target1  = round(max(r1, price*1.03), 2)
        target2  = round(max(r2, price*1.06), 2)
        signal   = "ENTER" if entry else ("WATCH" if score >= 6 else
                   ("AVOID" if vpa_sent=="BEAR" else "SKIP"))
        results.append({
            "signal": signal, "symbol": symbol, "score": f"{score}/8",
            "price": round(price,2), "vpa": vpa_sig,
            "stage2": stage2, "gann": angle_ok, "liv": liv,
            "regime": regime_ok, "rsi": round(rsi,1),
            "stop": stop, "target1": target1, "target2": target2,
            "shares": shares, "opt_contracts": opt_contracts,
            "opt_strike": opt_strike, "opt_premium": opt_px, "entry": entry,
        })
    results.sort(key=lambda r: (0 if r["entry"] else 1, -int(r["score"].split("/")[0])))
    enter = [r for r in results if r["entry"]]
    print("=" * 72)
    print(f"  SIGNAL SUMMARY  -  {today}  |  {regime}  |  {'BULL' if bull_market else 'BEAR'}")
    print("=" * 72)
    if enter:
        for r in enter:
            rr = round((r["target2"]-r["price"]) / (r["price"]-r["stop"]+1e-9), 1)
            print(f"  BUY {r['symbol']:<5} @ ${r['price']}  Stop:${r['stop']}  "
                  f"T1:${r['target1']}  T2:${r['target2']}  R:R {rr}:1")
            if r["shares"] > 0:
                print(f"       {r['shares']} shares  Cost:${round(r['shares']*r['price'],2)}  "
                      f"Risk:${round((r['price']-r['stop'])*r['shares'],2)}")
            if r["opt_contracts"] > 0:
                print(f"       + {r['opt_contracts']} call @ ${r['opt_premium']} strike ${r['opt_strike']}")
    else:
        print("  No signals today. Cash is a position.")
    print("\n  Full scan:")
    print(f"  {'SYM':<5} {'SIG':<6} {'SCORE':>5}  {'VPA':<22} {'RSI':>5}")
    print("  " + "-"*50)
    for r in results:
        print(f"  {r['symbol']:<5} {r['signal']:<6} {r['score']:>5}  {r['vpa']:<22} {r['rsi']:>5.1f}")
    pd.DataFrame(results).to_csv(SIGNAL_FILE, index=False)
    print(f"\n  Saved: {SIGNAL_FILE}")


if __name__ == "__main__":
    scan()
