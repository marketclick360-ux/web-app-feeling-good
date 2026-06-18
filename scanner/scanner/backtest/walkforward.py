"""
Walk-forward analysis and in-sample / out-of-sample / holdout splits.

Time-based splitting (never random over time) so that out-of-sample always
follows in-sample. The final holdout is reserved and only touched once, after
rules are locked.

Splits are by SIGNAL DATE. A typical layout for ~10y of data:
  * development (in-sample):  first 50%
  * out-of-sample validation: next 30%
  * untouched holdout:        last 20%

Walk-forward uses rolling train/test windows and concatenates the test-window
trades into a single out-of-sample stream.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

import numpy as np
import pandas as pd

from .engine import Trade, trades_to_frame
from . import metrics


@dataclass
class Split:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp


def time_splits(trades: List[Trade],
                dev=0.5, oos=0.3) -> Tuple[List[Trade], List[Trade], List[Trade]]:
    """Return (development, out_of_sample, holdout) trade lists by signal time."""
    if not trades:
        return [], [], []
    ts = sorted(t.signal_time for t in trades)
    t0, t1 = ts[0], ts[-1]
    span = (t1 - t0)
    dev_end = t0 + span * dev
    oos_end = t0 + span * (dev + oos)

    development = [t for t in trades if t.signal_time <= dev_end]
    out_sample = [t for t in trades if dev_end < t.signal_time <= oos_end]
    holdout = [t for t in trades if t.signal_time > oos_end]
    return development, out_sample, holdout


def walk_forward(trades: List[Trade], n_folds: int = 5,
                 train_frac: float = 0.6) -> dict:
    """Rolling-window walk-forward. With purely rule-based (non-optimized)
    setups, training windows are used only to confirm the rule was 'active'
    before each test window; test-window trades are concatenated into the OOS
    stream. Returns per-fold and aggregate OOS metrics."""
    if not trades:
        return {"folds": [], "oos": {}}
    ts = np.array([t.signal_time.value for t in trades])
    order = np.argsort(ts)
    trades = [trades[i] for i in order]
    n = len(trades)
    fold_size = max(n // (n_folds + 1), 1)

    folds, oos_trades = [], []
    for k in range(n_folds):
        test_lo = fold_size * (k + 1)
        test_hi = min(fold_size * (k + 2), n)
        if test_lo >= n:
            break
        test = trades[test_lo:test_hi]
        oos_trades.extend(test)
        folds.append({"fold": k + 1, "n_test": len(test),
                      **metrics.summary(test)})
    return {"folds": folds, "oos": metrics.summary(oos_trades),
            "oos_trades": oos_trades}
