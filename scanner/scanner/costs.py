"""
Realistic execution-cost model.

Captures the frictions the spec requires: commissions/fees, bid-ask spread,
slippage, delayed fills, and (via the engine) gap behavior and partial/missed
fills. Costs are applied on BOTH entry and exit.

All values are configurable and intentionally conservative defaults for liquid
U.S. equities/ETFs. They are estimates — real costs vary by broker, venue,
order type, size, and market conditions. Stress-test by scaling them up
(see CLI `--cost-stress`) and confirm the edge survives.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import params


@dataclass
class CostModel:
    commission_per_share: float = 0.005    # IBKR-tiered-ish; min handled below
    min_commission: float = 1.0            # per order
    sec_taf_bps: float = 0.02              # regulatory fees on sells (bps of notional)
    spread_bps: float = 2.0                # half-spread paid on each side (bps)
    slippage_frac: float = 0.0010          # slippage PER SIDE as fraction of price
    delay_bars: int = 1                    # fill delay: signal bar t -> fill at t+delay open
    cost_multiplier: float = 1.0           # global stress knob (kept for ad-hoc stress)

    def per_side_price_cost(self, price: float) -> float:
        """Price degradation per share from spread + slippage (one side)."""
        spread = self.spread_bps / 10_000.0
        return price * (spread + self.slippage_frac) * self.cost_multiplier

    def commission(self, shares: int) -> float:
        c = max(self.min_commission, shares * self.commission_per_share)
        return c * self.cost_multiplier

    def regulatory(self, shares: int, price: float, is_sell: bool) -> float:
        if not is_sell:
            return 0.0
        return shares * price * (self.sec_taf_bps / 10_000.0) * self.cost_multiplier

    def effective_entry(self, ref_price: float, is_long: bool) -> float:
        """Worse fill: longs pay up, shorts sell down."""
        adj = self.per_side_price_cost(ref_price)
        return ref_price + adj if is_long else ref_price - adj

    def effective_exit(self, ref_price: float, is_long: bool) -> float:
        adj = self.per_side_price_cost(ref_price)
        return ref_price - adj if is_long else ref_price + adj


def scenario_costs(scenario: str) -> CostModel:
    """Return a CostModel for one of the named slippage scenarios
    ('low' 0.05% / 'normal' 0.10% / 'stressed' 0.25% per side)."""
    if scenario not in params.COST_SCENARIOS:
        raise ValueError(f"unknown cost scenario {scenario!r}")
    return CostModel(slippage_frac=params.COST_SCENARIOS[scenario])


DEFAULT_COSTS = scenario_costs("normal")

