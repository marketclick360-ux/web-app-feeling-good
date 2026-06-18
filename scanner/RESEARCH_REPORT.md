# Research Report — Rule-Based Market Scanner

**Scope.** This report documents the methodology, the rule set for every
candidate setup, the validation protocol, and the standing conclusion. It is
written to be regenerated whenever the pipeline is run against a real data
adapter; the numeric results section is populated by `python -m scanner.cli
research --source <polygon|csv>`.

> Backtests estimate historical behavior under explicit cost assumptions. They
> do **not** prove future results. No setup is labeled "proven," "guaranteed,"
> or "safe." The strongest label this system issues is **ROBUST — ELIGIBLE FOR
> FORWARD OBSERVATION ONLY**, meaning paper trading is the next step, not live
> capital.

---

## 1. Data integrity

Every run begins with a header stating: data source, universe source, candidate
count, data timestamp, timezone/session convention, and whether **live data was
verified**. Only completed bars are used. If a real source is not reachable the
run is marked `CURRENT MARKET DATA NOT AVAILABLE — RESEARCH MODE ONLY` and no
row is presented as a live signal.

Distinctions maintained throughout:
- **Historical research results** — backtest output on past data.
- **Current scanner signals** — fresh triggers on the most recent completed
  bar; entry is the *next* session open via a forward order.
- **Untested hypotheses** — setup ideas not yet validated.
- **Paper / forward-observation candidates** — setups that cleared validation
  but have *not* been live-traded.

## 2. Universe & data

Configurable parameters (`scanner/params.py`) — one source of truth:
`MIN_PRICE = $10`, `MIN_AVG_DOLLAR_VOLUME = $20M`, `EARNINGS_EXCLUSION_DAYS = 10`,
`MIN_PROFIT_FACTOR = 1.30`.

- U.S.-listed common stocks and unlevered ETFs (no OTC, no leveraged/inverse).
- Liquidity: trailing-20-session average daily dollar volume ≥ `MIN_AVG_DOLLAR_VOLUME`.
- Excluded: price < `MIN_PRICE`, leveraged/inverse ETFs (separate test only),
  and — when a calendar is supplied — names within `EARNINGS_EXCLUSION_DAYS`
  trading days of earnings.
- **Document in every report**: exact OHLCV source, exact corporate-actions
  source (splits, cash/stock/special dividends, spin-offs, mergers, symbol
  changes), the single adjustment methodology used, the daily-close
  timestamp/timezone (default 16:00 America/New_York), and whether results are
  **price-return** or **total-return**. The same convention must be applied to
  all prices, indicators, stops, targets, and metrics so results are
  reproducible by an independent researcher.
- Adjusted OHLCV (splits/dividends). Survivorship-bias-free when the adapter
  supports delisted tickers (Polygon, or a CSV `delistings.csv`); otherwise
  survivorship bias is disclosed as a limitation.
- Daily bars for trend/regime context; 1h/15m for intraday entry families only
  where reliable intraday history exists.
- Holding period: intraday to 10 trading days.

## 3. Setup rules (objective, codeable)

For each family: hypothesis · regime filter · entry · stop · planned ≥3R target
· time stop · invalidation. Full parameter defaults live in each module under
`scanner/setups/`.

Default daily-swing research set (the five spec families). Each target is an
**objective ATR-based R multiple fitting the hypothesis — there is no forced
3R minimum.**

| Setup | Hypothesis | Entry (closed bar → next open) | Stop | Target rule | Time stop |
|-------|-----------|-------------------------------|------|-------------|-----------|
| `trend_pullback` | Pullbacks to the EMA20 inside an ADX trend are continuations | Trend (close vs 50/200SMA, ADX≥20) + low within 0.5·ATR of EMA20 + RSI cooled, close reclaims EMA20 | entry ∓ 1.5·ATR | 2.0R | 10 bars |
| `vcp_breakout` | Low-bandwidth coil + volume break precedes expansion | BB bandwidth in bottom quintile, close beyond prior-20 extreme, volume ≥1.5× | other side of coil / 1.2·ATR | 2.5R | 10 bars |
| `relative_strength_breakout` | New RS highs vs SPY + price breakout capture cross-sectional momentum | RS line new 60-bar high **and** price > prior-20 high | entry − 1.5·ATR | 2.5R | 10 bars |
| `ma_pullback` | Touch-and-hold of the 10/20-day MA in a strong trend is continuation | Trend (close vs 50/200SMA, ADX≥20) + bar low ≤ MA ≤ close | entry ∓ 1.5·ATR | 2.0R | 10 bars |
| `sector_leader_continuation` | Leaders of leading sectors continue | RS-vs-sector ETF new 40-bar high + sector ETF > its 200SMA + price > prior-10 high + close > 50SMA | entry − 1.5·ATR | 2.5R | 10 bars |

Also available (not default): `volume_breakout`, `mean_reversion` (1.5R),
`opening_range_breakout` (intraday).

The **planned target R is not the average winner.** Time stops, gap exits, and
the conservative same-bar rule mean realized winners are frequently below the
planned target; metrics report planned-target-R, average winner R, average
loser R, profit factor, and net expectancy separately so the two are never
conflated.

## 4. Execution & cost model

- Commissions ($0.005/share, $1 min) + regulatory fees on sells.
- Half-spread (2 bps) + slippage (3 bps) applied to **both** sides; longs pay
  up / sell down, shorts the reverse.
- **Delayed fill**: signal on bar *t* → fill at bar *t+1* open.
- **Gap-through-stop**: if a bar opens beyond the stop, exit at the open and
  record the **actual** loss (which can exceed −1R). We never assume −1R.
- **Gap-through-target**: symmetric (a favorable gap can exceed 3R).
- **Same-bar stop+target**: resolved conservatively (assume stop first) unless
  finer-resolution data is supplied.
- **Missed fills**: signals with no available fill bar, or blocked by portfolio
  risk limits, are dropped (not silently filled).
- **Three slippage scenarios**, applied per side to entries and exits:
  low 0.05%, normal 0.10%, stressed 0.25%. The full backtest is run under each;
  acceptance is judged on the **stressed** scenario — an edge that does not
  survive it (positive expectancy **and** PF ≥ `MIN_PROFIT_FACTOR`) is rejected.
- Reported: planned loss vs actual simulated loss, and the frequency/severity
  of losses worse than −1R (`gap_tail_rate`, `worst_loss_r`).

## 5. Validation protocol

1. ≥ ~10 years of data where available.
2. Time-ordered split: **development 50% / out-of-sample 30% / untouched
   holdout 20%** (never random over time).
3. Rules are locked before the holdout is read; the holdout is touched once.
4. Walk-forward: rolling test windows concatenated into an OOS stream.
5. Parameter-sensitivity: each numeric parameter perturbed ±10/20%; expectancy
   dispersion and sign tracked.
6. Monte Carlo trade-order reshuffle (drawdown distribution).
7. **Block (stationary) bootstrap** for expectancy CI (regime-preserving),
   plus iid bootstrap CIs for win rate / expectancy / profit factor.
8. Breakdowns by ticker, sector, year, regime, direction, exit reason.
9. **Concentration tests**: drop top 1/5/10% winners; drop best ticker / sector
   / year; expectancy must stay positive under every stress.
10. **Placebo tests**: matched random-date control trades with identical
    direction mix and stop/target geometry; empirical p-value =
    P(placebo expectancy ≥ real). p ≥ 0.10 ⇒ the special condition adds no
    demonstrable edge ⇒ reject.
11. **Multiple-testing / overfitting**: total trials counted; deflated Sharpe
    ratio (Bailey–López de Prado) with a probability the true Sharpe > 0; and
    Probability of Backtest Overfitting (CSCV).

## 6. Acceptance / rejection rules

A setup reaches **ROBUST — ELIGIBLE FOR FORWARD OBSERVATION ONLY** only when
*all* gates hold — **note there is no minimum-R requirement**: OOS expectancy>0;
PF ≥ `MIN_PROFIT_FACTOR`; profitable under the stressed cost scenario;
win>50% or payoff distribution justifies positive expectancy; ≥100 OOS trades;
CI-low>0; passes concentration and placebo tests; holdout not negative;
parameter-stable; PBO not high. Soft failures →
**TENTATIVE — FOR PAPER OBSERVATION ONLY**. CI-low≤0 or thin sample →
**STATISTICALLY INCONCLUSIVE**. Hard failures → **REJECTED**.

Setup Quality Score (0–100) is computed only from defined components and only
when required inputs exist:

| Points | Component |
|-------:|-----------|
| 25 | OOS expectancy strength, gated by CI lower bound |
| 20 | Profit factor after costs/stress |
| 15 | Regime robustness (fraction of regimes with + expectancy) |
| 15 | Parameter stability (1 − normalized expectancy dispersion) |
| 10 | Concentration-test resilience |
| 10 | Placebo-test advantage (1 − p-value) |
| 5 | Liquidity & execution practicality |

## 7. Standing results

**On the synthetic demo adapter (random-walk data with no real edge), all five
daily families are REJECTED** — typically for failing the placebo and
concentration tests and/or sub-1.30 profit factor after costs. This is the
correct, intended outcome: the system does not manufacture an edge where none
exists, and the live table prints `NO QUALIFYING SETUPS TODAY`.

To populate this section with real evidence, run:

```bash
python -m scanner.cli research --source polygon   # or --source csv
```

and record, per setup: development vs OOS vs holdout metrics, walk-forward
folds, bootstrap CIs, Monte Carlo drawdown, placebo p-value, concentration
survival, parameter sensitivity, deflated Sharpe and PBO, and the final label.

## 8. Assumptions & limitations

- Costs are conservative estimates for liquid names; real costs vary by broker,
  venue, order type, size, and conditions.
- Same-bar ambiguity is resolved conservatively on daily bars; intraday data
  would resolve some sequences more precisely.
- Earnings exclusion requires a supplied calendar; otherwise disclosed.
- The default candidate watchlist is small — production use needs a full,
  point-in-time, survivorship-free symbol universe.
- Synthetic results are for plumbing only and prove nothing about markets.

## 9. Conclusion (evidence status)

On the only data shipped with the repo (synthetic), the evidence is
**INSUFFICIENT / REJECTED by design** — no setup qualifies. Any claim of a
robust edge requires re-running against real adjusted, survivorship-free data
and confirming every acceptance gate, followed by a documented paper-trading
period before any discussion of live readiness.
