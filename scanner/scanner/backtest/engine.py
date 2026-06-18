"""
Event-driven backtest engine.

Realism rules implemented here (per the tightened spec):
  * Entries fill at the open of the bar `delay_bars` after the signal bar
    (delayed fill); never on the signal bar itself (no look-ahead).
  * Costs (spread + slippage + commission + regulatory) hit both sides.
  * GAP-THROUGH-STOP: if the fill/holding bar OPENS beyond the stop, the trade
    exits at that open and the ACTUAL loss is recorded — which may be worse
    than -1R. We never assume a fixed -1R.
  * GAP-THROUGH-TARGET: symmetric; a favorable gap can exceed the planned 3R.
  * SAME-BAR STOP+TARGET ambiguity on a single bar is resolved CONSERVATIVELY
    (assume the stop filled first) unless finer-resolution data is supplied.
  * TIME STOP: exit at the close of the last allowed bar.
  * Portfolio risk controls (RiskController) gate every entry.

Realized R is measured in units of PLANNED risk-per-share so that planned 3R
targets and realized outcomes are directly comparable but never conflated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..costs import CostModel, DEFAULT_COSTS
from ..setups.base import Setup, Signal, Direction
from ..sizing import RiskConfig, RiskController, shares_for_trade


@dataclass
class Trade:
    symbol: str
    sector: str
    setup: str
    direction: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float          # cost-adjusted fill
    exit_price: float           # cost-adjusted fill
    stop: float
    target: float
    shares: int
    planned_risk_per_share: float
    planned_r_multiple: float
    realized_r: float           # net of costs, in planned-risk units
    pnl_dollars: float
    bars_held: int
    exit_reason: str            # target | stop | gap_stop | gap_target | time | eod
    regime: str
    year: int
    worse_than_1r: bool         # actual loss exceeded planned 1R (gap tail)


class BacktestEngine:
    def __init__(self,
                 cost: Optional[CostModel] = None,
                 risk: Optional[RiskConfig] = None,
                 sector_map: Optional[Dict[str, str]] = None,
                 starting_equity: float = 100_000.0,
                 enforce_portfolio_risk: bool = True):
        self.cost = cost or DEFAULT_COSTS
        self.risk_cfg = risk or RiskConfig()
        self.sector_map = sector_map or {}
        self.starting_equity = starting_equity
        self.enforce_portfolio_risk = enforce_portfolio_risk

    # -- single-trade simulation ------------------------------------------
    def _simulate_exit(self, bars: pd.DataFrame, fill_pos: int, sig: Signal):
        is_long = sig.direction is Direction.LONG
        stop, target = sig.stop, sig.target
        raw_entry = float(bars["open"].iloc[fill_pos])
        entry_fill = self.cost.effective_entry(raw_entry, is_long)
        last_pos = min(fill_pos + sig.time_stop_bars, len(bars) - 1)

        for pos in range(fill_pos, last_pos + 1):
            bar = bars.iloc[pos]
            o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])

            # --- gap handling at the bar open ---
            if is_long:
                if o <= stop:
                    return entry_fill, self.cost.effective_exit(o, is_long), pos, "gap_stop"
                if o >= target:
                    return entry_fill, self.cost.effective_exit(o, is_long), pos, "gap_target"
            else:
                if o >= stop:
                    return entry_fill, self.cost.effective_exit(o, is_long), pos, "gap_stop"
                if o <= target:
                    return entry_fill, self.cost.effective_exit(o, is_long), pos, "gap_target"

            # --- intrabar touches (skip entry bar's pre-open already handled) ---
            if is_long:
                stop_hit, tgt_hit = l <= stop, h >= target
            else:
                stop_hit, tgt_hit = h >= stop, l <= target

            if stop_hit and tgt_hit:
                # conservative: assume stop filled first
                return entry_fill, self.cost.effective_exit(stop, is_long), pos, "stop"
            if stop_hit:
                return entry_fill, self.cost.effective_exit(stop, is_long), pos, "stop"
            if tgt_hit:
                return entry_fill, self.cost.effective_exit(target, is_long), pos, "target"

        # time stop -> exit at last allowed bar close
        exit_raw = float(bars["close"].iloc[last_pos])
        return entry_fill, self.cost.effective_exit(exit_raw, is_long), last_pos, "time"

    # -- portfolio run -----------------------------------------------------
    def run(self,
            signals_by_symbol: Dict[str, List[Signal]],
            bars_by_symbol: Dict[str, pd.DataFrame]) -> List[Trade]:
        """Simulate all signals on a shared timeline with portfolio risk gating."""
        # flatten + sort by signal time for deterministic sequential processing
        flat: List[Signal] = [s for sym in signals_by_symbol
                              for s in signals_by_symbol[sym]]
        flat.sort(key=lambda s: s.signal_time)

        controller = RiskController(self.risk_cfg, self.sector_map)
        equity = self.starting_equity
        trades: List[Trade] = []

        for sig in flat:
            bars = bars_by_symbol[sig.symbol]
            idx = bars.index
            if sig.signal_time not in idx:
                continue
            sig_pos = idx.get_loc(sig.signal_time)
            fill_pos = sig_pos + self.cost.delay_bars
            if fill_pos >= len(bars):
                continue  # missed fill: no bar to fill on

            controller.roll_clock(sig.signal_time)
            planned_rps = abs(sig.entry_ref - sig.stop)
            if planned_rps <= 0:
                continue
            shares = shares_for_trade(equity, sig.entry_ref, sig.stop, self.risk_cfg)
            if shares <= 0:
                continue
            planned_risk_dollars = shares * planned_rps

            if self.enforce_portfolio_risk:
                ok, _reason = controller.can_open(sig.symbol, equity, planned_risk_dollars)
                if not ok:
                    continue  # skipped/missed due to risk limits

            entry_fill, exit_fill, exit_pos, reason = self._simulate_exit(bars, fill_pos, sig)
            is_long = sig.direction is Direction.LONG
            gross = (exit_fill - entry_fill) * shares * (1 if is_long else -1)
            commissions = self.cost.commission(shares) * 2
            reg = (self.cost.regulatory(shares, entry_fill, is_sell=not is_long)
                   + self.cost.regulatory(shares, exit_fill, is_sell=is_long))
            pnl = gross - commissions - reg
            realized_r = pnl / planned_risk_dollars

            controller.open(sig.symbol, planned_risk_dollars)
            controller.close(sig.symbol, realized_r)
            equity += pnl

            exit_time = bars.index[exit_pos]
            trades.append(Trade(
                symbol=sig.symbol, sector=self.sector_map.get(sig.symbol.upper(), "UNKNOWN"),
                setup=sig.setup_name, direction=sig.direction.value,
                signal_time=sig.signal_time, entry_time=bars.index[fill_pos],
                exit_time=exit_time, entry_price=entry_fill, exit_price=exit_fill,
                stop=sig.stop, target=sig.target, shares=shares,
                planned_risk_per_share=planned_rps,
                planned_r_multiple=sig.planned_r_multiple,
                realized_r=realized_r, pnl_dollars=pnl,
                bars_held=exit_pos - fill_pos, exit_reason=reason,
                regime=sig.regime_at_signal, year=sig.signal_time.year,
                worse_than_1r=(realized_r < -1.0),
            ))
        return trades


def trades_to_frame(trades: List[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    return pd.DataFrame([t.__dict__ for t in trades])
