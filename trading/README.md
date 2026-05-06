# Trading System — Quick Start

## Setup (do once)

```bash
cd trading
pip3 install schwab-py pandas python-dotenv
cp .env.example .env
```

Open `.env` and fill in your Schwab keys from developer.schwab.com:
```
SCHWAB_APP_KEY=paste_your_key_here
SCHWAB_APP_SECRET=paste_your_secret_here
SCHWAB_CALLBACK_URL=https://127.0.0.1
```

## Run the backtest (~10 min)

```bash
python3 backtest.py
```

First run opens a browser — log in to Schwab, click Allow, copy the URL from
the address bar and paste it into Terminal. Token saves automatically after that.

## Run daily signals (~30 sec)

```bash
python3 signals.py
```

## Output files

| File | Contents |
|------|----------|
| `backtest_results.csv` | Every stock trade |
| `options_results.csv` | Every options trade |
| `equity_curve.csv` | Day-by-day equity |
| `backtest_summary.txt` | Sharpe, drawdown, verdict |
| `signals_today.csv` | Today's signals |

## Strategy

Combines 5 legendary frameworks:
- **Anna Couling** — Full VPA (Upthrust, Test of Supply, Stopping Volume, Effort vs Result)
- **W.D. Gann** — 1x1 angle, Square of 9 targets, time cycles
- **Ray Dalio** — Risk-parity sizing, 4-quadrant growth/inflation regime
- **Stan Weinstein** — Stage 2 filter (30-week SMA rising)
- **Jesse Livermore** — Pivotal point breakout confirmation
