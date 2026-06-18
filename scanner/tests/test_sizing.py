"""Position sizing + portfolio risk controls."""
import pandas as pd

from scanner.sizing import RiskConfig, RiskController, shares_for_trade


def test_fixed_fractional_sizing():
    cfg = RiskConfig(risk_per_trade_pct=0.01)
    # 1% of 100k = $1000 risk; risk/share = $2 -> 500 shares
    assert shares_for_trade(100_000, entry=100.0, stop=98.0, cfg=cfg) == 500


def test_zero_risk_per_share_is_safe():
    cfg = RiskConfig()
    assert shares_for_trade(100_000, entry=100.0, stop=100.0, cfg=cfg) == 0


def test_total_open_risk_cap():
    cfg = RiskConfig(max_total_open_risk_pct=0.06, max_positions=99)
    rc = RiskController(cfg)
    rc.roll_clock(pd.Timestamp("2024-01-02", tz="UTC"))
    equity = 100_000
    # open 6 positions each at 1% planned risk = 6% total
    for i in range(6):
        ok, _ = rc.can_open(f"S{i}", equity, 1000.0)
        assert ok
        rc.open(f"S{i}", 1000.0)
    # 7th would exceed 6%
    ok, reason = rc.can_open("S7", equity, 1000.0)
    assert not ok and reason == "max_total_open_risk"


def test_no_pyramiding():
    rc = RiskController(RiskConfig())
    rc.roll_clock(pd.Timestamp("2024-01-02", tz="UTC"))
    rc.open("AAPL", 500.0)
    ok, reason = rc.can_open("AAPL", 100_000, 500.0)
    assert not ok and reason == "already_open"


def test_daily_loss_limit_blocks_new_entries():
    cfg = RiskConfig(daily_loss_limit_r=3.0)
    rc = RiskController(cfg)
    rc.roll_clock(pd.Timestamp("2024-01-02", tz="UTC"))
    rc.open("X", 500.0)
    rc.close("X", -3.0)  # hit the daily limit
    ok, reason = rc.can_open("Y", 100_000, 500.0)
    assert not ok and reason == "daily_loss_limit"


def test_sector_cap():
    cfg = RiskConfig(max_sector_risk_pct=0.02, max_total_open_risk_pct=0.99,
                     max_positions=99)
    rc = RiskController(cfg, sector_map={"AAPL": "Tech", "MSFT": "Tech"})
    rc.roll_clock(pd.Timestamp("2024-01-02", tz="UTC"))
    rc.open("AAPL", 2000.0)  # 2% of 100k in Tech
    ok, reason = rc.can_open("MSFT", 100_000, 100.0)
    assert not ok and reason == "max_sector_risk"
