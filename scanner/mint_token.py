"""
Mint a Schwab OAuth token.json — standard-library only, no pip installs.

Usage:
    export SCHWAB_APP_KEY=...   SCHWAB_APP_SECRET=...   # optional; will prompt if unset
    python3 mint_token.py

It prints the Schwab login URL, waits while you log in and click Allow, then
exchanges the redirect URL for a token and writes token.json next to this file.
The input() prompt waits indefinitely, so there's no rush until you click Allow
(Schwab's code expires ~30s after that — paste the redirect URL promptly).
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

key = os.environ.get("SCHWAB_APP_KEY") or input("Schwab App Key: ").strip()
secret = os.environ.get("SCHWAB_APP_SECRET") or input("Schwab App Secret: ").strip()
callback = os.environ.get("CALLBACK", "https://127.0.0.1")

auth_url = ("https://api.schwabapi.com/v1/oauth/authorize"
            f"?response_type=code&client_id={key}&redirect_uri={callback}")
print("\n1) Open this URL in your browser, log in, and click Allow:\n")
print("   " + auth_url + "\n")
print("2) You'll land on a 'can't be reached' page — that's expected.")
print("   Copy the FULL address-bar URL (starts with " + callback + "/?code=...)\n")
redirect = input("3) Paste that URL here and press Enter:\n   ").strip()

query = urllib.parse.urlparse(redirect).query
code = urllib.parse.parse_qs(query).get("code", [None])[0]
if not code:
    print("\n❌ No 'code' found in that URL. Copy the WHOLE address-bar URL and retry.")
    sys.exit(1)

basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
body = urllib.parse.urlencode({
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": callback,
}).encode()
req = urllib.request.Request(
    "https://api.schwabapi.com/v1/oauth/token", data=body,
    headers={"Authorization": f"Basic {basic}",
             "Content-Type": "application/x-www-form-urlencoded"})

try:
    token = json.loads(urllib.request.urlopen(req).read())
except urllib.error.HTTPError as e:
    print("\n❌ Schwab rejected it:", e.read().decode()[:300])
    print("   (Usually means the code expired — just run this again and paste faster.)")
    sys.exit(1)

if "refresh_token" not in token:
    print("\n❌ No refresh_token returned:", token)
    sys.exit(1)

token["expires_at"] = time.time() + token.get("expires_in", 1800)
with open("token.json", "w") as fh:
    json.dump(token, fh, indent=2)
print("\n✅ TOKEN OK — saved token.json. You're ready to run the scanner.")
