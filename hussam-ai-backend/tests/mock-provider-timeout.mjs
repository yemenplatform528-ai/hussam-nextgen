// Test-only mock. It never contacts a real provider.
globalThis.fetch = async () => {
  const error = new Error("simulated provider timeout");
  error.name = "TimeoutError";
  throw error;
};
