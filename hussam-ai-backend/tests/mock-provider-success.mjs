// Deterministic test-only successful provider response. Never used by the deployed service.
let calls = 0;
globalThis.fetch = async () => {
  calls += 1;
  console.log(`TEST_PROVIDER_SUCCESS_${calls}`);
  return new Response(JSON.stringify({
    candidates: [{ content: { parts: [{ text: "HUSSAM_LIVE_HEALTH_TEST_OK" }] } }]
  }), { status: 200, headers: { "Content-Type": "application/json" } });
};
