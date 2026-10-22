import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
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
      HUSSAM_SESSION_SECRET: "test session secret fixture only for tests"
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

    const validLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(validLogin.status, 200);
    const loginData = await validLogin.json();
    assert.equal(typeof loginData.token, "string");
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
