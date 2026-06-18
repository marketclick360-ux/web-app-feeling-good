"""Objective trade-setup families. Each emits fully-specified, rule-based signals."""
from .base import Setup, Signal, Direction
from .registry import ALL_SETUPS, get_setup

__all__ = ["Setup", "Signal", "Direction", "ALL_SETUPS", "get_setup"]
