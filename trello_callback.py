import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer

class TrelloCallbackServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address):
        self.token = None
        self.error = None
        self.state = secrets.token_urlsafe(32)
        super().__init__(server_address, TrelloCallbackHandler)

class TrelloCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        # Do not log authorization callback traffic or token-related data.
        return

    def _send(self, status, body, content_type="text/html; charset=utf-8"):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/callback":
            self._send(404, "Not found")
            return

        page = """<!doctype html>
                  <html lang="en">
                  <head><meta charset="utf-8"><title>LifeQuest Trello Authorization</title></head>
                  <body style="font-family:Segoe UI,Arial,sans-serif;background:#11111b;color:#f4f1ff;padding:40px">
                    <h2>Returning to LifeQuest…</h2>
                    <p id="status">Finishing the secure connection. You can return to LifeQuest.</p>
                    <script>
                      const callbackState = __CALLBACK_STATE__;
                      
                      (async () => {
                        const params = new URLSearchParams(window.location.hash.slice(1));
                        const token = params.get("token");
                        const error = params.get("error");
                        const status = document.getElementById("status");
                        if (error || !token) {
                          status.textContent = "Authorization was denied or no token was returned. You can close this tab and try again in LifeQuest.";
                          return;
                        }
                        try {
                          const response = await fetch("/token", {
                            method: "POST",
                            headers: {"Content-Type": "application/json"},
                            body: JSON.stringify({
                                token,
                                state: callbackState
                            })
                          });
                          if (!response.ok) throw new Error("Local handoff failed");
                          history.replaceState(null, "", "/callback");
                          status.textContent = "Trello is connected. You can return to LifeQuest now.";
                        } catch (_) {
                          status.textContent = "Could not pass the token to LifeQuest. Close this tab and try again.";
                        }
                      })();
                    </script>
                  </body>
                  </html>
               """

        page = page.replace("__CALLBACK_STATE__", json.dumps(self.server.state))
        self._send(200, page)

    def do_POST(self):
        if self.path != "/token":
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 8192:
                raise ValueError("Invalid callback payload.")

            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if payload.get("state") != self.server.state:
                raise ValueError("Invalid authorization state.")
            if not isinstance(payload, dict):
                raise ValueError("Invalid callback payload.")
            
            state = payload.get("state")
            if not isinstance(state, str) or not secrets.compare_digest(state, self.server.state):
                raise ValueError("Invalid authorization state.")
            
            token = payload.get("token", "")
            if not isinstance(token, str):
                raise ValueError("Invalid token format.")

            token = token.strip()
            if not token or len(token) > 4096:
                raise ValueError("Trello did not return a valid token.")

            self.server.token = token
            self._send(200, "Token received. Return to LifeQuest.", "text/plain; charset=utf-8")
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.server.error = str(exc)
            self._send(400, "Invalid token callback.", "text/plain; charset=utf-8")