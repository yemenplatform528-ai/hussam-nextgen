#!/usr/bin/env python3
"""Browser acceptance checks for the standalone Hussam AI portal auth flow."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "E2E owner password fixture only 2026"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(QuietHandler, directory=str(ROOT)),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state = {"expires_in": 1800, "chat_authorized": False, "chat_unauthorized": False, "provider_auth_failure": False}
    origin_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Vary": "Origin",
        "Content-Type": "application/json",
    }

    def fulfill(route, status, payload):
        route.fulfill(
            status=status,
            headers=origin_headers,
            body=json.dumps(payload, ensure_ascii=False),
        )

    def mock_api(route):
        request = route.request
        path = urlparse(request.url).path
        if request.method == "OPTIONS":
            route.fulfill(status=204, headers=origin_headers, body="")
            return
        if path == "/health":
            fulfill(route, 200, {
                "service": "hussam-ai-inference-bridge",
                "status": "online",
                "inferenceConfigured": True,
                "accessControlConfigured": True,
                "liveModelVerified": False,
                "provider": "mock",
                "model": "portal-e2e",
                "truth": "OBSERVED",
            })
            return
        if path == "/api/session/login":
            try:
                body = json.loads(request.post_data or "{}")
            except json.JSONDecodeError:
                body = {}
            if body.get("password") != PASSWORD:
                fulfill(route, 401, {"error": "INVALID_CREDENTIALS", "message": "رمز وصول غير صحيح"})
            else:
                fulfill(route, 200, {"token": "e2e-session-token", "expiresIn": state["expires_in"]})
            return
        if path == "/api/chat":
            state["chat_authorized"] = request.headers.get("authorization") == "Bearer e2e-session-token"
            if state["provider_auth_failure"] and state["chat_authorized"]:
                fulfill(route, 502, {"error": "PROVIDER_AUTHENTICATION_FAILED", "message": "تعذر التحقق من اعتماد مزود الاستدلال"})
                return
            if state["chat_unauthorized"] or not state["chat_authorized"]:
                state["chat_authorized"] = False
                fulfill(route, 401, {"error": "INVALID_SESSION", "message": "انتهت صلاحية الجلسة"})
            else:
                fulfill(route, 200, {
                    "answer": "HUSSAM_AI_PORTAL_AUTH_E2E_OK",
                    "provider": "mock",
                    "model": "portal-e2e",
                    "truth": "VERIFIED_RESPONSE",
                })
            return
        fulfill(route, 200, {})

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(7000)
            page.route("https://hussam-ai-inference-bridge.onrender.com/**", mock_api)
            page.goto(
                f"http://127.0.0.1:{server.server_port}/hussam-ai-portal/hussam-ai/index.html",
                wait_until="domcontentloaded",
            )

            assert not page.locator("#logoutButton").is_visible(), "logout must be hidden before login"
            assert "غير مشفر" in page.locator("#loginPanel").inner_text(), "local history storage warning must be visible"
            page.locator("#navDashboard").click()
            assert page.locator("#loginPanel").is_visible(), "protected dashboard must require login"

            page.locator("#accessPassword").fill("wrong password fixture only 2026")
            page.locator("#loginButton").click()
            page.wait_for_function(
                "() => document.getElementById('loginStatus').textContent.includes('تعذر الدخول')"
            )
            assert page.locator("#chatLayout").is_hidden(), "failed login must not open chat"

            page.locator("#accessPassword").fill(PASSWORD)
            page.locator("#loginButton").click()
            page.locator("#chatLayout").wait_for(state="visible")
            assert page.locator("#loginPanel").is_hidden()
            assert page.locator("#logoutButton").is_visible(), "logout must appear after successful login"

            page.locator("#navDashboard").click()
            assert page.locator("#dashboard").is_visible(), "authenticated dashboard should open"
            page.locator("#navChat").click()
            assert page.locator("#chatLayout").is_visible()

            page.locator("#prompt").fill("portal authentication browser test")
            page.locator("#form button[type='submit']").click()
            page.get_by_text("HUSSAM_AI_PORTAL_AUTH_E2E_OK").wait_for()
            assert state["chat_authorized"], "chat must send the bearer token"

            state["provider_auth_failure"] = True
            page.locator("#prompt").fill("provider credential failure must not log out the owner")
            page.locator("#form button[type='submit']").click()
            page.locator(".msg.assistant").filter(has_text="تعذر التحقق من اعتماد مزود الاستدلال").wait_for()
            assert page.locator("#chatLayout").is_visible(), "provider auth failure must not clear the owner session"
            assert page.locator("#loginPanel").is_hidden(), "provider auth failure must not expose the login panel"
            assert page.locator("#logoutButton").is_visible(), "owner logout must remain available after provider failure"
            state["provider_auth_failure"] = False

            assert "e2e-session-token" not in page.evaluate("JSON.stringify(localStorage)")
            page.locator("#logoutButton").click()
            assert page.locator("#loginPanel").is_visible(), "local logout must return to login"
            assert page.locator("#chatLayout").is_hidden(), "local logout must hide chat"
            assert page.locator("#dashboard").is_hidden(), "local logout must hide dashboard"
            assert not page.locator("#logoutButton").is_visible(), "logout control must hide after logout"

            state["chat_unauthorized"] = True
            page.locator("#accessPassword").fill(PASSWORD)
            page.locator("#loginButton").click()
            page.locator("#chatLayout").wait_for(state="visible")
            page.locator("#prompt").fill("force the API to reject this session")
            page.locator("#form button[type='submit']").click()
            page.locator("#loginPanel").wait_for(state="visible", timeout=5000)
            assert page.locator("#chatLayout").is_hidden(), "a chat 401 must return the portal to login"
            assert "انتهت صلاحية الجلسة" in page.locator("#loginStatus").inner_text()
            state["chat_unauthorized"] = False

            page.locator("#accessPassword").fill(PASSWORD)
            page.locator("#loginButton").click()
            page.locator("#chatLayout").wait_for(state="visible")
            page.locator("#navDashboard").click()
            assert page.locator("#dashboard").is_visible()
            state["chat_unauthorized"] = True
            page.locator("#testInference").click()
            page.locator("#loginPanel").wait_for(state="visible", timeout=5000)
            assert page.locator("#dashboard").is_hidden(), "a dashboard chat 401 must return the portal to login"
            assert "انتهت صلاحية الجلسة" in page.locator("#loginStatus").inner_text()
            state["chat_unauthorized"] = False

            state["expires_in"] = 1
            page.locator("#accessPassword").fill(PASSWORD)
            page.locator("#loginButton").click()
            page.locator("#chatLayout").wait_for(state="visible")
            page.locator("#loginPanel").wait_for(state="visible", timeout=5000)
            assert page.locator("#chatLayout").is_hidden(), "automatic expiry must hide chat"
            assert not page.locator("#logoutButton").is_visible(), "automatic expiry must clear the local session"
            assert "انتهت مدة الجلسة" in page.locator("#loginStatus").inner_text()

            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    print("Hussam AI portal auth browser contract: PASS")


if __name__ == "__main__":
    main()
