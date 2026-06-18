"""
Ranked scanner output.

Builds the ranked table of CURRENTLY VALID setups. A live signal is only
emitted if the setup it belongs to has cleared validation (label TENTATIVE or
ROBUST — i.e. at least eligible for paper observation) and the signal is fresh
(triggered on the most recent completed bar). Rows are sorted by Setup Quality
Score descending.

If nothing qualifies, callers print exactly: NO QUALIFYING SETUPS TODAY.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .setups.base import Signal
from .validation import LABEL_TENTATIVE, LABEL_ROBUST

COLUMNS = [
    "Ticker", "Direction", "Setup Name", "Data Timestamp", "Market Regime",
    "Entry", "Stop", "Target", "Risk per Share", "Reward per Share",
    "Planned R:R", "Setup Quality Score", "Historical OOS Win Rate",
    "Historical OOS Expectancy (R)", "Historical OOS Profit Factor",
    "Number of OOS Trades", "Typical Hold Time", "Key Invalidation Condition",
    "Concentration / Regime Warning", "Forward-Observation Status", "Notes",
]

ELIGIBLE_LABELS = {LABEL_TENTATIVE, LABEL_ROBUST}


@dataclass
class SetupEvidence:
    """Validated evidence attached to a setup family for ranking."""
    label: str
    quality_total: Optional[float]
    oos_win_rate: float
    oos_expectancy_r: float
    oos_profit_factor: float
    n_oos_trades: int
    typical_hold: str
    concentration_regime_warning: str


def _fmt_pct(x: float) -> str:
    return f"{x:.1%}" if x == x else "n/a"


def build_table(live_signals: List[Signal],
                evidence_by_setup: Dict[str, SetupEvidence],
                data_timestamp: str) -> pd.DataFrame:
    rows = []
    for sig in live_signals:
        ev = evidence_by_setup.get(sig.setup_name)
        if ev is None or ev.label not in ELIGIBLE_LABELS:
            continue  # setup not validated -> never emit a live trade
        if ev.quality_total is None:
            continue  # missing-data quality -> not ranked
        rr = sig.reward_per_share / sig.risk_per_share if sig.risk_per_share else 0.0
        invalidation = (f"close back below {sig.stop:.2f}"
                        if sig.direction.value == "long"
                        else f"close back above {sig.stop:.2f}")
        rows.append({
            "Ticker": sig.symbol, "Direction": sig.direction.value,
            "Setup Name": sig.setup_name, "Data Timestamp": data_timestamp,
            "Market Regime": sig.regime_at_signal,
            "Entry": round(sig.entry_ref, 2), "Stop": round(sig.stop, 2),
            "Target": round(sig.target, 2),
            "Risk per Share": round(sig.risk_per_share, 2),
            "Reward per Share": round(sig.reward_per_share, 2),
            "Planned R:R": f"1:{rr:.2f}",
            "Setup Quality Score": ev.quality_total,
            "Historical OOS Win Rate": _fmt_pct(ev.oos_win_rate),
            "Historical OOS Expectancy (R)": round(ev.oos_expectancy_r, 3),
            "Historical OOS Profit Factor": round(ev.oos_profit_factor, 2),
            "Number of OOS Trades": ev.n_oos_trades,
            "Typical Hold Time": ev.typical_hold,
            "Key Invalidation Condition": invalidation,
            "Concentration / Regime Warning": ev.concentration_regime_warning,
            "Forward-Observation Status": ev.label,
            "Notes": sig.notes,
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty:
        df = df.sort_values("Setup Quality Score", ascending=False).reset_index(drop=True)
    return df


def to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "NO QUALIFYING SETUPS TODAY"
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)
