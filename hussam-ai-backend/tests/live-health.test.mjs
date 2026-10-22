import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const backend = resolve(here, "..");
const serverFile = resolve(backend, "server.js");
const preloadFile = resolve(here, "mock-provider-success.mjs");

test("health flips liveModelVerified only after a non-empty provider response", async () => {
  const port = 18768;
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
    let health = await (await fetch(`${base}/health`)).json();
    assert.equal(health.liveModelVerified, false);

    const login = await fetch(`${base}/api/session/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(login.status, 200);
    const { token } = await login.json();

    const chat = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ messages: [{ role: "user", content: "deterministic health test" }] })
    });
    const response = await chat.json();
    assert.equal(chat.status, 200);
    assert.equal(response.truth, "VERIFIED_RESPONSE");
    assert.equal(response.answer, "HUSSAM_LIVE_HEALTH_TEST_OK");

    health = await (await fetch(`${base}/health`)).json();
    assert.equal(health.liveModelVerified, true, "health must record a successful non-empty provider response");
    assert.equal((output.match(/TEST_PROVIDER_SUCCESS_/g) || []).length, 1);
  } finally {
    child.kill("SIGTERM");
    await Promise.race([
      new Promise(resolveExit => child.once("exit", resolveExit)),
      delay(2000)
    ]);
  }
});
