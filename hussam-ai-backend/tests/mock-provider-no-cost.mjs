const originalFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : input?.url || "";
  if (url.startsWith("https://api.openai.com/") || url.includes("generativelanguage.googleapis.com")) {
    process.stdout.write("TEST_EXTERNAL_PROVIDER_CALL\\n");
    return new Response(JSON.stringify({ choices: [{ message: { content: "unexpected provider call" } }] }), {
      status: 200,
      headers: { "content-type": "application/json" }
    });
  }
  return originalFetch(input, init);
};
