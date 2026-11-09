import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const backend = resolve(here, "..");
const serverFile = resolve(backend, "server.js");
const preloadFile = resolve(here, "mock-provider-status.mjs");
const ownerPassword = "test owner password fixture 2026";
const sessionSecret = "0123456789abcdef0123456789abcdef";
const origin = "http://127.0.0.1";

for (const [upstreamStatus, expectedCode] of [
  [401, "PROVIDER_AUTHENTICATION_FAILED"],
  [403, "PROVIDER_AUTHENTICATION_FAILED"],
  [404, "PROVIDER_MODEL_UNAVAILABLE"]
]) {
  test(`provider HTTP ${upstreamStatus} remains a gateway failure, not owner-session 401`, async () => {
    const port = 19_000 + upstreamStatus;
    const child = spawn(process.execPath, ["--import", preloadFile, serverFile], {
      cwd: backend,
      env: {
        ...process.env,
        PORT: String(port),
        TEST_PROVIDER_STATUS: String(upstreamStatus),
        GEMINI_API_KEY: "fake-key",
        HUSSAM_GEMINI_FREE_TIER_ENABLED: "true",
        HUSSAM_ACCESS_PASSWORD: ownerPassword,
        HUSSAM_SESSION_SECRET: sessionSecret,
        OPENAI_API_KEY: "",
        ALLOWED_ORIGIN: origin
      },
      stdio: ["ignore", "pipe", "pipe"]
    });
    let output = "";
    child.stdout.on("data", chunk => { output += chunk.toString(); });
    child.stderr.on("data", chunk => { output += chunk.toString(); });
    const base = `http://127.0.0.1:${port}`;

    try {
      let ready = false;
      for (let i = 0; i < 50; i += 1) {
        if (child.exitCode !== null) throw new Error(`server exited early: ${output}`);
        try {
          const response = await fetch(`${base}/health`);
          if (response.ok) { ready = true; break; }
        } catch {}
        await delay(100);
      }
      assert.equal(ready, true, `server did not become ready: ${output}`);

      const login = await fetch(`${base}/api/session/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Origin: origin },
        body: JSON.stringify({ password: ownerPassword })
      });
      assert.equal(login.status, 200);
      assert.equal(login.headers.get("cache-control"), "no-store");
      const loginBody = await login.json();
      assert.equal(typeof loginBody.token, "string");

      const response = await fetch(`${base}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: origin,
          Authorization: `Bearer ${loginBody.token}`
        },
        body: JSON.stringify({ messages: [{ role: "user", content: "provider status regression" }] })
      });
      const body = await response.json();
      assert.equal(response.status, 502, "upstream 401/403/404 must not be confused with owner-session expiry");
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.equal(body.error, expectedCode);
      assert.notEqual(body.error, "AUTHENTICATION_REQUIRED");
      assert.equal(JSON.stringify(body).includes("fake-key"), false);
      assert.equal(JSON.stringify(body).includes("mocked provider status"), false);

      const health = await fetch(`${base}/health`);
      const healthBody = await health.json();
      assert.equal(healthBody.liveModelVerified, false, "failed provider requests must not mark live inference verified");
      assert.equal(output.includes("fake-key"), false);
      assert.equal(output.includes("mocked provider status"), false);
    } finally {
      child.kill("SIGTERM");
      await Promise.race([
        new Promise(resolveExit => child.once("exit", resolveExit)),
        delay(2000)
      ]);
    }
  });
}
