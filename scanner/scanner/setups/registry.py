"""Registry of available setup families."""
from __future__ import annotations

from .trend_pullback import TrendPullback
from .vcp_breakout import VCPBreakout
from .opening_range import OpeningRangeBreakout
from .mean_reversion import MeanReversion
from .relative_strength import RelativeStrengthBreakout
from .volume_breakout import VolumeBreakout
from .ma_pullback import MAPullback
from .sector_leader import SectorLeaderContinuation

ALL_SETUPS = {
    TrendPullback.name: TrendPullback,
    VCPBreakout.name: VCPBreakout,
    RelativeStrengthBreakout.name: RelativeStrengthBreakout,
    MAPullback.name: MAPullback,
    SectorLeaderContinuation.name: SectorLeaderContinuation,
    VolumeBreakout.name: VolumeBreakout,
    MeanReversion.name: MeanReversion,
    OpeningRangeBreakout.name: OpeningRangeBreakout,
}

# Families that require intraday data (excluded from daily-bar backtests).
INTRADAY_ONLY = {OpeningRangeBreakout.name}

# The five daily-swing families from the spec — the default research set.
DEFAULT_RESEARCH_SETUPS = [
    TrendPullback.name,
    VCPBreakout.name,
    RelativeStrengthBreakout.name,
    MAPullback.name,
    SectorLeaderContinuation.name,
]


def get_setup(name: str, **overrides):
    if name not in ALL_SETUPS:
        raise KeyError(f"unknown setup {name!r}; choices: {list(ALL_SETUPS)}")
    return ALL_SETUPS[name](**overrides)
