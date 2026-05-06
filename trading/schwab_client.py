"""
Schwab API client — direct HTTP, no schwab-py auth dependency.

FIRST-TIME SETUP:
  1. pip3 install pandas python-dotenv
  2. Copy .env.example to .env and fill in SCHWAB_APP_KEY / SCHWAB_APP_SECRET
  3. Run:  python3 setup_auth.py   (one-time login, saves token.json)
  4. Run:  python3 backtest.py

NEVER commit token.json or .env — they are gitignored.
"""
import os, json, time, math, base64, urllib.request, urllib.parse
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

APP_KEY    = os.getenv("SCHWAB_APP_KEY", "")
APP_SECRET = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK   = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1")
TOKEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")

BASE_MARKET = "https://api.schwabapi.com/marketdata/v1"
BASE_TRADER = "https://api.schwabapi.com/trader/v1"
TOKEN_URL   = "https://api.schwabapi.com/v1/oauth/token"


# ─── Token management ─────────────────────────────────────────────────────────
def _load_token():
    if not os.path.exists(TOKEN_PATH):
        raise SystemExit(
            "\n  No token.json found.\n"
            "  Run this first:  python3 setup_auth.py\n"
        )
    with open(TOKEN_PATH) as f:
        return json.load(f)


def _save_token(token):
    with open(TOKEN_PATH, "w") as f:
        json.dump(token, f, indent=2)


def _refresh(token):
    creds = base64.b64encode(f"{APP_KEY}:{APP_SECRET}".encode()).decode()
    body  = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "refresh_token": token["refresh_token"],
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type":  "application/x-www-form-urlencoded",
        }
    )
    with urllib.request.urlopen(req) as r:
        new = json.loads(r.read())
    new["expires_at"] = time.time() + new.get("expires_in", 1800)
    if "refresh_token" not in new:
        new["refresh_token"] = token["refresh_token"]
    _save_token(new)
    return new


def _access_token():
    token = _load_token()
    if time.time() >= token.get("expires_at", 0) - 300:
        try:
            token = _refresh(token)
        except Exception as e:
            raise SystemExit(
                f"\n  Token expired and refresh failed: {e}\n"
                "  Run:  python3 setup_auth.py\n"
            )
    return token["access_token"]


def _get(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {_access_token()}"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 0, {}


# ─── Public API ───────────────────────────────────────────────────────────────
def fetch_history(symbol, years=7, extra_days=300):
    """
    Fetch daily OHLCV history. Returns DataFrame or None on failure.
    Columns: open, high, low, close, volume  (lowercase).
    """
    try:
        status, data = _get(
            f"{BASE_MARKET}/pricehistory",
            params={
                "symbol":               symbol,
                "periodType":           "year",
                "period":               10,
                "frequencyType":        "daily",
                "frequency":            1,
                "needExtendedHoursData": "false",
            }
        )
        if status != 200:
            print(f"  [schwab] {symbol}: HTTP {status}")
            return None

        candles = data.get("candles", [])
        if not candles:
            print(f"  [schwab] {symbol}: empty response")
            return None

        df = pd.DataFrame(candles)
        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms", utc=True)
        df = df.set_index("datetime")
        df.index = df.index.tz_convert("America/New_York").normalize()
        df = df[["open", "high", "low", "close", "volume"]].copy()

        cutoff = (pd.Timestamp.now(tz="America/New_York")
                  - pd.Timedelta(days=365 * years + extra_days))
        df = df[df.index >= cutoff]

        if len(df) < 50:
            print(f"  [schwab] {symbol}: insufficient data ({len(df)} rows)")
            return None

        return df
    except Exception as e:
        print(f"  [schwab] {symbol}: {e}")
        return None


def fetch_quote(symbol):
    """Return {last, bid, ask, volume} or empty dict."""
    try:
        status, data = _get(f"{BASE_MARKET}/{symbol}/quotes")
        if status != 200:
            return {}
        q = data.get(symbol, {}).get("quote", {})
        return {
            "last":   q.get("lastPrice", 0),
            "bid":    q.get("bidPrice", 0),
            "ask":    q.get("askPrice", 0),
            "volume": q.get("totalVolume", 0),
        }
    except Exception as e:
        print(f"  [quote] {symbol}: {e}")
        return {}


def get_account_balance():
    """Return account liquidation value as float, or None."""
    try:
        status, data = _get(f"{BASE_TRADER}/accounts")
        if status != 200:
            return None
        for acct in data:
            bal = acct.get("securitiesAccount", {}).get("currentBalances", {})
            liquid = bal.get("liquidationValue") or bal.get("cashBalance", 0)
            if liquid and liquid > 0:
                return float(liquid)
        return None
    except Exception as e:
        print(f"  [account] {e}")
        return None


def get_client():
    """Compatibility shim — not needed with direct HTTP approach."""
    return None
