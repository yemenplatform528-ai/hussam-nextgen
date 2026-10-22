import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import http from "node:http";
import { createHmac } from "node:crypto";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const backend = resolve(here, "..");
const serverFile = resolve(backend, "server.js");
const preloadFile = resolve(here, "mock-provider-quota.mjs");

test("chat fails closed without session; login enforces exact origin and password", async () => {
  const port = 18767;
  const child = spawn(process.execPath, ["--import", preloadFile, serverFile], {
    cwd: backend,
    env: {
      ...process.env,
      PORT: String(port),
      GEMINI_API_KEY: "fake-key",
      OPENAI_API_KEY: "",
      ALLOWED_ORIGIN: "http://127.0.0.1",
      HUSSAM_ACCESS_PASSWORD: "test password fixture only 2026",
      HUSSAM_SESSION_SECRET: "test session secret fixture only for tests",
      HUSSAM_REQUEST_BODY_TIMEOUT_MS: "250"
    },
    stdio: ["ignore", "pipe", "pipe"]
  });
  let output = "";
  child.stdout.on("data", chunk => { output += chunk.toString(); });
  child.stderr.on("data", chunk => { output += chunk.toString(); });
  const base = `http://127.0.0.1:${port}`;
  try {
    let ready = false;
    for (let i = 0; i < 50; i++) {
      if (child.exitCode !== null) throw new Error(`server exited early: ${output}`);
      try { const response = await fetch(`${base}/health`); if (response.ok) { ready = true; break; } } catch {}
      await delay(100);
    }
    assert.equal(ready, true, `server did not become ready: ${output}`);

    const stalledLoginStatus = await new Promise((resolveStatus, rejectStatus) => {
      const stalled = http.request(`${base}/api/session/login`, {
        method: "POST",
        headers: {
          Origin: "http://127.0.0.1",
          "CF-Connecting-IP": "192.0.2.50",
          "Content-Type": "application/json",
          "Content-Length": "100"
        }
      }, response => {
        response.resume();
        response.on("end", () => resolveStatus(response.statusCode));
      });
      stalled.on("error", error => rejectStatus(error));
      stalled.flushHeaders();
    });
    assert.equal(stalledLoginStatus, 408, "a stalled unauthenticated login body must time out");

    const preflight = await fetch(`${base}/api/chat`, {
      method: "OPTIONS",
      headers: { Origin: "http://127.0.0.1", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type" }
    });
    assert.equal(preflight.status, 204);
    assert.equal(preflight.headers.get("access-control-allow-origin"), "http://127.0.0.1");
    assert.match(preflight.headers.get("access-control-allow-headers") || "", /Authorization/i);

    const validLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(validLogin.status, 200);
    const loginData = await validLogin.json();
    assert.equal(typeof loginData.token, "string");
    assert.equal(loginData.expiresIn, 30 * 60, "stateless owner tokens must expire within 30 minutes");
    const validToken = loginData.token;
    const nullLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: "null"
    });
    assert.equal(nullLogin.status, 400);
    const oversizedLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: "x".repeat(9_000)
    });
    assert.equal(oversizedLogin.status, 413);
    const tamperedToken = validToken.slice(0, -1) + (validToken.endsWith("x") ? "y" : "x");
    const tamperedSession = await fetch(`${base}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", Authorization: `Bearer ${tamperedToken}` },
      body: JSON.stringify({ messages: [{ role: "user", content: "must not reach provider" }] })
    });
    assert.equal(tamperedSession.status, 401);

    const expiredPayload = Buffer.from(JSON.stringify({ exp: Math.floor(Date.now() / 1000) - 60 })).toString("base64url");
    const expiredSignature = createHmac("sha256", "test session secret fixture only for tests").update(expiredPayload).digest("base64url");
    const expiredSession = await fetch(`${base}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", Authorization: `Bearer ${expiredPayload}.${expiredSignature}` },
      body: JSON.stringify({ messages: [{ role: "user", content: "expired session must not reach provider" }] })
    });
    assert.equal(expiredSession.status, 401);

    const oversizedChat = await fetch(`${base}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", Authorization: `Bearer ${validToken}` },
      body: "x".repeat(101_000)
    });
    assert.equal(oversizedChat.status, 413);

    const stalledBodyStatus = await new Promise((resolveStatus, rejectStatus) => {
      const stalled = http.request(`${base}/api/chat`, {
        method: "POST",
        headers: {
          Origin: "http://127.0.0.1",
          Authorization: `Bearer ${validToken}`,
          "Content-Type": "application/json",
          "Content-Length": "100"
        }
      }, response => {
        response.resume();
        response.on("end", () => resolveStatus(response.statusCode));
      });
      stalled.on("error", error => rejectStatus(error));
      stalled.flushHeaders();
    });
    assert.equal(stalledBodyStatus, 408, "a stalled request body must time out rather than hold an upload slot indefinitely");
    assert.equal((output.match(/TEST_PROVIDER_CALL_/g) || []).length, 0);

    const noOrigin = await fetch(`${base}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content: "must not reach provider" }] })
    });
    assert.equal(noOrigin.status, 403);
    assert.equal((output.match(/TEST_PROVIDER_CALL_/g) || []).length, 0);

    const noSession = await fetch(`${base}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ messages: [{ role: "user", content: "must not reach provider" }] })
    });
    assert.equal(noSession.status, 401);
    assert.equal((output.match(/TEST_PROVIDER_CALL_/g) || []).length, 0);

    const loginIp = "203.0.113.10";
    const badLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", "CF-Connecting-IP": loginIp },
      body: JSON.stringify({ password: "incorrect password for test" })
    });
    assert.equal(badLogin.status, 401);
    for (let i = 0; i < 7; i++) {
      const attempt = await fetch(`${base}/api/session/login`, {
        method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", "CF-Connecting-IP": loginIp },
        body: JSON.stringify({ password: "incorrect password for test" })
      });
      assert.equal(attempt.status, 401);
    }
    const throttledLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", "CF-Connecting-IP": loginIp },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(throttledLogin.status, 429);
    const otherClientLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", "CF-Connecting-IP": "198.51.100.20" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(otherClientLogin.status, 200, "one client's failed attempts must not lock out another client");

    // Treat forwarded client identity as best-effort: rotating caller-supplied
    // IP values must still hit the global login ceiling without reaching inference.
    let globalThrottleObserved = false;
    for (let i = 1; i <= 120; i++) {
      const attempt = await fetch(`${base}/api/session/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", "CF-Connecting-IP": `192.0.2.${i}` },
        body: JSON.stringify({ password: "incorrect password for test" })
      });
      if (attempt.status === 429) {
        globalThrottleObserved = true;
        break;
      }
      assert.equal(attempt.status, 401);
    }
    assert.equal(globalThrottleObserved, true, "rotating forwarded IP values must not bypass the global login ceiling");

    const forgedOrigin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "https://attacker.example" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(forgedOrigin.status, 403);
    assert.equal((output.match(/TEST_PROVIDER_CALL_/g) || []).length, 0);
  } finally {
    child.kill("SIGTERM");
    await Promise.race([
      new Promise(resolveExit => child.once("exit", resolveExit)),
      delay(2000)
    ]);
  }
});
