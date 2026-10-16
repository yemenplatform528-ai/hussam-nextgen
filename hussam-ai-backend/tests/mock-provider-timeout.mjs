// Deterministic test-only provider failure. Never used by the deployed service.
globalThis.fetch = async () => {
  const error = new Error("simulated provider timeout");
  error.name = "TimeoutError";
  throw error;
};
