"""
One-time Schwab OAuth setup.
Run this BEFORE backtest.py or signals.py.
No web driver needed — just copy/paste a URL.
"""
import os, json, time, base64, urllib.request, urllib.parse
from dotenv import load_dotenv

load_dotenv()

KEY      = os.getenv("SCHWAB_APP_KEY", "")
SECRET   = os.getenv("SCHWAB_APP_SECRET", "")
CALLBACK = os.getenv("SCHWAB_CALLBACK_URL", "https://127.0.0.1")
TOKEN    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")

AUTH_URL  = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

if not KEY or not SECRET:
    raise SystemExit("\n  Missing keys in .env — fill in SCHWAB_APP_KEY and SCHWAB_APP_SECRET\n")

params   = urllib.parse.urlencode({"response_type": "code", "client_id": KEY, "redirect_uri": CALLBACK})
auth_url = f"{AUTH_URL}?{params}"

print()
print("=" * 65)
print("  SCHWAB ONE-TIME LOGIN")
print("=" * 65)
print()
print("  1. Copy the URL below and open it in Safari or Chrome:")
print()
print(f"  {auth_url}")
print()
print("  2. Log in to Schwab with your brokerage account")
print("     username and password, then click Allow.")
print()
print("  3. The browser will show 'This site can't be reached'")
print("     That is NORMAL. Do not close the browser.")
print()
print("  4. Copy the FULL URL from the browser address bar.")
print("     It starts with:  https://127.0.0.1?code=...")
print()
redirect = input("  Paste that URL here and press Enter: ").strip()

parsed = urllib.parse.urlparse(redirect)
code   = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
if not code:
    raise SystemExit("\n  No code found in URL — please try again from step 1.\n")

print("\n  Exchanging code for token...")
creds = base64.b64encode(f"{KEY}:{SECRET}".encode()).decode()
body  = urllib.parse.urlencode({
    "grant_type":   "authorization_code",
    "code":         code,
    "redirect_uri": CALLBACK,
}).encode()

req = urllib.request.Request(
    TOKEN_URL, data=body,
    headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"}
)
try:
    with urllib.request.urlopen(req) as r:
        token = json.loads(r.read())
except urllib.error.HTTPError as e:
    raise SystemExit(f"\n  Token exchange failed (HTTP {e.code}). Check your Client ID and Secret.\n")

token["expires_at"] = time.time() + token.get("expires_in", 1800)
with open(TOKEN, "w") as f:
    json.dump(token, f, indent=2)

print(f"\n  Token saved to token.json")
print("  You can now run:  python3 backtest.py")
print()
