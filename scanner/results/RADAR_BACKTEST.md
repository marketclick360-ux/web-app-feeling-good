# Tactical Signal Radar — honest backtest

- **Source:** yahoo · **Universe:** 26 stocks + ETFs · **Years:** 15 · **SPY momentum filter:** ON
- Canonical exits (strength / SMA50-break / Donchian channel), 2×ATR hard stop, next-open fills, 0.10%/side costs. OOS = most recent 40% of trades. **Not a live-trading green light.**

| Strategy | Trades | /week | Win% | Exp/trade | PF | Hold(d) | OOS n | OOS exp | OOS PF | Top ticker | Label |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|---|
| pullback_rsi2_200d | 2572 | 3.3 | 64% | +0.10% | 1.11 | 2 | 1029 | +0.22% | 1.23 | TSLA 12% | TENTATIVE |
| sma50_bullish_bounce | 2728 | 3.5 | 29% | +0.01% | 1.01 | 4 | 1092 | -0.01% | 0.99 | CAT 8% | REJECTED |
| breakout_20d | 1666 | 2.1 | 41% | +1.47% | 1.78 | 17 | 667 | +1.85% | 1.84 | NVDA 11% | PAPER-TRACK ONLY |
| breakout_55d | 1033 | 1.3 | 39% | +2.43% | 2.14 | 25 | 414 | +3.99% | 2.76 | TSLA 15% | PAPER-TRACK ONLY |
| oversold_reclaim_20d | 3543 | 4.5 | 50% | -0.20% | 0.72 | 0 | 1418 | -0.30% | 0.65 | NVDA 9% | REJECTED |

**Combined signal frequency: ~14.7 trades/week** across the universe (all five strategies).

## Verdicts

- **pullback_rsi2_200d** — TENTATIVE: positive but PF < 1.30 — fragile
- **sma50_bullish_bounce** — REJECTED: OOS expectancy -0.01%/trade not positive
- **breakout_20d** — PAPER-TRACK ONLY: passes every gate at this sample
- **breakout_55d** — PAPER-TRACK ONLY: passes every gate at this sample
- **oversold_reclaim_20d** — REJECTED: OOS expectancy -0.30%/trade not positive

**Best OOS performer: breakout_55d** (+3.99%/trade OOS; top ticker TSLA 15% of profits, exp without it +3.28%).

## Honest notes
- A positive strategy here is *promising*, not proven — paper-trade it before a cent, and re-check concentration (one hot ticker can fake an edge).
- **Options:** cannot be honestly backtested without historical option chains (we don't have that data). Options multiply the underlying edge — including a negative one. Only consider defined-risk options (long calls / spreads) on a strategy that has already passed these gates, never before.

