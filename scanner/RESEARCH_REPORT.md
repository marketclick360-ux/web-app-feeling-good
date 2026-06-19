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

Default daily-swing research set — now **8 families**. Targets are objective
ATR-based R multiples, and the **hard rule is target ≥ 3R**: any family whose
planned target is below 3R is rejected before testing. The breakout/pullback
families are designed to 3R; `mean_reversion` (1.5R) is therefore auto-rejected
by the gate (kept only as a diagnostic). Edge mode additionally reports a
**2.0R / 2.5R / 3.0R target sweep** for transparency — but only the 3R variant
can be accepted.

| Setup | Hypothesis | Entry (closed bar → next open) | Stop | Target | Time stop |
|-------|-----------|-------------------------------|------|--------|-----------|
| `trend_pullback` | Pullbacks to the EMA20 inside an ADX trend are continuations | Trend + low within 0.5·ATR of EMA20 + RSI cooled, close reclaims EMA20 | entry ∓ 1.5·ATR | 3R | 10 bars |
| `ma_pullback` | Touch-and-hold of the 10/20-day MA in a strong trend | Trend (50/200SMA, ADX≥20) + bar low ≤ MA ≤ close | entry ∓ 1.5·ATR | 3R | 10 bars |
| `breakout_retest` | Volume break of a 40-bar high, then a held retest of the broken level | breakout in last 10 bars on volume + current bar retests & holds level | level − 0.3·ATR | 3R | 10 bars |
| `vcp_breakout` | Low-bandwidth coil + volume break precedes expansion | BB bandwidth bottom quintile, close beyond prior-20 extreme, volume ≥1.5× | other side of coil / 1.2·ATR | 3R | 10 bars |
| `relative_strength_breakout` | New RS highs vs SPY + price breakout | RS line new 60-bar high **and** price > prior-20 high | entry − 1.5·ATR | 3R | 10 bars |
| `failed_breakdown` | Quick reclaim of broken support traps shorts (bear trap) | low broke prior-40 support within 3 bars, close back above on volume | trap low − 0.25·ATR | 3R | 10 bars |
| `accumulation_breakout` | Breakout confirmed by objective accumulation (CMF>0, rising OBV, volume) | close > prior-20 high + CMF>0.05 + OBV rising + volume ≥1.3× | entry − 1.5·ATR | 3R | 10 bars |
| `sector_leader_continuation` | Leaders of leading sectors continue | RS-vs-sector ETF new 40-bar high + sector ETF > 200SMA + price > prior-10 high + close > 50SMA | entry − 1.5·ATR | 3R | 10 bars |

Also available (not default): `volume_breakout`, `mean_reversion` (1.5R → 3R-gate
rejected), `opening_range_breakout` (intraday).

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
*all* gates hold. **Hard pre-test gate: planned target ≥ 3R** (anything below 3R
is rejected before any performance test; see `validation.MIN_PLANNED_R`). Then:
OOS expectancy>0; PF ≥ `MIN_PROFIT_FACTOR`; profitable under the stressed cost
scenario; win>50% or payoff distribution justifies positive expectancy; ≥100 OOS
trades; CI-low>0; passes concentration and placebo tests; holdout not negative;
parameter-stable; PBO not high. Soft failures →
**TENTATIVE — FOR PAPER OBSERVATION ONLY**. CI-low≤0 or thin sample →
**STATISTICALLY INCONCLUSIVE**. Zero OOS trades → **NO OOS SAMPLE** (no stats
computed). Hard failures → **REJECTED**.

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
daily families are REJECTED** — the system does not manufacture an edge where
none exists, and the live table prints `NO QUALIFYING SETUPS TODAY`.

### 7a. First real-data run — Schwab (smoke test)

Source: **Schwab** (`Live data verified: YES`), split-adjusted, price-return,
not survivorship-bias-free. Config: 8 liquid symbols, 5 years, `--fast`. This is
a deliberately small smoke test, **not** a definitive study — samples are far
too thin to draw conclusions, which is itself why nothing qualified.

| Setup | OOS n | Win | Expectancy (R) | PF | Outcome / reason |
|-------|------:|----:|---------------:|---:|------------------|
| trend_pullback | 0 | — | — | — | REJECTED — no signals in this tiny universe |
| vcp_breakout | 3 | 66.7% | +0.427 | 28.9 | REJECTED — only 3 trades; **holdout −0.998R**, fails placebo |
| relative_strength_breakout | 49 | 30.6% | −0.519 | 0.22 | REJECTED — negative expectancy after costs |
| ma_pullback | 59 | 28.8% | −0.363 | 0.55 | REJECTED — negative expectancy after costs |
| sector_leader_continuation | — | — | — | — | REJECTED — not eligible |

**Result: NO QUALIFYING SETUPS TODAY (0 of 5 eligible).** The `vcp_breakout`
case is the key illustration of the design working: a tiny, attractive-looking
in-sample sample (PF 29) was correctly refused because it collapsed on the
untouched holdout and failed the placebo control. Expectancy stayed negative
under all three cost scenarios for the losing families.

Caveats: 8 symbols / 5 years / fast mode → thin samples (most families would be
`STATISTICALLY INCONCLUSIVE` on sample size alone). A meaningful test requires
the larger run (≥30 symbols, 10 years, full mode) across more tickers, years,
and regimes. Schwab data is price-return and not survivorship-bias-free — both
disclosed limitations.

### 7b. Reproducing / extending

To populate a fuller study, run against real data:

```bash
python -m scanner.cli research --source schwab --symbols 30 --years 10
python -m scanner.cli research --source polygon  # or csv
```

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

---

## 10. Cross-Review Conclusion and Current Research Status

Two independent AI reviews — **Codex** (working in the separate
`vpa-trading-strategy` repo) and **Claude** (this `scanner` package) — reviewed
the methodology and the real-data (Schwab) outputs and reached the same core
conclusions.

### 10.1 Where both reviews agree (safety conclusions)
- A **hard 3R gate** is correct: any setup whose planned target is below 3R is
  rejected *before* backtesting.
- **OOS n == 0** must be labeled **NO OOS SAMPLE** (no expectancy / profit
  factor / win rate / placebo / concentration / cost-stress claims computed).
- **OOS n < 100** must be labeled **STATISTICALLY INCONCLUSIVE**; 300+ preferred.
- **No 3R stock/ETF setup scanner qualifies yet** — there is no 100+ OOS-trade
  sample, and current setup exporters are not true backtests.
- **ETF timing/regime filters currently look stronger than the 3R setup scanner.**
- `sector_rotation` and `SPY_or_BONDS` **remain rejected**.
- `SPY_200d_timing` is a **defensive overlay, not a return engine**.

### 10.2 Important caveat on SPY_abs_momentum
- `SPY_abs_momentum` had the **strongest out-of-sample** result (OOS CAGR
  ~13.8%, MaxDD ~−18.8%, Sharpe ~0.79, Calmar ~0.73).
- **But it performed poorly in-sample** (IS CAGR ~5.6% vs SPY ~14.3%, with
  ~−34% drawdown — i.e. no protection in the first half).
- A strategy that only works in one half is **regime-dependent luck, not a
  robust edge**. It must **not** be crowned the best framework yet.
- Status: **observe-only** until it survives further forward testing across a
  full market cycle. The same caution applies to `dual_momentum`.

### 10.3 Revised ranking (current, hypothetical)
1. **Primary paper-track candidate:** `SPY_200d_timing` / 200-day defensive
   overlay (and its lower-whipsaw `SPY_200d_buffer` variant) — chosen because it
   showed **consistent drawdown reduction across both in-sample and
   out-of-sample halves**. It reduces risk; it does **not** beat SPY on total
   return.
2. **Observe-only candidates:** `SPY_abs_momentum`, `dual_momentum` — strong OOS
   but weak/ inconsistent IS; track forward before trusting.
3. **Rejected:** `sector_rotation`, `SPY_or_BONDS`.
4. **No qualifying 3R scanner setup exists yet** (insufficient OOS sample;
   exporters are not true backtests).

### 10.4 Warning — agreement is not proof
- Two AI reviews agreeing is **useful corroboration, not proof of
  profitability.**
- Both reviews are based on the **same historical outputs and assumptions**
  (same Schwab price-return data, same cost model) — so they share the same
  blind spots; agreement does not add independent evidence about the future.
- **Forward paper-tracking is still required** before any live-risk decision.
  Backtests are hypothetical and do not predict future results (SEC).

### 10.5 Repository source-of-truth
- **Canonical / maintained going forward:** this **`scanner/`** package in
  `web-app-feeling-good` — it is self-contained, has a passing test suite
  (no-look-ahead, cost, sizing, engine, metrics, pipeline) and CI, and
  implements the validation gates, edge mode, and the Beat-SPY overlay tooling.
- **Reference / archival:** the `vpa-trading-strategy` repo (Codex's changes)
  and the legacy `trading/` folder (Gann/VPA experiments). Useful for
  cross-checking conclusions, but **not** the primary codebase — to avoid two
  divergent implementations, new development should land in `scanner/`.
- If the two repos must coexist, keep `scanner/` authoritative for validation
  rules and engine logic; treat the other as research notes.
