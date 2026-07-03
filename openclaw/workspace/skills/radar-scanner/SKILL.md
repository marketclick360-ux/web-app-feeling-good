---
name: radar-scanner
description: Run the validated stock/ETF breakout scanner (backtests, nightly signals, key levels, ticker profiles) from ~/web-app-feeling-good and report results honestly.
---

# Radar scanner

All commands run from `~/web-app-feeling-good/scanner`. Python 3.11+, deps
installed via `pip install -r requirements.txt yfinance`.

## Commands

| Ask | Command | Notes |
|---|---|---|
| Fresh signals on the last close | `python -m scanner.cli radar --signal --source yahoo` | The main nightly check. Writes RADAR_SIGNALS.md. Rows carry TAKE/CAUTION/SKIP verdicts — relay them verbatim with the Why column. |
| Trigger prices + typical movement | `python -m scanner.cli radar --levels --source yahoo` | "How far is X from a breakout, what's its $/day" |
| Deep ticker personalities + 15y breakout report card | `python -m scanner.cli radar --profile --source yahoo` | Leaders, volatility mood, coils, drawdowns |
| Full 15-year backtest | `python -m scanner.cli radar --source yahoo --years 15` | Slow (minutes). Prefer quoting scanner/results/RADAR_BACKTEST.md unless asked to re-run. |

Reports are written to the working directory (or `--out-dir DIR`). The
15-year trade spreadsheets live in `scanner/results/*.csv`.

## Scheduled job

When asked to set up the nightly ping, schedule for **weekday evenings after
6:30pm Eastern** (after the US close settles): run the signal command, then send
the verdict table. If there are no rows, send "No fresh signals — normal;
breakouts are lumpy." Do not skip the message; silence is ambiguous.

## Reporting rules

- Lead with the verdict column. Never soften SKIP or upgrade CAUTION.
- Include the stop price and risk % with any signal you report.
- Always close signal reports with: "Paper-track only — not a live green light."
- Never place trades or touch brokerage accounts (see AGENTS.md — this is
  absolute).
- Keep `git pull` current before running, so the code matches the repo.
