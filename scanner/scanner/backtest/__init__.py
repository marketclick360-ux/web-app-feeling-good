"""Event-driven backtest engine, metrics, and robustness tooling."""
from .engine import BacktestEngine, Trade
from . import metrics

__all__ = ["BacktestEngine", "Trade", "metrics"]
