// Deterministic provider HTTP failure for local tests only; never used by deployment.
const status = Number(process.env.TEST_PROVIDER_STATUS || 503);
globalThis.fetch = async () => new Response(JSON.stringify({
  error: { status: status === 503 ? "UNAVAILABLE" : status === 404 ? "NOT_FOUND" : "TEST_STATUS", message: "mocked provider status" }
}), { status, headers: { "Content-Type": "application/json" } });
