"""
Backtest v3 — Multi-Legend Strategy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Anna Couling  — Full VPA taxonomy (Upthrust, Test of Supply, Effort vs Result,
                No Supply, No Demand, Stopping Volume, Buying Climax)
W.D. Gann     — 1×1 angle (ATR-normalised), Square of 9 targets, time cycles
Ray Dalio     — Risk-parity position sizing, 4-quadrant growth/inflation regime
Stan Weinstein— Stage 2 filter (30-week SMA rising + price above it)
Jesse Livermore— Pivotal-point breakout (20-bar swing high break + volume confirm)

Risk objective: minimise drawdown first, then maximise Sharpe.
"""
import os, math, datetime
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
ACCOUNT_SIZE       = float(os.getenv("ACCOUNT_SIZE", 1673.00))
YEARS_BACK         = 7
SLIPPAGE           = 0.03     # $ per share, both sides
OPTION_SLIP        = 0.05     # $ per share on options premium
RISK_FREE_RATE     = 0.045    # ~4.5% (approx 10yr Treasury)
TARGET_VOL_CONTRIB = 0.007    # Dalio risk-parity: 0.7% daily vol per position
MAX_POS_PCT        = 0.20     # hard cap: 20% of equity per trade
OPTION_RISK        = 0.015    # 1.5% of equity per options trade
OPT_DTE            = 40
OPT_OTM            = 0.02
GANN_LOOKBACK      = 60       # bars to look back for rolling swing low
SWING_WINDOW       = 10       # bars each side for swing detection

RESULTS_FILE = "backtest_results.csv"
OPTIONS_FILE = "options_results.csv"
EQUITY_FILE  = "equity_curve.csv"
SUMMARY_FILE = "backtest_summary.txt"

ETF_WATCHLIST = [
    "SPY", "QQQ", "IWM", "VTI",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLRE",
    "GLD", "SLV", "TLT", "HYG", "ARKK", "SMH", "IBB", "EEM", "EFA",
]

# Dalio All-Weather: which ETFs to trade in each macro quadrant
REGIME_ETFS = {
    "GROWTH_DEFLATION":    ["QQQ", "XLK", "SPY", "VTI", "IWM", "XLY", "SMH",
                            "IBB", "XLC", "XLF", "ARKK", "EFA"],
    "GROWTH_INFLATION":    ["GLD", "SLV", "XLE", "XLB", "XLI", "EEM", "EFA",
                            "SMH", "IBB", "XLF"],
    "RECESSION_DEFLATION": ["TLT", "GLD", "XLV", "XLP", "XLRE", "HYG", "EFA"],
    "RECESSION_INFLATION": ["GLD", "SLV", "XLE", "TLT", "XLV", "XLP", "XLB"],
}


# ─── Data ─────────────────────────────────────────────────────────────────────
def fetch_history(symbol, extra_days=300):
    try:
        end   = datetime.date.today()
        start = end - datetime.timedelta(days=365 * YEARS_BACK + extra_days)
        df    = yf.Ticker(symbol).history(start=start, end=end, interval="1d")
        if df is None or df.empty or len(df) < 250:
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
    # Trend SMAs
    d["sma20"]        = d["close"].rolling(20).mean()
    d["sma50"]        = d["close"].rolling(50).mean()
    d["sma150"]       = d["close"].rolling(150).mean()   # Weinstein 30-week
    d["sma200"]       = d["close"].rolling(200).mean()
    d["sma150_slope"] = d["sma150"].diff(5)              # positive = rising

    # Volume
    d["avg_vol"]   = d["volume"].rolling(20).mean()
    d["vol_ratio"] = d["volume"] / (d["avg_vol"] + 1e-9)

    # Candle anatomy (all relative to price so they work across all ETF price levels)
    atr_raw       = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift(1)).abs(),
        (d["low"]  - d["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    d["atr14"]     = atr_raw.rolling(14).mean()
    d["atr_pct"]   = d["atr14"] / (d["close"] + 1e-9)   # ATR as fraction of price
    d["spread"]    = (d["high"] - d["low"]) / (d["close"] + 1e-9)
    d["close_pos"] = (d["close"] - d["low"]) / (d["high"] - d["low"] + 1e-9)
    d["dollar_vol"]= d["volume"] * d["close"]

    # Momentum
    d["mom10"] = d["close"].pct_change(10)
    d["mom20"] = d["close"].pct_change(20)
    d["mom60"] = d["close"].pct_change(60)

    # RSI 14
    delta      = d["close"].diff()
    gain       = delta.clip(lower=0).rolling(14).mean()
    loss       = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - (100 / (1 + gain / (loss + 1e-9)))

    # Livermore: 20-bar rolling swing high (of highs, shifted 1 bar back)
    d["pivot_hi"] = d["high"].rolling(20).max().shift(1)

    # Historical vol annualised (for options pricing)
    d["hist_vol"] = d["close"].pct_change().rolling(20).std() * math.sqrt(252)

    return d.dropna()


# ═══════════════════════════════════════════════════════════════════════════════
# ANNA COULING — Full VPA Taxonomy
# Reference: "A Complete Guide to Volume Price Analysis" (2013)
# ═══════════════════════════════════════════════════════════════════════════════
def couling_vpa(row, prev):
    """
    Classify a bar using Couling's full VPA taxonomy.
    All spread/volume comparisons are relative to ATR and average volume
    so they work across all price levels without hard-coded thresholds.

    Returns (signal_name, sentiment):  sentiment ∈ {'BULL', 'BEAR', 'NEUTRAL'}
    """
    if row["dollar_vol"] < 50_000_000:
        return "LOW_LIQUIDITY", "NEUTRAL"

    atr_pct = float(row["atr_pct"]) if row["atr_pct"] > 0 else 0.01
    spread  = float(row["spread"])
    cp      = float(row["close_pos"])
    vr      = float(row["vol_ratio"])

    # Volume tiers
    very_high = vr > 2.0
    high_vol  = vr > 1.5
    mod_high  = 1.1 < vr <= 1.5
    low_vol   = vr < 0.75
    very_low  = vr < 0.50

    # Spread tiers (relative to current ATR)
    wide   = spread > atr_pct * 1.0    # wider than 1 ATR
    normal_spread = atr_pct * 0.4 <= spread <= atr_pct * 1.0
    narrow = spread < atr_pct * 0.4   # much narrower than normal

    # Body vs range — price move vs effort
    price_move   = abs(float(row["close"]) - float(row["open"])) / (float(row["close"]) + 1e-9)
    effort_ok    = price_move > atr_pct * 0.35   # meaningful move relative to ATR

    # ── Effort vs Result (Couling divergence) ─────────────────────────────
    # High volume + tiny price move = trapped bulls/bears, no result for effort
    if (high_vol or very_high) and not effort_ok:
        # Sentiment depends on where price closed in the range
        if cp > 0.55:
            return "EFFORT_NO_RESULT_UP", "NEUTRAL"   # absorption — watch next bar
        return "EFFORT_NO_RESULT_DOWN", "NEUTRAL"

    # ── BEARISH signals ───────────────────────────────────────────────────

    # Upthrust — Couling's primary reversal warning
    # High volume, wide spread, but close NEAR THE BOTTOM (sellers overwhelming buyers)
    # Context: price was previously above SMA20 (in an uptrend)
    if (high_vol or very_high) and wide and cp < 0.35:
        if float(prev["close"]) > float(prev["sma20"]):
            return "UPTHRUST", "BEAR"

    # Pseudo-Upthrust — lower volume version, still bearish
    if mod_high and wide and cp < 0.40:
        return "PSEUDO_UPTHRUST", "BEAR"

    # No Demand — market not interested in rising; buyers absent
    # Low volume, narrow spread, closes in lower half of range
    if low_vol and narrow and cp < 0.50:
        return "NO_DEMAND", "BEAR"

    # Buying Climax — distribution into retail buying
    # Very high volume, wide spread, close near low (smart money selling)
    if very_high and wide and cp < 0.30:
        return "BUYING_CLIMAX", "BEAR"

    # ── BULLISH signals ───────────────────────────────────────────────────

    # No Supply — sellers absent; market poised to rise
    # Low volume, narrow spread, close in upper half of range
    if low_vol and narrow and cp > 0.55:
        return "NO_SUPPLY", "BULL"

    # Test of Supply — ultra-low volume probe that finds no resistance
    # Price dips but recovers to close near top; prior bar had normal+ volume
    # (tests that the prior high-volume bar absorbed all the supply)
    if very_low and cp > 0.60 and float(prev["vol_ratio"]) >= 0.9:
        return "TEST_OF_SUPPLY", "BULL"

    # Stopping Volume — massive buying halts a decline; demand overwhelms supply
    # High volume, wide spread, price closes in upper 65%+ of the bar
    if (high_vol or very_high) and wide and cp > 0.65:
        return "STOPPING_VOLUME", "BULL"

    # Moderate bullish: normal+ volume, above average spread, closes high
    if mod_high and normal_spread and cp > 0.65:
        return "BULLISH_CONFIRMATION", "BULL"

    return "NORMAL", "NEUTRAL"


# ═══════════════════════════════════════════════════════════════════════════════
# W.D. GANN — Angles, Square of 9, Time Cycles
# ═══════════════════════════════════════════════════════════════════════════════
def gann_1x1_bullish(close, bar_idx, swing_low_price, swing_low_idx):
    """
    Gann 1×1 angle: price should advance at 0.1% per bar from the swing low.
    0.1%/bar ≈ 25% annualised — represents a healthy uptrend.
    If price is below the angle, the uptrend has stalled.
    """
    bars = bar_idx - swing_low_idx
    if bars <= 0:
        return True
    angle_level = swing_low_price * (1 + 0.001 * bars)
    return close >= angle_level


def gann_sq9_targets(entry_price):
    """
    Square of 9: resistance levels above entry price.
    Method: sqrt(price) + 0.5, +1.0, +2.0 → re-squared.
    These act as natural price targets and S/R levels.
    Returns (r1, r2) as price targets.
    """
    root = math.sqrt(max(entry_price, 0.01))
    r1   = (root + 0.5) ** 2
    r2   = (root + 1.0) ** 2
    return round(r1, 2), round(r2, 2)


def find_confirmed_swings(df):
    """
    Find swing lows confirmed by SWING_WINDOW bars on each side.
    Returns list of integer bar positions (no future data leakage:
    a swing at position i is only usable at position i+SWING_WINDOW).
    """
    closes  = df["close"].values
    swings  = []
    w       = SWING_WINDOW
    for i in range(w, len(closes) - w):
        window = closes[i - w: i + w + 1]
        if closes[i] == window.min():
            swings.append(i)
    return swings


def is_gann_time_cycle(bar_idx, confirmed_swings, tolerance=5):
    """
    True if current bar is within ±tolerance bars of a Gann cycle date
    (90, 180, or 360 bars from any confirmed past swing).
    Only uses swings that are fully confirmed (swing_idx + SWING_WINDOW < bar_idx).
    """
    for s in confirmed_swings:
        if s + SWING_WINDOW >= bar_idx:
            continue                    # swing not yet confirmed
        for cycle in (90, 180, 360):
            if abs(bar_idx - (s + cycle)) <= tolerance:
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# STAN WEINSTEIN — Stage Analysis
# Reference: "Secrets for Profiting in Bull and Bear Markets" (1988)
# ═══════════════════════════════════════════════════════════════════════════════
def is_weinstein_stage2(row):
    """
    Stage 2 (advancing phase):
      • Price above the 30-week (≈150-day) SMA
      • 30-week SMA slope is positive (rising)
    Avoids dead-money sideways and declining stages.
    """
    return (float(row["close"]) > float(row["sma150"])) and (float(row["sma150_slope"]) > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# JESSE LIVERMORE — Pivotal Point Breakout
# Reference: "How to Trade in Stocks" (1940)
# ═══════════════════════════════════════════════════════════════════════════════
def is_livermore_breakout(prev, prev_prev):
    """
    Livermore only entered AFTER price convincingly broke a prior pivotal point.
    Here: prev bar's close > the 20-bar swing high as of prev_prev bar,
    confirmed by above-average volume on prev bar.
    Using prev/prev_prev avoids any look-ahead (entry is at today's open).
    """
    above_pivot     = float(prev["close"]) > float(prev_prev["pivot_hi"])
    volume_confirms = float(prev["vol_ratio"]) > 1.05
    return above_pivot and volume_confirms


# ═══════════════════════════════════════════════════════════════════════════════
# RAY DALIO — Risk Parity + Macro Regime
# Reference: Bridgewater All Weather, "Principles" (2017)
# ═══════════════════════════════════════════════════════════════════════════════
def build_dalio_regime():
    """
    Growth proxy:    SPY 60-day ROC  (positive = growing economy)
    Inflation proxy: TLT 60-day ROC  (negative = rising inflation → bonds fall)
    Returns dict: date → regime string (one of four quadrants).
    """
    spy_df = fetch_history("SPY", extra_days=300)
    tlt_df = fetch_history("TLT", extra_days=300)
    if spy_df is None or tlt_df is None:
        return {}

    spy_roc = spy_df["close"].pct_change(60)
    tlt_roc = tlt_df["close"].pct_change(60)

    spy_by_date = {d.date(): v for d, v in spy_roc.items() if not math.isnan(v)}
    tlt_by_date = {d.date(): v for d, v in tlt_roc.items() if not math.isnan(v)}

    regime = {}
    for d in set(spy_by_date) & set(tlt_by_date):
        growth    = spy_by_date[d] > 0
        inflation = tlt_by_date[d] < 0    # falling TLT = rising inflation
        if growth and not inflation:
            regime[d] = "GROWTH_DEFLATION"
        elif growth and inflation:
            regime[d] = "GROWTH_INFLATION"
        elif not growth and not inflation:
            regime[d] = "RECESSION_DEFLATION"
        else:
            regime[d] = "RECESSION_INFLATION"
    return regime


def etf_fits_regime(symbol, regime_str):
    """True if this ETF is preferred in the current Dalio regime."""
    if not regime_str:
        return True
    return symbol in REGIME_ETFS.get(regime_str, [])


def size_riskparity(equity, atr, price):
    """
    Dalio risk parity: each position contributes TARGET_VOL_CONTRIB of
    daily portfolio volatility.  shares = (equity × target_vol) / ATR.
    Hard-capped at MAX_POS_PCT of equity.
    """
    if atr <= 0 or price <= 0:
        return 0
    by_vol = int((equity * TARGET_VOL_CONTRIB) / atr)
    by_cap = int((equity * MAX_POS_PCT) / price)
    return max(min(by_vol, by_cap), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# SPY MACRO REGIME (bull / bear market filter)
# ═══════════════════════════════════════════════════════════════════════════════
def build_spy_regime():
    """date → bool: True = SPY above 200-day SMA (macro bull market)."""
    df = fetch_history("SPY", extra_days=300)
    if df is None:
        return {}
    df = compute_indicators(df)
    return {idx.date(): bool(row["close"] > row["sma200"]) for idx, row in df.iterrows()}


# ═══════════════════════════════════════════════════════════════════════════════
# MASTER ENTRY GATE — all frameworks combined
# ═══════════════════════════════════════════════════════════════════════════════
BULLISH_VPA = {"NO_SUPPLY", "TEST_OF_SUPPLY", "STOPPING_VOLUME", "BULLISH_CONFIRMATION"}
BEARISH_VPA = {"UPTHRUST", "PSEUDO_UPTHRUST", "BUYING_CLIMAX", "NO_DEMAND"}


def should_enter(prev, prev_prev, spy_bullish, dalio_regime, symbol,
                 bar_idx, swing_low_price, swing_low_idx, confirmed_swings):
    """
    All six frameworks must agree before entering a trade.
    Signals are checked on the *previous* bar — entry is at next open.
    """
    # 1. SPY macro regime (Weinstein/Dalio macro overlay)
    if not spy_bullish:
        return False

    # 2. Dalio regime compatibility
    if not etf_fits_regime(symbol, dalio_regime):
        return False

    # 3. Weinstein Stage 2 — only trade advancing ETFs
    if not is_weinstein_stage2(prev):
        return False

    # 4. Couling VPA — require a confirmed bullish signal
    sig, sentiment = couling_vpa(prev, prev_prev)
    if sentiment != "BULL":
        return False

    # 5. Gann 1×1 angle — price in healthy uptrend from swing low
    if not gann_1x1_bullish(float(prev["close"]), bar_idx - 1,
                             swing_low_price, swing_low_idx):
        return False

    # 6. Livermore pivotal breakout — prev bar broke above prior swing high w/ volume
    if not is_livermore_breakout(prev, prev_prev):
        return False

    # 7. Dual momentum (multi-timeframe confirmation)
    if float(prev["mom20"]) <= 0 or float(prev["mom60"]) <= 0:
        return False

    # 8. RSI — avoid overbought and deeply oversold entries
    if not (35 <= float(prev["rsi14"]) <= 72):
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES (no scipy dependency)
# ═══════════════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE-SYMBOL BACKTEST
# ═══════════════════════════════════════════════════════════════════════════════
def backtest_symbol(symbol, spy_regime, dalio_regime, equity_ref):
    df = fetch_history(symbol)
    if df is None:
        return [], []
    df = compute_indicators(df)
    if len(df) < 200:
        return [], []

    confirmed_swings = find_confirmed_swings(df)
    closes           = df["close"].values

    stock_trades  = []
    option_trades = []
    in_pos        = False
    in_option     = False
    entry = stop = target1 = target2 = 0.0
    shares = shares_remain = 0
    entry_date   = None
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

        # Rolling swing low over last GANN_LOOKBACK bars (no future data)
        sw_start          = max(0, i - GANN_LOOKBACK)
        sw_slice          = closes[sw_start:i]
        sw_rel_idx        = int(sw_slice.argmin())
        swing_low_price   = float(sw_slice[sw_rel_idx])
        swing_low_bar_idx = sw_start + sw_rel_idx

        # ── ENTRY ─────────────────────────────────────────────────────────
        if not in_pos:
            if should_enter(prev, prev_prev, spy_ok, d_regime, symbol,
                            i, swing_low_price, swing_low_bar_idx, confirmed_swings):

                entry = float(row["open"]) + SLIPPAGE
                atr   = float(prev["atr14"])
                stop  = round(entry - 2.0 * atr, 2)

                # Gann Square of 9 as targets (floored at +3% and +6%)
                sq9_r1, sq9_r2 = gann_sq9_targets(entry)
                target1 = round(max(sq9_r1, entry * 1.03), 2)
                target2 = round(max(sq9_r2, entry * 1.06), 2)

                shares = size_riskparity(cur_eq, atr, entry)
                if shares < 1:
                    continue

                shares_remain = shares
                partial_done  = False
                in_pos        = True
                entry_date    = date

                # Options overlay: 2% OTM call, 40 DTE, 1.5% equity budget
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

            # Couling early exit: bearish VPA signal while in position
            sig, sentiment = couling_vpa(row, prev)
            if sig in BEARISH_VPA and sentiment == "BEAR":
                exit_price = float(row["close"]) - SLIPPAGE
                reason     = f"VPA_{sig}"

            # Partial exit at target1 — sell half, trail stop to breakeven
            if exit_price is None and not partial_done and hi >= target1:
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
                    "vpa_signal": "",
                })
                shares_remain -= half
                stop          = entry   # trail to breakeven — remainder is a free trade
                partial_done  = True

            # Full-position exit
            if exit_price is None:
                if lo <= stop:
                    exit_price = stop - SLIPPAGE;            reason = "STOP"
                elif hi >= target2:
                    exit_price = target2 - SLIPPAGE;         reason = "TARGET2"
                elif hold_days >= 12:
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
                    "vpa_signal": sig,
                })
                in_pos = False

        # ── OPTIONS EXIT ──────────────────────────────────────────────────
        if in_option:
            days_held     = (date - opt_entry_date).days
            remaining_dte = max(opt_dte_start - days_held, 1)
            if (not in_pos) or (days_held >= opt_dte_start):
                S   = float(row["close"])
                vol = float(row["hist_vol"])
                cur_px, _ = price_option(S, opt_direction, vol,
                                         dte=remaining_dte, otm_pct=OPT_OTM)
                exit_px  = max(cur_px - OPTION_SLIP, 0.0)
                opt_pnl  = (exit_px - opt_entry_px) * opt_contracts * 100
                option_trades.append({
                    "symbol":        symbol,
                    "direction":     opt_direction,
                    "entry_date":    opt_entry_date.isoformat(),
                    "exit_date":     date.isoformat(),
                    "entry_premium": round(opt_entry_px, 2),
                    "exit_premium":  round(exit_px, 2),
                    "contracts":     opt_contracts,
                    "pnl":           round(opt_pnl, 2),
                    "pnl_pct":       round((exit_px - opt_entry_px) /
                                          (opt_entry_px + 1e-9) * 100, 1),
                })
                in_option = False

    return stock_trades, option_trades


# ═══════════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════════
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


def buy_and_hold_spy(equity):
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=365 * YEARS_BACK)
    df    = yf.Ticker("SPY").history(start=start, end=end)
    if df is None or df.empty:
        return {}
    sp, ep = float(df["Close"].iloc[0]), float(df["Close"].iloc[-1])
    sh     = int(equity / sp)
    return {
        "pnl":          round((ep - sp) * sh, 2),
        "total_return": round((ep - sp) / sp * 100, 1),
        "final_equity": round(equity + (ep - sp) * sh, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def run_backtest():
    print("=" * 68)
    print("  BACKTEST v3 — Multi-Legend Strategy")
    print("  Couling VPA · Gann · Dalio · Weinstein · Livermore")
    print(f"  Account: ${ACCOUNT_SIZE:,.2f}  |  {YEARS_BACK} yrs  |  {len(ETF_WATCHLIST)} ETFs")
    print(f"  Slippage: ${SLIPPAGE}/share  |  Target vol/trade: {TARGET_VOL_CONTRIB*100:.1f}%")
    print("=" * 68)

    print("\n  [1/3] SPY macro regime (200-day SMA filter)...")
    spy_regime   = build_spy_regime()
    bull_days    = sum(spy_regime.values())
    total_days   = len(spy_regime)
    print(f"        Bullish: {bull_days}/{total_days} days ({bull_days/max(total_days,1)*100:.0f}%)")

    print("  [2/3] Dalio growth/inflation regime (SPY + TLT 60-day ROC)...")
    dalio_regime = build_dalio_regime()
    regime_count = {}
    for r in dalio_regime.values():
        regime_count[r] = regime_count.get(r, 0) + 1
    for r, c in sorted(regime_count.items()):
        pct = c / max(len(dalio_regime), 1) * 100
        etf_list = ", ".join(REGIME_ETFS.get(r, []))
        print(f"        {r:<25} {c:4d} days ({pct:.0f}%) → {etf_list}")

    print(f"\n  [3/3] Running symbol backtests...\n")
    print(f"  {'Symbol':<7} {'Trades':>6}  {'W/L':>7}  {'Stock P&L':>11}  {'Opts P&L':>9}")
    print("  " + "─" * 50)

    equity_ref = {"value": ACCOUNT_SIZE}
    all_stock  = []
    all_opts   = []

    for symbol in ETF_WATCHLIST:
        s_trades, o_trades = backtest_symbol(symbol, spy_regime, dalio_regime, equity_ref)
        all_stock.extend(s_trades)
        all_opts.extend(o_trades)

        sym_pnl = (sum(t["pnl"] for t in s_trades) +
                   sum(t["pnl"] for t in o_trades))
        equity_ref["value"] = max(equity_ref["value"] + sym_pnl, 1.0)

        n    = len(s_trades)
        w    = sum(1 for t in s_trades if t["pnl"] > 0)
        s_pl = sum(t["pnl"] for t in s_trades)
        o_pl = sum(t["pnl"] for t in o_trades)
        print(f"  {symbol:<7} {n:>6}   {w}W/{n-w}L   ${s_pl:>+10.2f}  ${o_pl:>+8.2f}")

    print()
    if not all_stock:
        print("  ⚠  No trades generated.")
        print("  Tip: relax filters by reducing TARGET_VOL_CONTRIB, widening RSI range,")
        print("       or removing the Livermore breakout gate.")
        return

    # Build equity curve
    date_pnl = {}
    for t in all_stock + all_opts:
        date_pnl[t["exit_date"]] = date_pnl.get(t["exit_date"], 0) + t["pnl"]
    eq_rows  = []
    running  = ACCOUNT_SIZE
    for d in sorted(date_pnl):
        running += date_pnl[d]
        eq_rows.append({"date": d, "equity": round(running, 2)})

    pd.DataFrame(eq_rows).to_csv(EQUITY_FILE, index=False)
    pd.DataFrame(all_stock).to_csv(RESULTS_FILE, index=False)
    pd.DataFrame(all_opts).to_csv(OPTIONS_FILE, index=False)

    # Per-symbol summary
    print(f"  {'Symbol':<7} {'Trades':>6}  {'WR%':>6}  {'Stock P&L':>11}  {'Opt P&L':>9}")
    print("  " + "─" * 50)
    for sym in ETF_WATCHLIST:
        st = [t for t in all_stock if t["symbol"] == sym]
        ot = [t for t in all_opts  if t["symbol"] == sym]
        if not st:
            continue
        pnls = [t["pnl"] for t in st]
        wr   = sum(1 for p in pnls if p > 0) / len(pnls) * 100
        print(f"  {sym:<7} {len(pnls):>6}  {wr:>5.1f}%  ${sum(pnls):>+10.2f}  ${sum(t['pnl'] for t in ot):>+8.2f}")

    # VPA signal breakdown
    sig_counts = {}
    for t in all_stock:
        s = t.get("vpa_signal", "")
        if s:
            sig_counts[s] = sig_counts.get(s, 0) + 1
    if sig_counts:
        print(f"\n  VPA EXIT SIGNALS: {dict(sorted(sig_counts.items(), key=lambda x: -x[1]))}")

    # Overall metrics
    all_pnls  = [t["pnl"] for t in all_stock]
    eq_vals   = [ACCOUNT_SIZE] + [r["equity"] for r in eq_rows]
    m         = calc_metrics(all_pnls, eq_vals, ACCOUNT_SIZE)
    opt_total = sum(t["pnl"] for t in all_opts)
    combined  = m["total_pnl"] + opt_total
    combo_ret = combined / ACCOUNT_SIZE * 100
    bnh       = buy_and_hold_spy(ACCOUNT_SIZE)
    diff      = combo_ret - bnh.get("total_return", 0)
    verdict   = (f"BEAT buy-and-hold by +{diff:.1f}%"
                 if diff > 0 else f"Buy-and-hold beat strategy by {abs(diff):.1f}%")

    print(f"""
  ┌─ STOCK STRATEGY ───────────────────────────────────┐
  │  Trades:         {m['trades']:<6}  Wins: {m['wins']}  Losses: {m['losses']}
  │  Win rate:       {m['win_rate']}%
  │  Profit factor:  {m['profit_factor']}
  │  P&L:            ${m['total_pnl']:,.2f}
  │  Return:         {m['total_return']}%
  │  Max drawdown:   {m['max_drawdown']}%
  │  Sharpe ratio:   {m['sharpe']}
  │  Sortino ratio:  {m['sortino']}
  └────────────────────────────────────────────────────┘

  ┌─ OPTIONS OVERLAY (2% OTM calls, 40 DTE) ───────────┐
  │  Trades:         {len(all_opts)}
  │  P&L:            ${opt_total:,.2f}{"" if not all_opts else f"  Win rate: {sum(1 for t in all_opts if t['pnl']>0)/len(all_opts)*100:.0f}%"}
  └────────────────────────────────────────────────────┘

  ┌─ COMBINED ──────────────────────────────────────────┐
  │  Total P&L:      ${combined:,.2f}
  │  Final equity:   ${ACCOUNT_SIZE + combined:,.2f}
  │  Combined return:{combo_ret:.1f}%
  └────────────────────────────────────────────────────┘

  ┌─ BUY & HOLD SPY ────────────────────────────────────┐
  │  Return:         {bnh.get('total_return', 0)}%
  │  Final equity:   ${bnh.get('final_equity', 0):,.2f}
  └────────────────────────────────────────────────────┘

  VERDICT: {verdict}
""")

    summary = (
        f"BACKTEST v3 — Multi-Legend Strategy\n"
        f"Couling VPA · Gann · Dalio · Weinstein · Livermore\n"
        f"{'─'*50}\n"
        f"Stock return:    {m['total_return']}%\n"
        f"Options P&L:     ${opt_total:,.2f}\n"
        f"Combined return: {combo_ret:.1f}%\n"
        f"Sharpe:          {m['sharpe']}  |  Sortino: {m['sortino']}\n"
        f"Max drawdown:    {m['max_drawdown']}%\n"
        f"Profit factor:   {m['profit_factor']}\n"
        f"Win rate:        {m['win_rate']}%\n"
        f"Buy-hold return: {bnh.get('total_return', 0)}%\n"
        f"{'─'*50}\n"
        f"Verdict: {verdict}\n"
        f"\nTUNING GUIDE (if trades are too few):\n"
        f"  1. TARGET_VOL_CONTRIB: raise 0.007 → 0.010 (larger positions)\n"
        f"  2. RSI range: widen 35-72 → 30-75\n"
        f"  3. Remove Livermore gate: comment out gate #6 in should_enter()\n"
        f"  4. Relax Dalio regime: set etf_fits_regime() to always return True\n"
        f"  5. Gann angle: lower daily increment 0.001 → 0.0005\n"
    )
    with open(SUMMARY_FILE, "w") as f:
        f.write(summary)

    print(f"  Saved: {RESULTS_FILE}, {OPTIONS_FILE}, {EQUITY_FILE}, {SUMMARY_FILE}\n")


if __name__ == "__main__":
    run_backtest()
