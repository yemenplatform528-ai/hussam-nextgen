// Deterministic provider HTTP status for local regression tests only.
const status = Number(process.env.TEST_PROVIDER_STATUS || 503);
const providerStatus = status === 503 ? "UNAVAILABLE" : status === 404 ? "NOT_FOUND" : "TEST_STATUS";
globalThis.fetch = async () => new Response(JSON.stringify({
  error: { status: providerStatus, message: "mocked provider status" }
}), { status, headers: { "Content-Type": "application/json" } });
