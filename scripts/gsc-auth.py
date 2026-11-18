#!/usr/bin/env python3
"""One-time OAuth consent for the Search Console API (desktop client, loopback redirect + PKCE).

Usage:
  python scripts/gsc-auth.py

Reads GSC_CLIENT_ID and GSC_CLIENT_SECRET from the Windows user environment, opens the Google consent page in
the browser and stores the refresh token in the user env var GSC_REFRESH_TOKEN. Never prints secrets. Run it
again only if the token stops working (revoked, or unused for 6 months). Setup details in CLAUDE.md.
"""
import base64, hashlib, http.server, secrets, socket, sys, urllib.parse, webbrowser, winreg
import requests

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

def user_env(name):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        return winreg.QueryValueEx(k, name)[0]

client_id, client_secret = user_env("GSC_CLIENT_ID"), user_env("GSC_CLIENT_SECRET")
verifier = secrets.token_urlsafe(64)
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
state = secrets.token_urlsafe(16)

sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
redirect = f"http://127.0.0.1:{port}"
result = {}

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in q or "error" in q:
            result.update({k: v[0] for k, v in q.items()})
        self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers()
        self.wfile.write(b"Done. You can close this tab and return to Claude Code.")
    def log_message(self, *a): pass

auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
    "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
    "access_type": "offline", "prompt": "consent"})
server = http.server.HTTPServer(("127.0.0.1", port), Handler)
server.timeout = 300
webbrowser.open(auth_url)
print("Browser opened; waiting up to 5 minutes for approval...", flush=True)
for _ in range(5):  # tolerate a few stray requests (e.g. favicon) before the redirect
    server.handle_request()
    if result:
        break
if not result:
    sys.exit("No answer from the browser (timeout).")

if result.get("state") != state: sys.exit("State mismatch; aborted.")
if "error" in result: sys.exit("Google returned error: " + result["error"])

r = requests.post("https://oauth2.googleapis.com/token", data={
    "code": result["code"], "client_id": client_id, "client_secret": client_secret,
    "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier}, timeout=30)
tok = r.json()
if "refresh_token" not in tok:
    sys.exit(f"Token exchange failed: HTTP {r.status_code} {tok.get('error')} {tok.get('error_description')}")
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
    winreg.SetValueEx(k, "GSC_REFRESH_TOKEN", 0, winreg.REG_SZ, tok["refresh_token"])
print("Refresh token stored in GSC_REFRESH_TOKEN. Granted scope:", tok.get("scope"))
