"""
Top-level configurable parameters.

These are the single source of truth referenced throughout the package instead
of hard-coded literals, so an independent researcher can change one value and
have it propagate to the universe filter, validation gates, and reports.

Philosophy note: there is intentionally NO minimum reward-to-risk requirement
here. Forcing a >50% win rate at a fixed 3R target is an extremely high hurdle
that invites curve-fitting; instead each setup defines its own objective target
rule and a setup is accepted only on positive net expectancy, profit factor,
consistency, and concentration/cost resilience. The scanner is rewarded for
rejecting weak ideas, not for producing trades.
"""
from __future__ import annotations

# Universe filters
MIN_PRICE = 10.0                      # USD; exclude sub-$10 names
MIN_AVG_DOLLAR_VOLUME = 20_000_000.0  # 20-session average daily dollar volume
EARNINGS_EXCLUSION_DAYS = 10          # trading days around earnings to avoid

# Acceptance
MIN_PROFIT_FACTOR = 1.30
MIN_OOS_TRADES = 100                  # below this -> STATISTICALLY INCONCLUSIVE
PREFERRED_OOS_TRADES = 300

# Slippage scenarios, fraction-of-price PER SIDE (applied to entry and exit).
COST_SCENARIOS = {
    "low": 0.0005,       # 0.05%
    "normal": 0.0010,    # 0.10%
    "stressed": 0.0025,  # 0.25% — acceptance must hold here
}
ACCEPTANCE_SCENARIO = "stressed"

# Daily-bar session convention used to generate signals.
SIGNAL_CLOSE = "16:00 America/New_York (official U.S. equity close)"
EXECUTION_RULE = "signals from close of bar t are executed at the open of bar t+1"
