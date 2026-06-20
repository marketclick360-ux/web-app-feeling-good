# Trading Scanner — Plain-English Guide

A one-page cheat sheet for the **ETF rule-based scanner**. Keep it; everything
you need is here.

> Honest reminder up front: this tool finds and tests trade ideas. It does **not**
> promise profit. Its best label is "worth paper-testing," never "guaranteed."
> Paper-trade first. Real money only after forward evidence.

---

## 0. Two different tools (don't mix them up)
- **ETF scanner** (this guide): `python -m scanner.cli ...` — simple ETF swing setups.
- **Options/wheel alert** (the long email with PFE/DKNG/KO, "WHEEL", "VPA"): a
  *separate, more advanced* tool. Not covered here.

---

## 1. The right order (never skip a step)
1. **Backtest** — does the idea work on years of history?  → `edge`
2. **Double-test** — does it still work on data it never saw + a 2nd data feed?  → `edge`, `compare`
3. **Forward-test** — log it on paper and watch it for weeks.  → `log`, `review`
4. **Only then** — consider real money, tiny size.

You were right: never forward-test something you haven't backtested first.

---

## 2. One-time setup (per Terminal window)
```
cd ~/market-scanner/scanner
source .venv/bin/activate
git pull
```
- Backtesting now uses **stooq** by default = **free, no keys, no signup**.
- **Schwab** (live signals) needs your keys set in the window. To avoid retyping:
  `echo 'export SCHWAB_APP_KEY=...' >> ~/.zshrc` (and the secret), then `source ~/.zshrc`.
- **Polygon** (optional 2nd opinion) needs a free key:
  `echo 'export POLYGON_API_KEY=...' >> ~/.zshrc`, then `source ~/.zshrc`.

---

## 3. The commands (what each does, plain English)

| Command | What it does |
|---|---|
| `edge` | **Backtest + double-test.** Grades every setup A–F and sorts into buckets. START HERE. |
| `compare` | Runs the backtest on **two data feeds** and flags what passes BOTH. |
| `log` | Writes today's candidate trades to a paper journal (`signal_log.csv`). |
| `review` | Scores how the logged paper trades actually played out. |
| `concentration` | Checks if a setup's edge is real or just **one ticker** (the SLV trap). |
| `plan` | Dates, time-to-next-signal, **money required**, and highlights. |

### The one-line everything (easiest)
```
python -m scanner.cli report --small-account --etf-only --fast
```
`report` = **Part 1** backtest + double-test (what's PROVEN, the buckets) **then
Part 2** today's actual candidate trades. Take only Part-2 trades whose setup is
in an **A/B** bucket from Part 1.

### Copy-paste commands
```
# 1) Backtest + double-test (free, no keys)
python -m scanner.cli edge --small-account --etf-only --fast

# 2) Two opinions — only trust what passes BOTH feeds (needs Polygon key)
python -m scanner.cli compare --sources stooq polygon --small-account --etf-only --fast

# 3) Log today's candidates (Schwab for live; or stooq to practice)
python -m scanner.cli log --source schwab --small-account --etf-only --backfill-days 7

# 4) See how logged trades played out (entry/exit/duration with --trades)
python -m scanner.cli review --trades

# 5) Is the edge broad or one ticker?
python -m scanner.cli concentration --setup relative_strength_breakout

# 6) Money + timing plan for your account size
python -m scanner.cli plan --account 2000
```

---

## 4. How to read the results

### `edge` — the buckets (look at the bottom)
- **A. VALIDATED** — passed everything. Strongest.
- **B. PAPER-ONLY** — promising. **Forward-test these.**
- **C. WATCHLIST** — interesting, not proven. Wait.
- **D. REJECTED** — failed. Ignore.
- Per setup, two key numbers: **IS trades** (backtest) and **OOS trades** (the blind
  double-test). If OOS < ~100 → **"INCONCLUSIVE"** = not enough proof yet.
- **"NO QUALIFYING SETUPS"** = honest, not broken. Nothing was good enough.

### `compare` — the verdict column
- **✅ BOTH — candidate** → passed on both feeds. Real.
- **⚠ only stooq / only polygon** → red flag, likely a data quirk. Don't trust.
- **— rejected by both** → ignore.

### `log` — the FRESH candidates table
```
tkr  dir   setup           price  support  resist  →sup%  entry  stop   3R     trad
GLD  long  volume_breakout 161.08 158.91          1.3%   161.08 157.99 170.35  88/A
```
- **dir**: long = buy (bet up); short = bet down.
- **price**: current price.  **support**: floor it bounces off.  **resist**: ceiling.
- **→sup%**: how far price is ABOVE support. **Smaller = closer to support = safer long.**
- **entry**: buy price.  **stop**: safety exit (sell if it drops here).  **3R**: profit target.
- **trad**: quality grade. Stick to **A and B**.
- Levels are **mechanical** (moving averages + recent swing highs/lows), a quick
  gut-check — not a substitute for reading the chart.

### `plan` — money & timing
- **CADENCE**: how often signals come, average days until the next one.
- **MONEY**: dollars each trade needs (never more cash than you have); flags trades
  too pricey for the account.
- **PEAK CAPITAL**: most trades open at once; you need ~one account's worth, not margin.
- **HIGHLIGHTS**: win rate, expectancy in $, best/worst trade, hold time, exit mix.

---

## 5. Data feeds
| Feed | Cost | Key? | Setup | Best for |
|---|---|---|---|---|
| **stooq** | Free | No | 0 min (default) | Backtesting |
| **schwab** | Free | Yes | keys + token.json | Live signals |
| **massive** | Free tier | Yes (1 key) | ~5 min | 2nd opinion (Polygon's new name) |
| **polygon** | Free tier | Yes (1 key) | ~5 min | same as massive, old address |

**Massive = Polygon.** Polygon.io rebranded to **Massive** (massive.com). Same API,
same key. Use `--source massive` and set your key once:
`echo 'export MASSIVE_API_KEY=your_key' >> ~/.zshrc`, then `source ~/.zshrc`.
Two-feed cross-check: `compare --sources stooq massive`.

---

## 6. Cost / "tokens"
- The scanner runs **locally on your Mac**. It uses **no AI tokens** and costs **$0**.
- It only fetches **free** price data (stooq unlimited; Polygon free tier is just slower).
- Run it as much as you want for free.

---

## 6b. Beat buy-and-hold (the `beat_spy.py` tool)
This is the tool for your "beat buy-and-hold" goal. It compares simple low-risk
rules against just holding SPY, and shows **in-sample AND out-of-sample** so a
tweak that only works on old data is exposed.
```
python3 beat_spy.py --source massive --equity SPLG --years 12
```
**Tweak the knobs and re-run** (then look ONLY at the OUT-OF-SAMPLE block):
```
python3 beat_spy.py --source massive --years 12 --ma 150 --buffer 3 --mom 150
```
- `--ma` = moving-average length (200 default; try 150 / 250)
- `--buffer` = % cushion before switching (cuts whipsaws)
- `--mom` = momentum lookback in days

**How to read it — the honest definition of "beat":**
- **MaxDD** (max drawdown) = the worst crash. **Smaller = better.**
- **Calmar** = return per unit of crash. **Higher = better.**
- Beating SPY on **raw return** is rare and usually luck. Beating it on
  **drawdown / Calmar** (a smoother ride) is the achievable, real win — exactly
  the "low-risk, small-account" goal.
- **Trust only what still looks good in the OUT-OF-SAMPLE block.** If a setting
  wins in-sample but loses out-of-sample, you curve-fit it — throw it out.

Today's in-or-out signal (check monthly, act only when it flips):
```
python3 beat_spy.py --source massive --equity SPLG --signal
```

## 7. Golden rules
1. Backtest first. Always.
2. Trust only what passes **two feeds** (`compare`).
3. Only forward-test **A/B** bucket setups.
4. Watch for the **one-ticker trap** (`concentration`).
5. Set your **stop** and **target** when you enter, then leave it alone.
6. Paper first. Real money last, and tiny.
7. "NO QUALIFYING SETUPS" is a feature — the tool refusing to lie to you.
