#!/usr/bin/env python3
"""Read-only production smoke checks for the standalone Hussam AI portal."""
import json
import os
import sys
import urllib.error
import urllib.request

FRONTEND = os.environ.get("FRONTEND_URL", "https://hussam-ai-standalone-portal.onrender.com").rstrip("/")
BACKEND = os.environ.get("BACKEND_URL", "https://hussam-ai-inference-bridge.onrender.com").rstrip("/")
TIMEOUT = 90


def request(url, method="GET", headers=None, body=None):
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def check(name, ok, detail):
    result = {"check": name, "status": "PASS" if ok else "FAIL", "detail": detail}
    print(json.dumps(result, ensure_ascii=False))
    if not ok:
        raise SystemExit(1)


# Public landing page and the actual authenticated chat portal must both serve.
status, _, body = request(FRONTEND + "/")
landing = body.decode("utf-8", errors="replace")
check("landing_page_http", status == 200 and "Hussam AI" in landing,
      f"HTTP {status}; Hussam AI identity present")
check("landing_page_route", 'href="/hussam-ai/"' in landing,
      "landing page links to the standalone chat portal")

status, _, body = request(FRONTEND + "/hussam-ai/")
portal = body.decode("utf-8", errors="replace")
check("chat_portal_http", status == 200, f"HTTP {status}")
check("chat_portal_identity", "Hussam AI" in portal and BACKEND in portal,
      "chat portal identity and configured inference backend")

# Backend liveness and owner access-control readiness are separate facts.
status, _, body = request(BACKEND + "/health")
try:
    health = json.loads(body)
except Exception:
    health = {}
check("backend_health", status == 200 and health.get("status") == "online",
      f"HTTP {status}; status={health.get('status')}")
check("owner_access_control", health.get("accessControlConfigured") is True,
      f"accessControlConfigured={health.get('accessControlConfigured')}")

# Allowed browser origin must receive exact-origin CORS headers.
origin = FRONTEND
status, cors_headers, _ = request(
    BACKEND + "/api/chat",
    method="OPTIONS",
    headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    },
)
allow_origin = cors_headers.get("Access-Control-Allow-Origin") or cors_headers.get("access-control-allow-origin")
check("allowed_origin_cors", status == 204 and allow_origin == origin,
      f"HTTP {status}; allow-origin={allow_origin}")

# A cross-origin login attempt must be rejected before credentials are parsed.
status, _, body = request(
    BACKEND + "/api/session/login",
    method="POST",
    headers={"Origin": "https://invalid.example", "Content-Type": "application/json"},
    body=b'{"password":"not-a-real-password"}',
)
check("untrusted_origin_rejected", status == 403,
      f"HTTP {status}; response={body[:160].decode('utf-8', errors='replace')}")

# Chat must reject an unauthenticated request even when the allowed origin is used.
status, _, body = request(
    BACKEND + "/api/chat",
    method="POST",
    headers={"Origin": origin, "Content-Type": "application/json"},
    body=b'{"messages":[]}',
)
check("unauthenticated_chat_rejected", status == 401,
      f"HTTP {status}; response={body[:160].decode('utf-8', errors='replace')}")

# A healthy, secure service can still have inference intentionally disabled.
print(json.dumps({
    "summary": "PRODUCTION_SMOKE_PASS",
    "inferenceConfigured": health.get("inferenceConfigured"),
    "liveModelVerified": health.get("liveModelVerified"),
    "provider": health.get("provider"),
    "model": health.get("model"),
    "truth": "OBSERVED",
}, ensure_ascii=False))
