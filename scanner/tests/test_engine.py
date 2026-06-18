"""Engine fill mechanics: gaps, same-bar ambiguity, time stop, planned-vs-real R."""
import pandas as pd

from scanner.costs import CostModel
from scanner.backtest.engine import BacktestEngine
from scanner.setups.base import Signal, Direction


def _bars(rows):
    idx = pd.date_range("2024-01-02", periods=len(rows), freq="B", tz="UTC")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close", "volume"])


# zero-cost engine so we can assert exact level mechanics
ENGINE = BacktestEngine(cost=CostModel(commission_per_share=0, min_commission=0,
                                       sec_taf_bps=0, spread_bps=0, slippage_bps=0,
                                       delay_bars=1))


def _sig(entry_ref, stop, target, direction=Direction.LONG, bars=5):
    return Signal("T", direction, "t", pd.Timestamp("2024-01-02", tz="UTC"),
                  entry_ref, stop, target, planned_r_multiple=3.0, time_stop_bars=bars)


def test_target_hit_is_three_r():
    # signal bar index 0, fill at index 1 open=100, stop=99 (1R=1), target=103 (3R)
    bars = _bars([
        [100, 100, 100, 100, 1e6],   # signal bar
        [100, 100, 100, 100, 1e6],   # fill bar open=100
        [100, 103.5, 99.5, 103, 1e6],# target 103 touched, stop not
        [103, 104, 102, 103, 1e6],
    ])
    sig = _sig(100, 99, 103)
    entry, exit_, pos, reason = ENGINE._simulate_exit(bars, fill_pos=1, sig=sig)
    assert reason == "target"
    assert abs((exit_ - entry) / (100 - 99) - 3.0) < 1e-9


def test_gap_through_stop_records_real_loss_worse_than_1r():
    bars = _bars([
        [100, 100, 100, 100, 1e6],
        [100, 100, 100, 100, 1e6],   # fill bar open=100
        [96, 96, 95, 95.5, 1e6],     # gaps down to 96, below stop 99 -> exit at 96 = -4R
    ])
    sig = _sig(100, 99, 103)
    entry, exit_, pos, reason = ENGINE._simulate_exit(bars, fill_pos=1, sig=sig)
    assert reason == "gap_stop"
    realized_r = (exit_ - entry) / (100 - 99)
    assert realized_r < -1.0  # gap tail: worse than nominal -1R


def test_same_bar_stop_and_target_is_conservative():
    bars = _bars([
        [100, 100, 100, 100, 1e6],
        [100, 100, 100, 100, 1e6],
        [100, 103.5, 98.5, 100, 1e6],  # both stop (99) and target (103) inside the bar
    ])
    sig = _sig(100, 99, 103)
    _, exit_, _, reason = ENGINE._simulate_exit(bars, fill_pos=1, sig=sig)
    assert reason == "stop"  # conservative: assume stop first
    assert abs(exit_ - 99) < 1e-9


def test_time_stop_exit_at_last_bar_close():
    bars = _bars([[100]*4 + [1e6]] + [[100, 101, 99.5, 100.5, 1e6]] * 5)
    sig = _sig(100, 95, 130, bars=2)  # never reached; exits on time
    _, exit_, pos, reason = ENGINE._simulate_exit(bars, fill_pos=1, sig=sig)
    assert reason == "time"
    assert pos == 1 + 2  # fill_pos + time_stop_bars


def test_full_run_realized_r_sign():
    bars = _bars([
        [100, 100, 100, 100, 5e6],
        [100, 100, 100, 100, 5e6],
        [100, 103.5, 99.5, 103, 5e6],
    ])
    sig = _sig(100, 99, 103)
    trades = ENGINE.run({"T": [sig]}, {"T": bars})
    assert len(trades) == 1
    assert trades[0].realized_r > 2.9
    assert trades[0].exit_reason == "target"
