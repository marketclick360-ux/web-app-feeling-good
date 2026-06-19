"""Select a data adapter from config / environment."""
from __future__ import annotations

import os
from typing import Optional

from .base import DataAdapter


def get_adapter(source: Optional[str] = None, **kwargs) -> DataAdapter:
    """Return a DataAdapter.

    source: "polygon" (recommended for real data), "schwab" (broker OAuth),
            "csv" (offline files), or "synthetic" (deterministic demo/test
            data, no network).
    Falls back to env var SCANNER_DATA_SOURCE, then "synthetic".
    """
    source = (source or os.getenv("SCANNER_DATA_SOURCE") or "synthetic").lower()

    if source == "polygon":
        from .polygon_adapter import PolygonAdapter
        return PolygonAdapter(**kwargs)
    if source == "schwab":
        from .schwab_adapter import SchwabAdapter
        return SchwabAdapter(**kwargs)
    if source == "stooq":
        from .stooq_adapter import StooqAdapter
        return StooqAdapter(**kwargs)
    if source == "csv":
        from .csv_adapter import CSVAdapter
        root = kwargs.pop("root", None) or os.getenv("SCANNER_CSV_ROOT", "./data")
        return CSVAdapter(root=root, **kwargs)
    if source == "synthetic":
        from .synthetic import SyntheticAdapter
        return SyntheticAdapter(**kwargs)
    raise ValueError(f"unknown data source: {source!r}")
