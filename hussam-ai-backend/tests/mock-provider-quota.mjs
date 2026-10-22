// Deterministic test-only quota failure. Never used by the deployed service.
let calls = 0;
globalThis.fetch = async () => {
  calls += 1;
  console.log(`TEST_PROVIDER_CALL_${calls}`);
  return new Response(JSON.stringify({
    error: { status: "RESOURCE_EXHAUSTED", message: "simulated quota exhaustion" }
  }), { status: 429, headers: { "Content-Type": "application/json" } });
};
