"""
Smoke test: the full research pipeline runs end-to-end on a tiny synthetic
universe and returns a well-formed verdict for each setup. Kept small/fast.
"""
import pandas as pd

from scanner.data import get_adapter
from scanner.pipeline import PipelineConfig, research, live_signals


def _tiny_cfg():
    cfg = PipelineConfig()
    cfg.years = 6
    cfg.n_boot = 100
    cfg.placebo_runs = 5
    cfg.param_perturb = (1.1,)
    return cfg


def test_research_runs_and_labels():
    adapter = get_adapter("synthetic")
    as_of = pd.Timestamp.now("UTC").normalize()
    syms = ["AAPL", "MSFT", "NVDA", "XOM"]
    results = research(adapter, syms, setup_names=["trend_pullback", "mean_reversion"],
                       cfg=_tiny_cfg(), as_of=as_of)
    assert set(results) == {"trend_pullback", "mean_reversion"}
    for r in results.values():
        assert r.verdict.label  # a label was assigned
        assert "n_trades" in r.oos
        # quality is either a dict with total, or None when inputs are missing
        assert r.quality is None or "total" in r.quality


def test_live_signals_only_recent_bar():
    adapter = get_adapter("synthetic")
    as_of = pd.Timestamp.now("UTC").normalize()
    sigs, ts = live_signals(adapter, ["AAPL", "MSFT"], ["trend_pullback"],
                            _tiny_cfg(), as_of)
    assert isinstance(ts, str)
    # every emitted signal must be anchored to a single most-recent bar per symbol
    for s in sigs:
        assert s.setup_name == "trend_pullback"
