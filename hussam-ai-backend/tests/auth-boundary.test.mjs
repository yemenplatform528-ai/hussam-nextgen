import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
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
      GEMINI_API_KEY: "test-only-not-a-real-key",
      OPENAI_API_KEY: "",
      ALLOWED_ORIGIN: "http://127.0.0.1",
      HUSSAM_ACCESS_PASSWORD: "test-access-password-12345",
      HUSSAM_SESSION_SECRET: "test-session-secret-abcdefghijklmnopqrstuvwxyz"
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

    const badLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "incorrect-password-value" })
    });
    assert.equal(badLogin.status, 401);
    for (let i = 0; i < 7; i++) {
      const attempt = await fetch(`${base}/api/session/login`, {
        method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
        body: JSON.stringify({ password: "incorrect-password-value" })
      });
      assert.equal(attempt.status, 401);
    }
    const throttledLogin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "test-access-password-12345" })
    });
    assert.equal(throttledLogin.status, 429);

    const forgedOrigin = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "https://attacker.example" },
      body: JSON.stringify({ password: "test-access-password-12345" })
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
