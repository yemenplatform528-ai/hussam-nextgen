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

for (const [upstreamStatus, expectedStatus, expectedCode] of [
  [401, 401, "PROVIDER_AUTHENTICATION_FAILED"],
  [403, 403, "PROVIDER_AUTHENTICATION_FAILED"],
  [404, 404, "PROVIDER_MODEL_UNAVAILABLE"]
]) {
  test(`provider HTTP ${upstreamStatus} maps to ${expectedStatus} ${expectedCode}`, async () => {
    const port = 18800 + upstreamStatus;
    const child = spawn(process.execPath, ["--import", preloadFile, serverFile], {
      cwd: backend,
      env: {
        ...process.env,
        PORT: String(port),
        TEST_PROVIDER_STATUS: String(upstreamStatus),
        GEMINI_API_KEY: "test-placeholder",
        OPENAI_API_KEY: "",
        ALLOWED_ORIGIN: "http://127.0.0.1"
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
        try {
          const response = await fetch(`${base}/health`);
          if (response.ok) { ready = true; break; }
        } catch {}
        await delay(100);
      }
      assert.equal(ready, true, `server did not become ready: ${output}`);
      const response = await fetch(`${base}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Origin: "http://127.0.0.1" },
        body: JSON.stringify({ messages: [{ role: "user", content: "deterministic provider status test" }] })
      });
      const body = await response.json();
      assert.equal(response.status, expectedStatus);
      assert.equal(body.error, expectedCode);
      assert.equal(JSON.stringify(body).includes("test-placeholder"), false);
      assert.equal(JSON.stringify(body).includes("mocked provider status"), false);
      assert.equal(output.includes("test-placeholder"), false);
    } finally {
      child.kill("SIGTERM");
      await Promise.race([
        new Promise(resolveExit => child.once("exit", resolveExit)),
        delay(2000)
      ]);
    }
  });
}
