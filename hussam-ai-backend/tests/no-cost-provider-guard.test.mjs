import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const backend = resolve(here, "..");
const serverFile = resolve(backend, "server.js");
const preloadFile = resolve(here, "mock-provider-no-cost.mjs");

test("provider keys are not used without explicit free-tier or billable approval", async () => {
  const port = 18771;
  const child = spawn(process.execPath, ["--import", preloadFile, serverFile], {
    cwd: backend,
    env: {
      ...process.env,
      PORT: String(port),
      GEMINI_API_KEY: "test-only-gemini-key",
      HUSSAM_GEMINI_FREE_TIER_ENABLED: "false",
      OPENAI_API_KEY: "test-only-openai-key",
      HUSSAM_ALLOW_BILLABLE_AI: "false",
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
    const health = await (await fetch(`${base}/health`)).json();
    assert.equal(health.provider, "none");
    assert.equal(health.inferenceConfigured, false);

    const login = await fetch(`${base}/api/session/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
      body: JSON.stringify({ password: "test password fixture only 2026" })
    });
    assert.equal(login.status, 200);
    const loginData = await login.json();

    const response = await fetch(`${base}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: "http://127.0.0.1",
        Authorization: `Bearer ${loginData.token}`
      },
      body: JSON.stringify({ messages: [{ role: "user", content: "must not reach a billable provider" }] })
    });
    const body = await response.json();
    assert.equal(response.status, 503);
    assert.equal(body.error, "INFERENCE_NOT_CONFIGURED");
    assert.equal(output.includes("TEST_EXTERNAL_PROVIDER_CALL"), false, "no external provider request may be sent");
  } finally {
    child.kill("SIGTERM");
    await Promise.race([
      new Promise(resolveExit => child.once("exit", resolveExit)),
      delay(2000)
    ]);
  }
});
