"""Disposable Cognito-shaped password grant for the local browser journey."""

import json
import os
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import jwt

if os.environ.get("JOURNEY_FIXTURE") != "isolated-only":
    raise RuntimeError("Local fixture opt-in required")

private_key = (
    Path("/fixtures") / (os.environ["JOURNEY_RUN_ID"] + ".private.pem")
).read_bytes()
issuer = "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_LOCALJOURNEY"


class Handler(BaseHTTPRequestHandler):
    def _headers(self, code):
        self.send_response(code)
        self.send_header("Content-Type", "application/x-amz-json-1.1")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:18082")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()

    def do_OPTIONS(self):
        self._headers(204)

    def do_POST(self):
        if (
            self.headers.get("X-Amz-Target")
            != "AWSCognitoIdentityProviderService.InitiateAuth"
        ):
            self._headers(400)
            self.wfile.write(b'{"__type":"UnsupportedOperationException"}')
            return
        try:
            payload = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
            )
        except (ValueError, TypeError):
            self._headers(400)
            return
        users = {
            "journey-owner@example.test": f"journey-{os.environ['JOURNEY_RUN_ID']}-owner",
            "journey-other@example.test": f"journey-{os.environ['JOURNEY_RUN_ID']}-other",
        }
        auth = payload.get("AuthParameters") or {}
        if (
            payload.get("AuthFlow") != "USER_PASSWORD_AUTH"
            or payload.get("ClientId") != "localjourneyclient"
            or auth.get("PASSWORD") != "local-only"
            or auth.get("USERNAME") not in users
        ):
            self._headers(400)
            self.wfile.write(
                b'{"__type":"NotAuthorizedException","message":"Invalid fixture credentials"}'
            )
            return
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "iss": issuer,
                "client_id": "localjourneyclient",
                "sub": users[auth["USERNAME"]],
                "token_use": "access",
                "iat": now,
                "exp": now + timedelta(hours=2),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "local-journey-key"},
        )
        self._headers(200)
        self.wfile.write(
            json.dumps(
                {
                    "AuthenticationResult": {
                        "AccessToken": token,
                        "IdToken": "local-fixture-id",
                        "RefreshToken": "local-fixture-refresh",
                        "ExpiresIn": 7200,
                        "TokenType": "Bearer",
                    }
                }
            ).encode()
        )


HTTPServer(("0.0.0.0", 8999), Handler).serve_forever()
