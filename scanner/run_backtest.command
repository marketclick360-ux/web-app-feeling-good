#!/bin/bash
# Double-click this file in Finder to run a backtest and see the result.
# It uses free stooq data (no key) on ONE ETF, so it always works.
cd "$(dirname "$0")" || exit 1

echo "=============================================="
echo "  Running your backtest... (takes ~20 seconds)"
echo "=============================================="

# turn on the sandbox if it exists
[ -f .venv/bin/activate ] && source .venv/bin/activate

# grab the latest version quietly (ignore errors if offline)
git pull --quiet 2>/dev/null

# the actual backtest: does a simple low-risk rule beat just holding the market?
python3 beat_spy.py --source stooq --equity SPLG --years 12

echo ""
echo "=============================================="
echo "  Done. Read the BOTTOM LINE above."
echo "  Press Enter to close this window."
echo "=============================================="
read -r _
