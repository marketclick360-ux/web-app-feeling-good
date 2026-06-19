"""Data access layer: pluggable adapters returning adjusted OHLCV bars."""
from .base import DataAdapter, BarsResult
from .factory import get_adapter

__all__ = ["DataAdapter", "BarsResult", "get_adapter"]
