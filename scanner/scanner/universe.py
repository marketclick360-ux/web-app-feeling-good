"""
Tradable universe construction and liquidity / exclusion filters.

Defaults follow the spec:
  * U.S.-listed stocks and ETFs only
  * Average daily dollar volume >= $10M (trailing 20 sessions)
  * Exclude penny stocks (price < $5), illiquid names, and leveraged ETFs
    (unless explicitly allowed for a separate test)

The point-in-time filter takes an `as_of` timestamp so the universe is rebuilt
without survivorship bias — a name only qualifies if it met the thresholds
using data available up to that date.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

import pandas as pd

from .data.base import DataAdapter
from . import params

# A non-exhaustive blocklist of common leveraged / inverse ETFs. For production
# use, source this from the provider's reference data. Leveraged ETFs are
# excluded by default and only tested separately.
LEVERAGED_ETFS = {
    "TQQQ", "SQQQ", "SPXL", "SPXU", "UPRO", "SPXS", "UDOW", "SDOW",
    "TNA", "TZA", "SOXL", "SOXS", "LABU", "LABD", "FAS", "FAZ",
    "UVXY", "SVXY", "TMF", "TMV", "NUGT", "DUST", "YINN", "YANG",
}


@dataclass
class UniverseConfig:
    min_adv_dollar: float = params.MIN_AVG_DOLLAR_VOLUME   # $20M
    min_price: float = params.MIN_PRICE                    # $10
    adv_window: int = 20
    allow_leveraged: bool = False
    candidates: List[str] = field(default_factory=list)


def default_candidates() -> List[str]:
    """A liquid starter watchlist (broad ETFs + large/mid-cap single names).
    Replace with a full provider symbol list for production scans."""
    etfs = ["SPY", "QQQ", "IWM", "DIA", "VTI", "XLF", "XLK", "XLE", "XLV",
            "XLI", "XLY", "XLP", "XLB", "XLU", "XLRE", "XLC", "SMH", "GLD",
            "SLV", "TLT", "HYG", "EEM", "EFA", "ARKK", "IBB"]
    stocks = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD",
              "AVGO", "JPM", "BAC", "XOM", "CVX", "UNH", "JNJ", "PG", "KO",
              "HD", "COST", "WMT", "CRM", "NFLX", "DIS", "INTC", "QCOM",
              "MU", "BA", "CAT", "GE", "F"]
    return etfs + stocks


def filter_universe(adapter: DataAdapter,
                    as_of: pd.Timestamp,
                    cfg: Optional[UniverseConfig] = None,
                    candidates: Optional[Iterable[str]] = None) -> List[str]:
    """Return symbols that pass the liquidity/exclusion filters at `as_of`."""
    cfg = cfg or UniverseConfig()
    syms = list(candidates or cfg.candidates or default_candidates())
    passed: List[str] = []
    for sym in syms:
        su = sym.upper()
        if not cfg.allow_leveraged and su in LEVERAGED_ETFS:
            continue
        if not adapter.is_tradable(sym, as_of=as_of):
            continue
        bars = adapter.get_bars(
            sym, "1d",
            start=as_of - pd.Timedelta(days=cfg.adv_window * 4 + 20),
            end=as_of, as_of=as_of,
        ).df
        if len(bars) < cfg.adv_window:
            continue
        last_price = float(bars["close"].iloc[-1])
        if last_price < cfg.min_price:
            continue
        adv = float((bars["close"] * bars["volume"]).tail(cfg.adv_window).mean())
        if adv < cfg.min_adv_dollar:
            continue
        passed.append(su)
    return passed
