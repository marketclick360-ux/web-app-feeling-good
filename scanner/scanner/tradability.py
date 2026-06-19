"""
Small-account tradability score.

A setup can have edge yet still be impractical for a small account. This scores
how tradable a ticker/setup is for a small account, using ONLY what daily OHLCV
data actually contains. Things that require a live quote or an options chain
(bid/ask spread, options volume/OI/IV) are reported as UNKNOWN — never faked.

Components (0..1 each, weighted to 100):
  25  affordability   — can you buy a meaningful share position?
  20  dollar volume   — >= $100M/day preferred (tight markets, clean fills)
  20  movement (ATR%) — moves enough to matter, not so much it's wild
  20  risk sizing     — stop is small enough to size >=1 share at 0.25-1% risk
  15  stop tightness  — stop distance as % of price not excessive
Reported separately (not scored): spread, options, earnings, gap — UNKNOWN/
flagged unless live data is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

DEFAULT_ACCOUNT = 2000.0  # small account; override via --account


def _clip01(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


@dataclass
class Tradability:
    score: float
    grade: str
    shares_at_risk: Dict[str, int]   # "0.25%" -> shares, etc.
    components: Dict[str, float]
    flags: list = field(default_factory=list)
    unknown: list = field(default_factory=list)


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def score(price: float, adv_dollar: float, atr: float, stop_distance: float,
          account: float = DEFAULT_ACCOUNT,
          price_min: float = 10.0, price_max: float = 250.0) -> Tradability:
    flags, unknown = [], []
    c = {}

    # 25 — affordability: at least a few shares buyable with the account
    if price <= 0:
        afford = 0.0
    elif price > price_max:
        afford = _clip01(price_max / price) * 0.5
        flags.append(f"price ${price:.0f} > ${price_max:.0f} (use a cheaper proxy, e.g. SPLG/QQQM)")
    elif price < price_min:
        afford = 0.3
        flags.append(f"price ${price:.2f} < ${price_min:.0f} (penny-ish)")
    else:
        # more shares affordable -> better; ~20+ shares = full credit
        afford = _clip01((account / price) / 20.0)
    c["affordability_25"] = round(afford * 25, 1)

    # 20 — dollar volume (>= $100M full credit)
    c["dollar_volume_20"] = round(_clip01(adv_dollar / 100_000_000.0) * 20, 1)
    if adv_dollar < 20_000_000:
        flags.append(f"thin liquidity (${adv_dollar/1e6:.0f}M/day)")

    # 20 — movement: ATR% sweet spot ~1%-5%
    atr_pct = atr / price if price > 0 else 0.0
    if atr_pct <= 0:
        mv = 0.0
    elif atr_pct < 0.005:
        mv = _clip01(atr_pct / 0.005) * 0.5
        flags.append(f"barely moves (ATR {atr_pct:.1%})")
    elif atr_pct <= 0.05:
        mv = 1.0
    else:
        mv = _clip01(1.0 - (atr_pct - 0.05) / 0.05)
        flags.append(f"very volatile (ATR {atr_pct:.1%})")
    c["movement_20"] = round(mv * 20, 1)

    # 20 — risk sizing: can you size >= 1 share at small risk %?
    shares_at = {}
    for pct, key in ((0.0025, "0.25%"), (0.005, "0.5%"), (0.01, "1.0%")):
        dollar_risk = account * pct
        shares_at[key] = int(dollar_risk // stop_distance) if stop_distance > 0 else 0
    sizeable = _clip01(shares_at["0.5%"] / 3.0)  # >=3 shares at 0.5% = full
    if shares_at["1.0%"] < 1:
        flags.append("cannot size even 1 share at 1% risk on this account")
    c["risk_sizing_20"] = round(sizeable * 20, 1)

    # 15 — stop tightness (% of price); wide stops eat small accounts
    stop_pct = stop_distance / price if price > 0 else 1.0
    tight = _clip01(1.0 - stop_pct / 0.12)   # 12% stop -> 0 credit
    c["stop_tightness_15"] = round(tight * 15, 1)

    # not scored — require live data
    unknown += ["bid/ask spread (needs live quote)",
                "options volume/OI/IV (needs options chain)",
                "earnings date (needs earnings calendar)"]

    total = round(sum(c.values()), 1)
    return Tradability(score=total, grade=_grade(total), shares_at_risk=shares_at,
                       components=c, flags=flags, unknown=unknown)
