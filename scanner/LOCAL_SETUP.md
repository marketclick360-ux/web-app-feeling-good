# Local setup with `git` (one time) — then updates are one `git pull`

This replaces the download-a-ZIP-every-time workflow. The repo is public, so no
login is needed to clone or pull.

## One-time setup (paste ONE line at a time, press Enter after each)

```bash
git --version
```
(If macOS offers to install "command line developer tools", click Install and
wait, then continue.)

```bash
git clone https://github.com/marketclick360-ux/web-app-feeling-good.git ~/market-scanner
```
```bash
cd ~/market-scanner
```
```bash
git checkout claude/rule-based-stock-scanner-j25y36
```
```bash
cd scanner
```
Bring your existing token + paper journal over from the old Downloads copy:
```bash
cp ~/Downloads/web-app-feeling-good-*/scanner/token.json ./token.json
```
```bash
cp ~/Downloads/web-app-feeling-good-*/scanner/signal_log.csv ./signal_log.csv
```
Build the sandbox and install:
```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate
```
```bash
pip install -q -r requirements.txt
```

## Stop re-typing your keys every session (optional, convenient)
Add your Schwab keys to your shell profile once so every new Terminal has them
(replace with your real values; this stores them in a local dotfile):
```bash
echo 'export SCHWAB_APP_KEY=yourkey' >> ~/.zshrc
echo 'export SCHWAB_APP_SECRET=yoursecret' >> ~/.zshrc
```
Then open a new Terminal (or run `source ~/.zshrc`).

## From now on — daily/weekly routine (one line each)
```bash
cd ~/market-scanner/scanner
```
```bash
git pull
```
```bash
source .venv/bin/activate
```
Then any command, e.g.:
```bash
python -m scanner.cli log    --source schwab --small-account --etf-only --backfill-days 7
python -m scanner.cli review --source schwab --in signal_log.csv
python -m scanner.cli edge   --source schwab --small-account --etf-only --fast
python beat_spy.py           --source schwab --signal --equity SPLG
```

`git pull` always gets my latest changes — no more ZIP downloads, and your
`token.json` / `signal_log.csv` stay in place (they're gitignored).
