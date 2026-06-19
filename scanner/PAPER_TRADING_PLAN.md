# 200-Day Trend Overlay — Paper-Tracking Plan

**Status: HYPOTHETICAL. PAPER ONLY. 0% real money.**
This is a forward-observation plan, not advice and not a proven system. Back-
tested results are hypothetical and do not reflect actual trading; past
performance does not predict future results (SEC). Frequent trading adds costs,
taxes, time, and risk, especially on margin (FINRA). Track it on paper for
several months before any real capital is ever considered.

---

## The goal (be honest about it)
Beat SPY buy-and-hold **on smoothness/drawdown**, not on total return. On 12
years of your real Schwab data this rule delivered **~1/3 smaller drawdowns in
both halves** (−11/−12% vs −24/−34%) with **better Calmar** — but **lower total
return** (it made roughly half the money over a strong bull market). You accept
lower growth in exchange for a smoother ride. If you want maximum growth, plain
buy-and-hold won and is a legitimate choice.

## The rule (objective, no judgment)
- **Instrument:** SPLG (S&P 500, ~$70/share — small-account friendly). SGOV =
  the "cash" leg (~5% T-bill yield).
- **Signal:** once a month, is SPLG's last close **above** its 200-day average?
  - **ABOVE → hold SPLG.**
  - **BELOW → hold SGOV (cash).**
- **Frequency:** check once a month. Act **only when the signal flips** (~2
  trades/year). No daily watching. No options. No leverage.

## Monthly routine (5 minutes, last trading day of the month)
```bash
cd ~/Downloads/web-app-feeling-good-*/scanner && source .venv/bin/activate
python beat_spy.py --source schwab --signal --equity SPLG
```
It prints **"hold SPLG"** or **"go to cash."** If it's the same as last month, do
nothing. If it flipped, update your paper log below.

## Paper log (copy this table; fill one row per month)
| Month | Signal (IN/OUT) | Action (hold/switch) | SPLG close | 200-day avg | Paper position | Note |
|-------|-----------------|----------------------|-----------|-------------|----------------|------|
| 2026-06 | | | | | | started paper-tracking |
| ... | | | | | | |

Also track, side by side, **"just held SPLG the whole time"** so you can compare
the overlay vs buy-and-hold honestly at the end.

## What success / failure looks like
- **Working:** over the paper period the overlay shows **smaller dips** than just
  holding SPLG, with return not far behind. (Expect it to **lag in a steady
  rally** — that is normal, not failure.)
- **Not working / stop:** it both **lags on return AND fails to cut drawdowns**
  (choppy, sideways markets can whipsaw it into repeated small losses).
- **Minimum observation:** several months, ideally through at least one real
  pullback, before judging anything.

## Risk discipline (staged — do not skip stages)
- **Now (paper):** 0% real money.
- **First tiny live test (only after a clean paper period):** 0.25% of equity.
- **After 100+ logged forward decisions with good behavior:** up to 0.5%.
- **Only after strong, consistent forward evidence:** consider 1.0%.

## Data / method limitations (disclosed)
- Schwab daily data is split-adjusted, **price-return** (dividends not exact),
  and **not survivorship-bias-free** — less of an issue for an index ETF like
  SPLG/SPY, which is why this overlay is more trustworthy than a single-stock
  backtest.
- The backtest assumed monthly rebalance, 1-day execution lag, ~5bps/switch
  costs, a 4% cash yield, and dividends added back equally to both sides. Real
  results will differ.

## The other half of the project
The 3R setup scanner is your **fake-edge filter**. When it says
`NO QUALIFYING SETUPS`, that is it protecting you — not failing. Do not optimize
it for weeks chasing a trade; "no" is a valid, useful answer.
