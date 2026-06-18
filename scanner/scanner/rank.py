"""
Ranked scanner output.

Builds the ranked table of CURRENTLY VALID setups in the spec's column format. A
live signal is only emitted if the setup it belongs to has cleared validation
(label TENTATIVE or ROBUST — i.e. at least eligible for paper observation) and
the signal is fresh (triggered on the most recent completed bar). Rows are
sorted by historical OOS expectancy (then profit factor) descending.

If nothing qualifies, callers print exactly: NO QUALIFYING SETUPS TODAY.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .setups.base import Signal
from .validation import LABEL_TENTATIVE, LABEL_ROBUST

COLUMNS = [
    "Ticker", "Direction", "Setup", "Entry", "Stop", "Target", "R:R",
    "Historical Win Rate", "Historical Expectancy", "Profit Factor", "Notes",
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
        rr = sig.reward_per_share / sig.risk_per_share if sig.risk_per_share else 0.0
        note = (f"{sig.notes}; status={ev.label}; n={ev.n_oos_trades}; "
                f"warn={ev.concentration_regime_warning}; "
                f"data_ts={data_timestamp}; entry=next-open forward order")
        rows.append({
            "Ticker": sig.symbol, "Direction": sig.direction.value,
            "Setup": sig.setup_name,
            "Entry": round(sig.entry_ref, 2), "Stop": round(sig.stop, 2),
            "Target": round(sig.target, 2),
            "R:R": f"1:{rr:.2f}",
            "Historical Win Rate": _fmt_pct(ev.oos_win_rate),
            "Historical Expectancy": f"{ev.oos_expectancy_r:.3f}R",
            "Profit Factor": round(ev.oos_profit_factor, 2),
            "Notes": note,
            "_exp": ev.oos_expectancy_r, "_pf": ev.oos_profit_factor,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["_exp", "_pf"], ascending=False).reset_index(drop=True)
        df = df[COLUMNS]
    else:
        df = pd.DataFrame(columns=COLUMNS)
    return df


def to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "NO QUALIFYING SETUPS TODAY"
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)
