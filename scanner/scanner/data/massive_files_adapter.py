"""
Massive.com FLAT FILES adapter (S3) — for accounts whose plan includes Flat
Files / S3 access but NOT the REST API.

How Massive flat files work (same layout Polygon used):
  * S3-compatible endpoint  : https://files.massive.com
  * bucket                  : flatfiles
  * daily OHLCV, ALL tickers per file:
        us_stocks_sip/day_aggs_v1/YYYY/MM/YYYY-MM-DD.csv.gz
    each file holds one row per ticker for that trading day.

Because every file covers ALL tickers for ONE day, building a multi-year history
for a few symbols means pulling one (small, gzipped) file per trading day. We
therefore cache aggressively:
  * each downloaded day file is cached on disk (shared across symbols), and
  * each symbol's assembled daily series is cached and extended incrementally,
so the FIRST run is slow (it downloads many day files) and later runs are fast.

Credentials are the S3 "Access Key ID" + "Secret Access Key" shown on the
Massive key page under the "Accessing Flat Files (S3)" tab:
    export MASSIVE_ACCESS_KEY_ID=...        (the Access Key ID)
    export MASSIVE_SECRET_ACCESS_KEY=...    (the Secret Access Key)

Requires boto3:  pip install boto3
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS

_ENDPOINT = "https://files.massive.com"
_BUCKET = "flatfiles"
_PREFIX = "us_stocks_sip/day_aggs_v1"


class MassiveFlatFilesAdapter(DataAdapter):
    name = "massive_files"
    adjustment = "Massive flat files (day aggregates); split-adjusted daily"
    survivorship_free = True  # delisted tickers remain in historical day files

    def __init__(self, access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 cache_dir: str = ".massive_files_cache",
                 endpoint: str = _ENDPOINT, bucket: str = _BUCKET):
        self.access_key = (access_key or os.getenv("MASSIVE_ACCESS_KEY_ID")
                           or os.getenv("MASSIVE_S3_ACCESS_KEY"))
        self.secret_key = (secret_key or os.getenv("MASSIVE_SECRET_ACCESS_KEY")
                           or os.getenv("MASSIVE_S3_SECRET"))
        if not self.access_key or not self.secret_key:
            raise RuntimeError(
                "Massive Flat Files needs S3 credentials. On massive.com open your "
                "key, click the 'Accessing Flat Files (S3)' tab, then set:\n"
                "  export MASSIVE_ACCESS_KEY_ID=your_access_key_id\n"
                "  export MASSIVE_SECRET_ACCESS_KEY=your_secret_access_key")
        self.endpoint = endpoint
        self.bucket = bucket
        self.cache_dir = cache_dir
        self.day_dir = os.path.join(cache_dir, "days")
        self.sym_dir = os.path.join(cache_dir, "symbols")
        os.makedirs(self.day_dir, exist_ok=True)
        os.makedirs(self.sym_dir, exist_ok=True)
        self._client = None

    # -- S3 plumbing -------------------------------------------------------
    def _s3(self):
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise RuntimeError(
                    "Massive Flat Files needs the boto3 library. Install it once:\n"
                    "  pip install boto3") from exc
            session = boto3.Session(aws_access_key_id=self.access_key,
                                    aws_secret_access_key=self.secret_key)
            self._client = session.client(
                "s3", endpoint_url=self.endpoint,
                config=Config(signature_version="s3v4"))
        return self._client

    def _key(self, date) -> str:
        return f"{_PREFIX}/{date.year:04d}/{date.month:02d}/{date:%Y-%m-%d}.csv.gz"

    def _day_path(self, date) -> str:
        return os.path.join(self.day_dir, f"{date:%Y-%m-%d}.csv.gz")

    def _miss_path(self, date) -> str:
        return os.path.join(self.day_dir, f"{date:%Y-%m-%d}.missing")

    def _download_day(self, date) -> Optional[str]:
        """Return local path to the day's gz file, or None if no file exists
        for that date (weekend/holiday). Caches both hits and misses."""
        path = self._day_path(date)
        if os.path.exists(path):
            return path
        if os.path.exists(self._miss_path(date)):
            return None
        client = self._s3()  # friendly 'pip install boto3' error if missing
        from botocore.exceptions import ClientError
        try:
            client.download_file(self.bucket, self._key(date), path)
            return path
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                open(self._miss_path(date), "w").close()  # remember the gap
                return None
            if code in ("403", "AccessDenied", "InvalidAccessKeyId",
                        "SignatureDoesNotMatch", "Forbidden"):
                akid = self.access_key or ""
                shown = f"{akid[:4]}…{akid[-4:]}" if len(akid) > 8 else akid
                if code in ("SignatureDoesNotMatch",):
                    why = ("The SECRET access key is wrong/mistyped. Re-copy the "
                           "'Secret Access Key' exactly (no spaces).")
                elif code in ("InvalidAccessKeyId",):
                    why = ("The ACCESS KEY ID is wrong, OR the two keys are SWAPPED. "
                           "MASSIVE_ACCESS_KEY_ID must be the long ID (e.g. "
                           "a054cdda-…), MASSIVE_SECRET_ACCESS_KEY the other one.")
                else:  # AccessDenied / 403 / Forbidden
                    why = ("Credentials look valid but your plan may not grant "
                           "Flat Files read access, OR the keys are swapped. Check "
                           "the 'Accessing Flat Files (S3)' tab is enabled.")
                raise RuntimeError(
                    f"Massive Flat Files rejected the request: {code}.\n"
                    f"  (using Access Key ID {shown})\n  → {why}") from exc
            raise

    def _day_symbol_row(self, date, symbol):
        path = self._download_day(date)
        if path is None:
            return None
        try:
            df = pd.read_csv(path, compression="gzip")
        except Exception:
            # corrupt/partial download — drop it so it re-fetches next time
            try:
                os.remove(path)
            except OSError:
                pass
            return None
        sub = df[df["ticker"].astype(str).str.upper() == symbol.upper()]
        if sub.empty:
            return None
        r = sub.iloc[0]
        return {"open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r["volume"])}

    # -- public API --------------------------------------------------------
    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        if resolution != "1d":
            return BarsResult(symbol, resolution,
                              pd.DataFrame(columns=OHLCV_COLUMNS,
                                           index=pd.DatetimeIndex([], tz="UTC")))
        sym = symbol.upper()
        cache = os.path.join(self.sym_dir, f"{sym}.csv")
        have = pd.DataFrame()
        if os.path.exists(cache):
            have = pd.read_csv(cache, index_col=0, parse_dates=True)
            if have.index.tz is None:
                have.index = have.index.tz_localize("UTC")

        # trading days we need (weekdays in range); reuse cached ones.
        want = pd.bdate_range(start.tz_convert(None) if start.tzinfo else start,
                              end.tz_convert(None) if end.tzinfo else end)
        want = pd.DatetimeIndex([d for d in want])
        have_dates = set(have.index.tz_convert(None).normalize()) if len(have) else set()
        todo = [d for d in want if d.normalize() not in have_dates]

        rows, idx = [], []
        for i, d in enumerate(todo):
            row = self._day_symbol_row(d.date(), sym)
            if i and i % 200 == 0:
                print(f"    [massive flat files] {sym}: fetched {i}/{len(todo)} days…")
            if row is None:
                continue
            rows.append(row)
            idx.append(pd.Timestamp(d).tz_localize("UTC"))
        fresh = pd.DataFrame(rows, index=pd.DatetimeIndex(idx)) if rows else pd.DataFrame()

        full = pd.concat([f for f in (have, fresh) if not f.empty]) \
            if (len(have) or len(fresh)) else pd.DataFrame(columns=OHLCV_COLUMNS)
        if not full.empty:
            full = full[~full.index.duplicated(keep="last")].sort_index()
            full.to_csv(cache)  # extend the symbol cache for next time

        out = full
        if not out.empty:
            out = out.loc[(out.index >= start) & (out.index <= end)]
            if as_of is not None:
                out = out.loc[out.index <= as_of]
            out = out[OHLCV_COLUMNS]
        return BarsResult(symbol, resolution, out.copy() if not out.empty else
                          pd.DataFrame(columns=OHLCV_COLUMNS,
                                       index=pd.DatetimeIndex([], tz="UTC")))

    def is_tradable(self, symbol, as_of=None) -> bool:
        end = as_of or pd.Timestamp.now("UTC").normalize()
        df = self.get_bars(symbol, "1d", end - pd.Timedelta(days=20), end).df
        return len(df) > 0
