"""Cost model: longs pay up on entry / sell down on exit; stress scales costs."""
from scanner.costs import CostModel


def test_long_pays_worse_fills():
    c = CostModel()
    assert c.effective_entry(100.0, is_long=True) > 100.0
    assert c.effective_exit(100.0, is_long=True) < 100.0


def test_short_pays_worse_fills():
    c = CostModel()
    assert c.effective_entry(100.0, is_long=False) < 100.0
    assert c.effective_exit(100.0, is_long=False) > 100.0


def test_min_commission_floor():
    c = CostModel(min_commission=1.0, commission_per_share=0.005)
    assert c.commission(10) == 1.0       # floor applies
    assert c.commission(1000) == 5.0     # per-share dominates


def test_stress_multiplier_increases_cost():
    base = CostModel().per_side_price_cost(100.0)
    stressed = CostModel(cost_multiplier=2.0).per_side_price_cost(100.0)
    assert stressed > base
    assert abs(stressed - 2 * base) < 1e-9


def test_regulatory_only_on_sells():
    c = CostModel()
    assert c.regulatory(100, 50.0, is_sell=False) == 0.0
    assert c.regulatory(100, 50.0, is_sell=True) > 0.0
