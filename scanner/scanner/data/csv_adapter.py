"""
Local CSV / Parquet adapter (offline, no network).

Expected layout under `root`:
    root/<resolution>/<SYMBOL>.csv      e.g. root/1d/AAPL.csv
or  root/<resolution>/<SYMBOL>.parquet

Each file must contain ADJUSTED OHLCV with a timestamp column. Recognized
timestamp column names: timestamp, date, datetime, time. Prices must already
be split/dividend adjusted by whoever produced the files.

Optional `delistings.csv` at `root` with columns [symbol, last_trade_date]
lets the adapter answer `is_tradable` correctly for survivorship-bias-free
universes.
"""
from __future__ import annotations

import os
from typing import Optional

import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS

_TS_CANDIDATES = ["timestamp", "date", "datetime", "time"]


class CSVAdapter(DataAdapter):
    name = "csv"

    def __init__(self, root: str):
        self.root = root
        self._delistings = self._load_delistings()

    def _load_delistings(self) -> dict:
        path = os.path.join(self.root, "delistings.csv")
        if not os.path.exists(path):
            return {}
        d = pd.read_csv(path)
        d.columns = [c.lower() for c in d.columns]
        return {
            str(r["symbol"]).upper(): pd.Timestamp(r["last_trade_date"], tz="UTC")
            for _, r in d.iterrows()
        }

    def _path(self, symbol: str, resolution: str) -> Optional[str]:
        base = os.path.join(self.root, resolution, symbol.upper())
        for ext in (".parquet", ".csv"):
            if os.path.exists(base + ext):
                return base + ext
        return None

    def _read(self, path: str) -> pd.DataFrame:
        df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
        df.columns = [c.lower() for c in df.columns]
        ts_col = next((c for c in _TS_CANDIDATES if c in df.columns), None)
        if ts_col is None:
            raise ValueError(f"{path}: no timestamp column among {_TS_CANDIDATES}")
        idx = pd.to_datetime(df[ts_col], utc=True)
        df = df.set_index(idx).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        return df[OHLCV_COLUMNS]

    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        path = self._path(symbol, resolution)
        if path is None:
            return BarsResult(symbol, resolution,
                              pd.DataFrame(columns=OHLCV_COLUMNS,
                                           index=pd.DatetimeIndex([], tz="UTC")))
        df = self._read(path)
        df = df.loc[(df.index >= start) & (df.index <= end)]
        if as_of is not None:
            df = df.loc[df.index <= as_of]
        return BarsResult(symbol, resolution, df.copy())

    def is_tradable(self, symbol, as_of=None) -> bool:
        if self._path(symbol, "1d") is None:
            return False
        last = self._delistings.get(symbol.upper())
        if last is not None and as_of is not None and as_of > last:
            return False
        return True
