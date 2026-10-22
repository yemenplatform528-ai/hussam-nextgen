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

test("quota exhaustion returns 429 and makes exactly one provider attempt", async () => {
  const port = 18766;
  const child = spawn(process.execPath, ["--import", preloadFile, serverFile], {
    cwd: backend,
    env: { ...process.env, PORT: String(port), GEMINI_API_KEY: "fake-key",
      OPENAI_API_KEY: "", ALLOWED_ORIGIN: "http://127.0.0.1",
      HUSSAM_ACCESS_PASSWORD: "test password fixture only 2026", HUSSAM_SESSION_SECRET: "test session secret fixture only for tests" },
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
    const login = await fetch(`${base}/api/session/login`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(login.status, 200);
    const loginData = await login.json();
    const response = await fetch(`${base}/api/chat`, {
      method: "POST", headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", Authorization: `Bearer ${loginData.token}` },
      body: JSON.stringify({ messages: [{ role: "user", content: "deterministic quota test" }] })
    });
    const body = await response.json();
    assert.equal(response.status, 429);
    assert.equal(body.error, "PROVIDER_QUOTA_OR_RATE_LIMIT");
    assert.equal((output.match(/TEST_PROVIDER_CALL_/g) || []).length, 1, `expected one provider call, got logs: ${output}`);
    assert.equal(JSON.stringify(body).includes("test-only-not-a-real-key"), false);
    assert.equal(output.includes("test-only-not-a-real-key"), false);
  } finally {
    child.kill("SIGTERM");
    await Promise.race([new Promise(resolveExit => child.once("exit", resolveExit)), delay(2000)]);
  }
});
