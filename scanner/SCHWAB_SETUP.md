# Running the scanner against real Schwab data (in a Claude Code web container)

Schwab can't complete its browser OAuth inside a headless container, and this
environment's network egress is allowlisted. So enabling Schwab takes three
one-time setup steps **outside** the container, then a fresh session.

## Step 1 — Mint a token.json on your own machine (has a browser)

You already have a no-web-driver helper in `trading/`:

```bash
cd trading
pip install python-dotenv
cp .env.example .env          # fill in SCHWAB_APP_KEY, SCHWAB_APP_SECRET,
                              # SCHWAB_CALLBACK_URL (must match your Schwab app)
python3 setup_auth.py         # prints a URL -> log in -> Allow -> paste the
                              # redirect URL back. Writes trading/token.json
```

`token.json` contains `access_token` + `refresh_token` + `expires_at`. The
**refresh token is valid ~7 days**, so do this shortly before the run. The
scanner auto-refreshes the short-lived access token using it.

## Step 2 — Configure the Claude Code environment (web UI)

In this repo's environment settings:

1. **Network egress allowlist** → add host: `api.schwabapi.com`
2. **Environment variables / secrets** → set:
   - `SCHWAB_APP_KEY` = your app key
   - `SCHWAB_APP_SECRET` = your app secret
   - `SCHWAB_TOKEN_JSON` = paste the **entire contents** of `trading/token.json`
   - (optional) `SCHWAB_CALLBACK_URL` = your registered callback

The adapter reads `SCHWAB_TOKEN_JSON` and materializes `token.json` in the
container at startup — so you never have to commit the sensitive token file
(`token.json` and `.env` are gitignored).

## Step 3 — Start a NEW web session

The egress allowlist and secrets apply at container start, so the *current*
session won't pick them up. Start a fresh Claude Code web session on this
environment.

## Step 4 — Run

```bash
cd scanner
pip install -r requirements.txt
# quick first pass:
python -m scanner.cli research --source schwab --symbols 12 --years 5 --fast
# fuller run:
python -m scanner.cli research --source schwab --symbols 30 --years 10
python -m scanner.cli scan     --source schwab --symbols 30
```

Or just tell me "run it" in the new session and I'll execute and populate
`RESEARCH_REPORT.md` with the real results.

## What to expect / caveats

- **Adjustment**: Schwab daily history is split-adjusted, **price-return**
  (dividends not reinvested). Documented in the report header.
- **Survivorship bias**: Schwab has no point-in-time delisted-ticker feed, so
  the universe is built from currently-listed names — disclosed as a limitation.
- **Rate limits**: ~120 req/min; 30 symbols of daily history is comfortable.
  Responses are cached on disk (`.schwab_cache/`, gitignored).
- **Token lifetime**: if the container is reclaimed and you start again after
  the 7-day refresh window, re-mint `token.json` (Step 1) and update
  `SCHWAB_TOKEN_JSON`.
- The scanner will honestly return `NO QUALIFYING SETUPS TODAY` and may REJECT
  every family — that is a valid, expected outcome, not a failure.
