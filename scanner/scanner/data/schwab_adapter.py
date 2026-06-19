"""
Charles Schwab market-data adapter.

Wraps Schwab's /marketdata/v1/pricehistory endpoint into the DataAdapter
interface, reusing the OAuth token approach from the repo's ``trading`` client.

ADJUSTMENT METHODOLOGY (document this in every report): Schwab daily price
history is SPLIT-ADJUSTED. Dividends are NOT reinvested, so results derived from
it are PRICE-RETURN. Schwab does not expose a survivorship-bias-free universe
(delisted tickers are not queryable), so survivorship bias must be disclosed as
a limitation when using this source.

AUTH / ENVIRONMENT REQUIREMENTS (cannot be satisfied inside a headless,
allowlisted container):
  1. ``api.schwabapi.com`` must be on the environment's network egress allowlist.
  2. ``SCHWAB_APP_KEY`` and ``SCHWAB_APP_SECRET`` must be set.
  3. A valid ``token.json`` (refresh_token + access_token) must exist — minted
     once via Schwab's browser OAuth flow OUTSIDE this container (the redirect
     cannot be completed headlessly). Point SCHWAB_TOKEN_PATH at it.

The token is auto-refreshed using the refresh_token when the access token is
near expiry. Responses are cached on disk for reproducibility / rate-limit
friendliness.
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Optional

import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS

_BASE_MARKET = "https://api.schwabapi.com/marketdata/v1"
_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

# Schwab supports these daily/intraday frequencies; 1h is not native.
_RES = {
    "1d": {"periodType": "year", "period": 20, "frequencyType": "daily", "frequency": 1},
    "15m": {"periodType": "day", "period": 10, "frequencyType": "minute", "frequency": 15},
}


class SchwabAdapter(DataAdapter):
    name = "schwab"
    adjustment = "split-adjusted; price-return (dividends not reinvested)"
    survivorship_free = False

    def __init__(self, app_key: Optional[str] = None, app_secret: Optional[str] = None,
                 token_path: Optional[str] = None, cache_dir: str = ".schwab_cache"):
        self.app_key = app_key or os.getenv("SCHWAB_APP_KEY", "")
        self.app_secret = app_secret or os.getenv("SCHWAB_APP_SECRET", "")
        self.token_path = token_path or os.getenv("SCHWAB_TOKEN_PATH", "token.json")
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        if not (self.app_key and self.app_secret):
            raise RuntimeError(
                "SCHWAB_APP_KEY / SCHWAB_APP_SECRET not set. Schwab also requires "
                "api.schwabapi.com on the egress allowlist and a token.json minted "
                "via browser OAuth outside this container."
            )
        # Headless convenience: if no token file exists but the token JSON was
        # provided as a secret env var, materialize it. This avoids committing a
        # sensitive token.json into the repo to get it into a container.
        token_json = os.getenv("SCHWAB_TOKEN_JSON")
        if token_json and not os.path.exists(self.token_path):
            try:
                with open(self.token_path, "w") as fh:
                    fh.write(token_json)
            except OSError:
                pass

    # -- token management --------------------------------------------------
    def _load_token(self) -> dict:
        if not os.path.exists(self.token_path):
            raise RuntimeError(
                f"No token.json at {self.token_path}. Mint it once locally via "
                "Schwab's browser OAuth (see trading/setup_auth.py) and provide it."
            )
        with open(self.token_path) as fh:
            return json.load(fh)

    def _save_token(self, token: dict) -> None:
        with open(self.token_path, "w") as fh:
            json.dump(token, fh, indent=2)

    def _refresh(self, token: dict) -> dict:
        import requests
        creds = base64.b64encode(f"{self.app_key}:{self.app_secret}".encode()).decode()
        resp = requests.post(_TOKEN_URL, headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        }, data={"grant_type": "refresh_token",
                 "refresh_token": token["refresh_token"]}, timeout=30)
        resp.raise_for_status()
        new = resp.json()
        new["expires_at"] = time.time() + new.get("expires_in", 1800)
        new.setdefault("refresh_token", token["refresh_token"])
        self._save_token(new)
        return new

    def _access_token(self) -> str:
        token = self._load_token()
        if "refresh_token" not in token or "access_token" not in token:
            raise RuntimeError(
                f"token.json at {self.token_path} is incomplete (no refresh_token). "
                "The OAuth login did not complete — re-mint it: open the authorize "
                "URL, log in, click Allow, and paste the FULL https://127.0.0.1/?code=... "
                "address-bar URL back within ~30 seconds. Current file contents: "
                f"{token}"
            )
        if time.time() >= token.get("expires_at", 0) - 300:
            token = self._refresh(token)
        return token["access_token"]

    def _get(self, url: str, params: dict) -> dict:
        import requests
        resp = requests.get(url, params=params,
                            headers={"Authorization": f"Bearer {self._access_token()}"},
                            timeout=30)
        if resp.status_code != 200:
            return {}
        return resp.json()

    # -- public ------------------------------------------------------------
    def _cache_path(self, symbol, resolution) -> str:
        return os.path.join(self.cache_dir, f"{symbol}_{resolution}.json")

    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        if resolution not in _RES:
            raise ValueError(f"Schwab adapter supports {list(_RES)}; got {resolution}")
        cache = self._cache_path(symbol, resolution)
        if os.path.exists(cache):
            with open(cache) as fh:
                data = json.load(fh)
        else:
            params = {**_RES[resolution], "symbol": symbol,
                      "needExtendedHoursData": "false"}
            data = self._get(f"{_BASE_MARKET}/pricehistory", params)
            with open(cache, "w") as fh:
                json.dump(data, fh)

        candles = data.get("candles", []) or []
        if not candles:
            empty = pd.DataFrame(columns=OHLCV_COLUMNS,
                                 index=pd.DatetimeIndex([], tz="UTC"))
            return BarsResult(symbol, resolution, empty)

        df = pd.DataFrame(candles)
        idx = pd.to_datetime(df["datetime"], unit="ms", utc=True)
        if resolution == "1d":
            idx = idx.dt.normalize()
        df = df.set_index(idx).sort_index()
        df = df[~df.index.duplicated(keep="last")][OHLCV_COLUMNS]
        df = df.loc[(df.index >= start) & (df.index <= end)]
        if as_of is not None:
            df = df.loc[df.index <= as_of]
        return BarsResult(symbol, resolution, df.copy())

    def is_tradable(self, symbol, as_of=None) -> bool:
        # Schwab has no point-in-time delisting feed; treat presence of recent
        # history as tradable. Survivorship bias is disclosed at the report level.
        try:
            bars = self.get_bars(symbol, "1d",
                                 start=pd.Timestamp("1990-01-01", tz="UTC"),
                                 end=as_of or pd.Timestamp.now("UTC"), as_of=as_of).df
        except Exception:
            return False
        return len(bars) > 0
