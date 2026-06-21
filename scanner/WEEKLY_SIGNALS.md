# Weekly Signals — Multi-Timeframe Trend Watchlist

**Status: HYPOTHETICAL — PAPER ONLY. 0% real money yet.**
Backtest/forward-observation only. Not advice, not a proven system. Past and
hypothetical results do not reflect actual trading and do not predict the future.

- **As of:** 2026-06-19 · **Source:** yahoo (yfinance) · **Universe:** 61 liquid tickers
- **Rule:** long/flat on ONE ticker; **BUY** when the 20-EMA, 50-SMA and
  200-SMA trends all agree (enter next open). **Exit** when the daily close
  drops below the 200-day line. Never short, never leveraged.
- This file is a snapshot. The live list refreshes every **Saturday** via the
  `weekly-signals` GitHub Action — open the latest run (or download the
  `weekly-signals` artifact) for the current week.

## 🟢 This week's BUYs (trend just turned up)

| Ticker | Enter ~ | Exit if closes below (200-day) | Cushion |
|---|--:|--:|--:|
| **SPY** (S&P 500) | 746.74 | 684.49 | 8.3% |
| **VTI** (total market) | 369.99 | 338.12 | 8.6% |
| TLT (bonds) — *marginal, thin cushion* | 86.75 | 86.40 | 0.4% |

**Cleanest buys: SPY and VTI** (broad index, ~8% cushion). TLT just barely
crossed (0.4% cushion) and bonds were weak in the backtest — skip or watch.

## Status of the full board

**IN_UPTREND (already trending — hold, not a fresh buy):**
AMD, SOXX, SMH, TXN, CAT, XLK, EEM, UNH, QQQ, XBI, IWM, LLY, IWD, XLI, MDY,
KRE, BAC, XLB, EFA, DIA, JPM, XLF, HYG, LQD

**HOLD_200 (above the 200-day but pulling back — not a buy):**
GOOGL, AVGO, AAPL, KO, XOP, XLE, XLRE, AMZN, IWF, XLP, XLU, WMT, XLV

**FLAT (below the 200-day — stay out):**
V, COST, ITB, XLY, DIS, **SLV**, PEP, TSLA, XLC, **GLD**, HD, MA, MCD, ORCL,
META, MSFT, NFLX, CRM, ADBE

> Note: **GLD (gold) and SLV (silver) are FLAT** — the rule keeps you OUT of the
> exact kind of asset that caused the blow-up. Several broken-down megacaps
> (MSFT, META, NFLX, CRM, ADBE) are also FLAT — you stay out of weakness and
> hold strength automatically.

## How to read the labels
- **BUY** — trend just turned up; paper-enter at the next session's open.
- **IN_UPTREND** — all three timeframes aligned; you'd already be holding.
- **HOLD_200** — above the 200-day but not fully aligned (a pullback); hold if in, don't add.
- **FLAT** — below the 200-day; stand aside.
- **Cushion** — how far price sits above the 200-day exit line (your room before the rule takes you out).
