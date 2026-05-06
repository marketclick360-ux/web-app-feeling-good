"""
Schwab API data client — replaces yfinance in backtest.py and signals.py.

FIRST-TIME SETUP:
  1. pip install schwab-py
  2. Copy .env.example to .env and fill in SCHWAB_APP_KEY / SCHWAB_APP_SECRET
  3. Make sure SCHWAB_CALLBACK_URL matches what you set in developer.schwab.com
  4. Run any script — a browser tab will open asking you to log in to Schwab.
     Approve it, and the token is saved to token.json automatically.
  5. Every future run is silent (token refreshes automatically).

NEVER commit token.json or .env — they are in .gitignore.
"""
import os, math, datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

APP_KEY      = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET   = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK_URL = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1")
TOKEN_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")

_client = None


def _make_client():
    """Create and return an authenticated Schwab client."""
    if not APP_KEY or not APP_SECRET:
        raise SystemExit(
            "\n  Missing Schwab credentials.\n"
            "  Copy trading/.env.example to trading/.env and fill in:\n"
            "    SCHWAB_APP_KEY=...\n"
            "    SCHWAB_APP_SECRET=...\n"
        )
    try:
        import schwab
    except ImportError:
        raise SystemExit(
            "\n  schwab-py not installed. Run:\n"
            "    pip install schwab-py\n"
        )

    print("  Connecting to Schwab API...")
    client = schwab.auth.easy_client(
        api_key=APP_KEY,
        app_secret=APP_SECRET,
        callback_url=CALLBACK_URL,
        token_path=TOKEN_PATH,
    )
    print("  Schwab connected ✓")
    return client


def get_client():
    """Return cached authenticated client, creating it on first call."""
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# ─── Price history ────────────────────────────────────────────────────────────
def fetch_history(symbol, years=7, extra_days=300):
    """
    Fetch daily OHLCV history from Schwab.
    Returns a pandas DataFrame indexed by date with columns:
      open, high, low, close, volume
    Returns None on any failure.

    Drop-in replacement for the yfinance fetch_history() used in backtest.py
    and signals.py — same output format, same None-on-failure contract.
    """
    try:
        from schwab.client import Client
        c = get_client()

        # Request 10 years so we always have enough warmup data
        resp = c.get_price_history_every_day(
            symbol,
            period_type=Client.PriceHistory.PeriodType.YEAR,
            period=Client.PriceHistory.Period.TEN_YEARS,
            need_extended_hours_data=False,
        )

        if resp.status_code != 200:
            print(f"  [schwab] {symbol}: HTTP {resp.status_code}")
            return None

        candles = resp.json().get("candles", [])
        if not candles:
            print(f"  [schwab] {symbol}: empty response")
            return None

        df = pd.DataFrame(candles)

        # Schwab returns Unix ms timestamps
        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms", utc=True)
        df = df.set_index("datetime")
        df.index = df.index.tz_convert("America/New_York").normalize()

        df = df[["open", "high", "low", "close", "volume"]].copy()

        # Trim to the requested lookback window
        cutoff = pd.Timestamp.now(tz="America/New_York") - pd.Timedelta(
            days=365 * years + extra_days
        )
        df = df[df.index >= cutoff]

        if len(df) < 50:
            print(f"  [schwab] {symbol}: insufficient data ({len(df)} bars)")
            return None

        return df

    except Exception as e:
        print(f"  [schwab] {symbol}: {e}")
        return None


# ─── Live quote ───────────────────────────────────────────────────────────────
def fetch_quote(symbol):
    """
    Return current quote dict: {last, bid, ask, volume}.
    Returns empty dict on failure.
    """
    try:
        c    = get_client()
        resp = c.get_quote(symbol)
        if resp.status_code != 200:
            return {}
        q = resp.json().get(symbol, {}).get("quote", {})
        return {
            "last":   q.get("lastPrice", 0),
            "bid":    q.get("bidPrice", 0),
            "ask":    q.get("askPrice", 0),
            "volume": q.get("totalVolume", 0),
        }
    except Exception as e:
        print(f"  [quote] {symbol}: {e}")
        return {}


# ─── Account balance ──────────────────────────────────────────────────────────
def get_account_balance():
    """
    Read liquidation value from the first linked Schwab account.
    Returns float or None on failure.
    Used to auto-populate ACCOUNT_SIZE instead of reading from .env.
    """
    try:
        c    = get_client()
        resp = c.get_accounts()
        if resp.status_code != 200:
            return None
        for acct in resp.json():
            bal = (acct.get("securitiesAccount", {})
                      .get("currentBalances", {}))
            liquid = bal.get("liquidationValue") or bal.get("cashBalance", 0)
            if liquid and liquid > 0:
                return float(liquid)
        return None
    except Exception as e:
        print(f"  [account] {e}")
        return None
