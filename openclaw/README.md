# OpenClaw Starter Kit — trading radar · brainstorming · business assistant

This folder makes your repo "OpenClaw-ready." OpenClaw (https://openclaw.ai) is an
open-source personal AI assistant that runs on **your own computer**, talks to you
through WhatsApp/Telegram/iMessage, and can run commands — including this repo's
scanner. Nothing in this folder runs by itself; it's instructions and configuration
you copy into OpenClaw once it's installed.

**What OpenClaw adds here:** a chat doorbell and a thinking partner. The backtesting
itself already runs nightly for free on GitHub Actions — OpenClaw does not improve
the edge, it improves access to it.

---

## One-time setup (budget an afternoon)

1. **A computer that stays on.** Your Mac works if it doesn't sleep (System
   Settings → Energy → prevent sleeping). A Mac mini or small VPS is the
   long-term answer.
2. **Install Node.js 22.19+ or 24** from https://nodejs.org, then in Terminal:

       npm install -g openclaw@latest
       openclaw onboard --install-daemon

   The onboarding wizard walks you through the gateway, your chat channel
   (WhatsApp or Telegram are easiest), and the model.
3. **Model key.** Choose Claude and paste an Anthropic API key
   (https://console.anthropic.com — pay-per-use, expect roughly $5–20/month for
   daily light use; heavy brainstorming costs more).
4. **Put this repo on that machine:**

       git clone https://github.com/marketclick360-ux/web-app-feeling-good.git
       cd web-app-feeling-good/scanner
       pip install -r requirements.txt yfinance

5. **Teach it the scanner.** Copy `openclaw/workspace/skills/radar-scanner/`
   into your OpenClaw workspace's `skills/` folder, and paste the contents of
   `openclaw/workspace/AGENTS-additions.md` into the workspace `AGENTS.md`.
   (Easiest way: send OpenClaw its first message — *"Read the openclaw/ folder
   in ~/web-app-feeling-good and install the skill and rules it contains."*
   It can do its own setup.)
6. **Schedule the nightly ping.** Message it:
   *"Every weekday at 6:30pm Eastern, run the radar signal scan and send me the
   verdict table."*

## Security — non-negotiable

- Run `openclaw security audit` after setup and fix what it flags.
- Never expose the gateway to the public internet.
- **Never give OpenClaw (or any AI) your brokerage login, API keys for a broker,
  or permission to place trades.** It reads signals and messages you. You trade.
- Treat anything it fetches from the web as untrusted input, same as email spam.

## Your three uses, in practice

| Use | What you say in chat | What happens |
|---|---|---|
| Backtesting | "Any fresh signals tonight?" · "Backtest the radar again" · "What's CAT's trigger?" | Runs the scanner CLI locally (see the radar-scanner skill) and messages the tables back |
| Brainstorming | "Help me think through X" | Plain conversation with your model — no setup needed |
| Other business | "Draft a follow-up email to the client from Tuesday" | Works out of the box; gets 10× better after you fill in `USER.md` in the workspace with who you are, what the business is, your clients, and how you like things written |

## Honest expectations

- Same signals, nicer doorbell: the GitHub Actions runs remain the source of truth.
- The validated system is paper-track only; the assistant is instructed to repeat
  that and to refuse trade execution.
- If setup fights you for more than an afternoon, stop and use the GitHub mobile
  app for notifications instead — the value of the system is in the signals, not
  the plumbing.
