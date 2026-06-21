# Multi-Timeframe Trend Model — Paper-Trading Plan

**Status: HYPOTHETICAL — PAPER ONLY. 0% real money.**
This is a forward-observation plan, not advice and not a proven system.
Backtested results are hypothetical, do not reflect actual trading, and do not
predict the future. The honest goal of this model is a **smoother ride** (lower
drawdown), **not** beating buy-and-hold on return.

---

## What this model is

One instrument at a time, **long or in cash** — never short, never leveraged,
never an overnight bet that can gap to zero. You are in the market only when a
ticker's short, medium and long-term trend all agree, and you step aside the
moment the long-term trend breaks.

**What the 15-year backtest actually showed (real data, 13 tickers):**
- It **cut the max drawdown on every ticker** (e.g. SPY 34% → 20%, GLD 46% → 30%).
- It **gave up some return** vs buy-and-hold on every ticker.
- Risk-adjusted return (Sharpe) only **tied or beat** buy-and-hold on the
  strongest trends — **QQQ and XLK**.
- **Conclusion:** a capital-preservation / smoother-ride overlay — *promising,
  not proven* (small trade count). Paper-track before any real money.

---

## The rules (exactly)

**Universe:** the weekly watchlist (`WEEKLY_SIGNALS.md`, refreshed every Saturday
by the `weekly-signals` GitHub Action).

**Entry**
1. Each **Saturday**, open the latest `weekly-signals` run and list the **BUY** rows.
2. Prefer the cleanest BUYs — broad index / strong-trend names (SPY, VTI, QQQ,
   XLK and similar). Skip thin-cushion BUYs (< ~2% above the exit line).
3. Paper-buy at **Monday's open**. Record the fill price.

**Exit**
4. **Sell when the daily close drops below the "Exit if <" (200-day) level** for
   that ticker. No other exit — you ride normal pullbacks.

**Position sizing (paper)**
5. Treat the account as **5 equal slots** (each new position = 1/5 of the
   account). Never more than 5 open at once. Never average down.
6. One ticker per slot. If you're already holding a name, its later signals
   don't add size.

**Discipline**
7. Signals are **lumpy** — some weeks 3 BUYs, many weeks zero. "Nothing this
   week" is a valid, correct outcome. Do **not** force trades.
8. Log **every** paper trade below for at least **one month** before any real money.

---

## Going live (only after the paper month)

- One month ≈ 4–8 trades — enough to learn the **mechanics and discipline**,
  **not** enough to *prove* the edge. Don't let one good/bad month decide it.
- When you go live, **start at 1/4** of your intended size and scale up slowly
  only if it behaves.
- Trade only the **cleanest names** (broad index / strong trend). The model's
  real value is *not blowing up* — protect that above all.

---

## Paper trade log

| # | Signal date | Ticker | Entry date | Entry $ | Exit date | Exit $ | Result % | Exit reason | Notes |
|--:|---|---|---|--:|---|--:|--:|---|---|
| 1 |  |  |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |  |  |
| 6 |  |  |  |  |  |  |  |  |  |
| 7 |  |  |  |  |  |  |  |  |  |
| 8 |  |  |  |  |  |  |  |  |  |

**Running tally:** trades ___ · winners ___ · losers ___ · biggest win ___% ·
biggest loss ___% · still open ___

_Exit reason is almost always "200-day break." If you ever exit for any other
reason, write why — that's a discipline leak to watch._
