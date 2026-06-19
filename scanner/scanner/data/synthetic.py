"""
Synthetic data adapter.

Generates deterministic pseudo-random OHLCV series so the whole pipeline
(scan -> backtest -> validation -> ranking) runs end-to-end with no network
and no API keys. Useful for tests, demos, and CI. It is NOT a substitute for
real adjusted market data — never treat synthetic backtest numbers as
evidence about real markets.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .base import DataAdapter, BarsResult, OHLCV_COLUMNS

_RES_FREQ = {"1d": "B", "1h": "h", "15m": "15min"}


class SyntheticAdapter(DataAdapter):
    name = "synthetic"
    survivorship_free = False  # synthetic; no real delistings anyway

    def __init__(self, seed: int = 7, n_days: int = 2600, regime_cycles: bool = True):
        self.seed = seed
        self.n_days = n_days
        self.regime_cycles = regime_cycles
        self._cache: dict = {}

    def _symbol_seed(self, symbol: str) -> int:
        return (self.seed * 1_000_003 + sum(ord(c) for c in symbol)) % (2**31)

    def _generate_daily(self, symbol: str) -> pd.DataFrame:
        if symbol in self._cache:
            return self._cache[symbol]
        rng = np.random.default_rng(self._symbol_seed(symbol))
        n = self.n_days
        end = pd.Timestamp.now("UTC").normalize()
        idx = pd.bdate_range(end=end, periods=n, tz="UTC")

        # Regime cycling: alternating drift/vol so multi-regime testing is possible.
        t = np.arange(n)
        if self.regime_cycles:
            drift = 0.0004 * np.sin(2 * np.pi * t / 380) + 0.0002
            vol = 0.011 + 0.006 * (1 + np.sin(2 * np.pi * t / 250 + 1.3)) / 2
        else:
            drift = np.full(n, 0.0003)
            vol = np.full(n, 0.013)

        shocks = rng.standard_normal(n) * vol + drift
        # occasional jumps to create breakouts / gaps
        jumps = rng.choice([0, 1], size=n, p=[0.985, 0.015]) * rng.standard_normal(n) * 0.04
        log_ret = shocks + jumps
        close = 50 * np.exp(np.cumsum(log_ret))

        intrabar = np.abs(rng.standard_normal(n)) * vol * close
        open_ = close * (1 + rng.standard_normal(n) * vol * 0.5)
        high = np.maximum(open_, close) + intrabar * 0.6
        low = np.minimum(open_, close) - intrabar * 0.6
        low = np.maximum(low, 0.01)
        base_vol = rng.integers(2_000_000, 8_000_000, size=n).astype(float)
        vol_mult = 1 + np.abs(log_ret) / (vol + 1e-9)  # volume rises with range
        volume = base_vol * vol_mult

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=idx,
        )[OHLCV_COLUMNS]
        self._cache[symbol] = df
        return df

    def get_bars(self, symbol, resolution, start, end, as_of=None) -> BarsResult:
        if resolution not in _RES_FREQ:
            raise ValueError(f"unsupported resolution {resolution}")
        daily = self._generate_daily(symbol)
        if resolution == "1d":
            df = daily
        else:
            # Resample daily into intraday by interpolating a simple path. This is
            # only a placeholder so intraday setups are exercisable in demos.
            freq = _RES_FREQ[resolution]
            per_day = {"1h": 7, "15m": 26}[resolution]
            rows = []
            rng = np.random.default_rng(self._symbol_seed(symbol) + 99)
            for ts, row in daily.iterrows():
                sub_idx = pd.date_range(ts, periods=per_day, freq=freq, tz="UTC")
                path = np.linspace(row["open"], row["close"], per_day)
                noise = rng.standard_normal(per_day) * (row["high"] - row["low"]) * 0.1
                c = path + noise
                o = np.concatenate([[row["open"]], c[:-1]])
                h = np.maximum(o, c) + abs(row["high"] - row["close"]) * 0.2
                lo = np.minimum(o, c) - abs(row["close"] - row["low"]) * 0.2
                v = np.full(per_day, row["volume"] / per_day)
                rows.append(pd.DataFrame(
                    {"open": o, "high": h, "low": lo, "close": c, "volume": v},
                    index=sub_idx))
            df = pd.concat(rows)[OHLCV_COLUMNS]

        df = df.loc[(df.index >= start) & (df.index <= end)]
        if as_of is not None:
            df = df.loc[df.index <= as_of]
        return BarsResult(symbol, resolution, df.copy())

    def is_tradable(self, symbol, as_of=None) -> bool:
        return True
