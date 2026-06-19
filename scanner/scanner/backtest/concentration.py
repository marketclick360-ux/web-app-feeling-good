"""
Concentration tests.

A robust edge must not depend on a handful of trades, one ticker, one sector,
or one year. Each test removes a slice of the BEST results and recomputes
expectancy; if expectancy collapses (especially below zero), the edge is
concentration-driven and is rejected.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .engine import Trade, trades_to_frame


def _exp(df: pd.DataFrame) -> float:
    return float(df["realized_r"].mean()) if len(df) else float("nan")


def run_concentration(trades: List[Trade]) -> Dict[str, dict]:
    df = trades_to_frame(trades)
    if df.empty:
        return {}
    base = _exp(df)
    out: Dict[str, dict] = {"baseline": {"expectancy_r": base, "n": len(df)}}

    # remove top winners
    r_sorted = df.sort_values("realized_r", ascending=False)
    for pct in (0.01, 0.05, 0.10):
        k = int(np.ceil(len(df) * pct))
        trimmed = r_sorted.iloc[k:]
        out[f"drop_top_{int(pct*100)}pct_winners"] = {
            "expectancy_r": _exp(trimmed), "removed": k}

    # remove best contributor in each grouping
    for dim in ("symbol", "sector", "year"):
        if dim not in df.columns:
            continue
        n_groups = int(df[dim].nunique(dropna=True))
        if dim == "symbol" and n_groups < 2:
            # A single ticker IS maximal concentration. Force a failing test so
            # one-name edges (e.g. an all-SLV result) can never pass the gate.
            out["drop_best_symbol"] = {
                "removed": (df[dim].iloc[0] if len(df) else None),
                "expectancy_r": float("nan"), "n": 0,
                "note": "only one symbol — maximal concentration"}
            continue
        if n_groups < 2:
            # sector / year with a single group: cross-group robustness simply
            # cannot be tested (removing the only group leaves nothing), and a
            # single sector or a one-year OOS window is NOT "one name driving
            # the edge". Skip rather than fail, so a setup that is diversified
            # across many tickers isn't wrongly REJECTED for spanning one
            # sector or a short window. (Thin-sample / regime concerns are
            # handled by their own gates.)
            continue
        contrib = df.groupby(dim)["realized_r"].sum()
        best = contrib.idxmax()
        kept = df[df[dim] != best]
        out[f"drop_best_{dim}"] = {"removed": best, "expectancy_r": _exp(kept),
                                   "n": len(kept)}

    # pass = expectancy stays positive under every APPLICABLE stress
    stresses = [v["expectancy_r"] for k, v in out.items() if k != "baseline"]
    out["passes"] = bool(all((not np.isnan(x)) and x > 0 for x in stresses))
    return out
