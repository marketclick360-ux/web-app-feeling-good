# Rule-Based Market Scanner

A skeptical, rule-based scanner and backtest/validation harness for liquid U.S.
stocks and ETFs. It designs objectively-defined long/short setups, backtests
them with realistic costs and gap behavior, subjects them to out-of-sample,
walk-forward, placebo, concentration, and overfitting tests, and then **ranks
only the survivors** — or prints `NO QUALIFYING SETUPS TODAY`.

> **Reality filter.** Backtests estimate historical behavior under stated cost
> assumptions; they do **not** prove future results. Nothing here is "proven to
> win," "guaranteed," or "safe." A setup that clears historical validation is at
> most *eligible for forward (paper) observation*, never certified for live
> trading. See `RESEARCH_REPORT.md`.

## Why this exists / relationship to `../trading`

The older `../trading` system combines Gann angles, VPA pattern reads, and other
**subjective chart interpretation**. This scanner deliberately rejects that
class of rule: every condition here is measurable, reproducible, and codeable
without discretion, and every accepted-looking edge must survive placebo and
concentration tests before it is ranked.

## Install

```bash
cd scanner
pip install -r requirements.txt          # pandas, numpy, pyyaml (+ requests for Polygon)
```

## Quick start (no data, no keys)

```bash
python -m scanner.cli demo --fast         # runs the whole pipeline on synthetic data
```

The demo prints a DATA INTEGRITY header, a per-setup research summary, the
ranked table (or `NO QUALIFYING SETUPS TODAY`), and the risk controls. On
synthetic random-walk data it correctly **rejects every setup** — that is the
intended behavior, demonstrating the system will not invent edges.

## Real data

```bash
export POLYGON_API_KEY=...                # recommended: adjusted, survivorship-bias-free
python -m scanner.cli research --source polygon
python -m scanner.cli scan     --source polygon
```

Offline files instead of an API:

```bash
export SCANNER_DATA_SOURCE=csv SCANNER_CSV_ROOT=/path/to/data
# layout: /path/to/data/1d/AAPL.csv (adjusted OHLCV), optional delistings.csv
python -m scanner.cli scan --source csv
```

If current data cannot be verified, the CLI prints
`CURRENT MARKET DATA NOT AVAILABLE — RESEARCH MODE ONLY` and refuses to present
any row as a live signal.

## Architecture

| Module | Responsibility |
|--------|----------------|
| `scanner/data/` | Pluggable adapters (`polygon`, `csv`, `synthetic`); adjusted OHLCV, `as_of` to prevent look-ahead, delisting-aware `is_tradable` |
| `scanner/indicators.py` | Vectorized indicators, no look-ahead/repaint; `*_prev` helpers are explicitly shifted |
| `scanner/regime.py` | Objective trend/vol regime tags from the benchmark |
| `scanner/universe.py` | Point-in-time liquidity ($10M ADV), penny-stock & leveraged-ETF exclusions |
| `scanner/setups/` | Six objective setup families (see below) |
| `scanner/costs.py` | Commissions/fees, spread, slippage, fill delay, stress multiplier |
| `scanner/sizing.py` | Fixed-fractional sizing + portfolio risk controls |
| `scanner/backtest/engine.py` | Event-driven engine: delayed fills, gap-through-stop (real loss, not −1R), conservative same-bar resolution, time stops |
| `scanner/backtest/` | Metrics, walk-forward, bootstrap/MC, placebo, concentration, overfitting (deflated Sharpe, PBO) |
| `scanner/quality.py` | Setup Quality Score (math-defined 25/20/15/15/10/10/5) |
| `scanner/validation.py` | Accept/reject labeling |
| `scanner/rank.py` | Ranked output table |
| `scanner/pipeline.py` | Orchestration (`research`, `live_signals`) |
| `scanner/cli.py` | CLI + data-integrity header |

## Configurable parameters (`scanner/params.py`)

One source of truth, referenced everywhere: `MIN_PRICE = $10`,
`MIN_AVG_DOLLAR_VOLUME = $20M`, `EARNINGS_EXCLUSION_DAYS = 10`,
`MIN_PROFIT_FACTOR = 1.30`, and the three slippage scenarios
(`low 0.05% / normal 0.10% / stressed 0.25%` per side; acceptance is judged on
**stressed**).

## Setup families

Default daily-swing research set (the five spec families):

1. `trend_pullback` — pullback to the EMA20 (RSI cooled) inside an ADX trend
2. `vcp_breakout` — volatility contraction (low Bollinger bandwidth) + volume break
3. `relative_strength_breakout` — RS-line new high vs SPY **and** price breakout
4. `ma_pullback` — touch-and-hold of the 10/20-day MA in a strong ADX trend
5. `sector_leader_continuation` — RS-vs-sector new high + sector ETF uptrend + breakout

Also available (not in the default set): `volume_breakout`, `mean_reversion`,
and `opening_range_breakout` (intraday only).

## No forced reward-to-risk target

There is **no minimum-R requirement**. Forcing a >50% win rate at a fixed 3R
target is an extremely high hurdle that invites curve-fitting, so each setup
defines its own objective target rule (an ATR-based R multiple fitting its
hypothesis) and acceptance is decided by expectancy, profit factor, and
robustness — never by manufacturing a 3R target.

## Acceptance gates (all must hold for ROBUST)

- OOS net expectancy > 0 after costs; profit factor ≥ `MIN_PROFIT_FACTOR` (1.30)
- Profitable under the **stressed** (0.25%/side) cost scenario
- OOS win rate > 50% **or** payoff distribution justifies positive expectancy
- ≥ 100 OOS trades (300+ preferred)
- 95% CI lower bound for expectancy > 0 (else `STATISTICALLY INCONCLUSIVE`)
- Not driven by one ticker/sector/year/winner/regime (concentration test)
- Survives placebo test (special condition adds value over a matched control)
- Holdout positive or honestly labeled inconclusive
- Parameter-stable; PBO not high

The scanner is rewarded for **rejecting** weak ideas, not for producing trades:
`NO QUALIFYING SETUPS TODAY` is a successful outcome.

Labels: `REJECTED` · `STATISTICALLY INCONCLUSIVE` · `TENTATIVE — FOR PAPER
OBSERVATION ONLY` · `ROBUST — ELIGIBLE FOR FORWARD OBSERVATION ONLY`.

## Tests

```bash
python -m pytest tests -q
```

Includes a numerical **no-look-ahead** guard, cost-model, sizing/risk-control,
and engine gap/same-bar/time-stop mechanics tests.

## Limitations

- The default candidate list is a small liquid watchlist; supply a full
  provider symbol universe for production scans.
- Earnings exclusion is enforced only when an earnings calendar is provided in
  context; otherwise it is disclosed as a limitation.
- The synthetic adapter is for plumbing/CI only — never interpret its numbers
  as evidence about real markets.
- Intraday ORB requires reliable intraday history; with daily-only data it is
  not testable and is excluded.
