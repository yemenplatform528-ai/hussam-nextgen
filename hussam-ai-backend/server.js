import http from "node:http";

const PORT = Number(process.env.PORT || 10000);
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-2.5-flash";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "https://hussam-ai-standalone-portal.onrender.com";

function activeProvider() {
  if (GEMINI_API_KEY) return { provider: "gemini", model: GEMINI_MODEL };
  if (OPENAI_API_KEY) return { provider: "openai", model: OPENAI_MODEL };
  return { provider: "none", model: null };
}

function validMessages(messages) {
  return Array.isArray(messages) && messages.length >= 1 && messages.length <= 40 &&
    !messages.some(m => !m || !["system", "user", "assistant"].includes(m.role) ||
      typeof m.content !== "string" || m.content.length > 20_000);
}

async function generateWithGemini(messages, model) {
  const systemText = messages.filter(m => m.role === "system").map(m => m.content).join("\n\n");
  const contents = messages.filter(m => m.role !== "system").map(m => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: m.content }]
  }));
  if (!contents.length) throw new Error("NO_USER_CONTENT");

  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
    {
      method: "POST",
      headers: {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        ...(systemText ? { systemInstruction: { parts: [{ text: systemText }] } } : {}),
        contents,
        generationConfig: { temperature: 0.65, maxOutputTokens: 800 }
      }),
      signal: AbortSignal.timeout(60_000)
    }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error("GEMINI_REQUEST_FAILED");
    error.status = response.status;
    throw error;
  }
  const answer = data?.candidates?.[0]?.content?.parts
    ?.map(part => typeof part.text === "string" ? part.text : "")
    .join("").trim();
  if (!answer) throw new Error("EMPTY_MODEL_RESPONSE");
  return answer;
}

async function generateWithOpenAI(messages, model) {
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${OPENAI_API_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ model, messages, temperature: 0.65, max_tokens: 800 }),
    signal: AbortSignal.timeout(60_000)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error("OPENAI_REQUEST_FAILED");
    error.status = response.status;
    throw error;
  }
  const answer = data?.choices?.[0]?.message?.content;
  if (typeof answer !== "string" || !answer.trim()) throw new Error("EMPTY_MODEL_RESPONSE");
  return answer.trim();
}

const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin || "";
  if (origin === ALLOWED_ORIGIN) {
    res.setHeader("Access-Control-Allow-Origin", ALLOWED_ORIGIN);
    res.setHeader("Vary", "Origin");
  }
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  if (req.method === "OPTIONS") { res.writeHead(204); return res.end(); }

  const url = new URL(req.url || "/", "http://localhost");
  const active = activeProvider();
  if (req.method === "GET" && url.pathname === "/health") {
    res.writeHead(200);
    return res.end(JSON.stringify({
      service: "hussam-ai-inference-bridge",
      status: "online",
      inferenceConfigured: active.provider !== "none",
      provider: active.provider,
      model: active.model,
      truth: "OBSERVED"
    }));
  }
  if (req.method !== "POST" || url.pathname !== "/api/chat") {
    res.writeHead(404);
    return res.end(JSON.stringify({ error: "NOT_FOUND" }));
  }
  if (origin && origin !== ALLOWED_ORIGIN) {
    res.writeHead(403);
    return res.end(JSON.stringify({ error: "ORIGIN_NOT_ALLOWED" }));
  }
  if (active.provider === "none") {
    res.writeHead(503);
    return res.end(JSON.stringify({
      error: "INFERENCE_NOT_CONFIGURED",
      message: "الخادم يعمل، لكن لم يُضبط اعتماد صالح لمزوّد الاستدلال. لم يتم توليد رد."
    }));
  }

  let raw = "";
  for await (const chunk of req) {
    raw += chunk;
    if (raw.length > 100_000) {
      res.writeHead(413);
      return res.end(JSON.stringify({ error: "REQUEST_TOO_LARGE" }));
    }
  }
  let body;
  try { body = JSON.parse(raw || "{}"); } catch {
    res.writeHead(400);
    return res.end(JSON.stringify({ error: "INVALID_JSON" }));
  }
  if (!validMessages(body.messages)) {
    res.writeHead(400);
    return res.end(JSON.stringify({ error: "INVALID_MESSAGES" }));
  }

  try {
    const answer = active.provider === "gemini"
      ? await generateWithGemini(body.messages, active.model)
      : await generateWithOpenAI(body.messages, active.model);
    res.writeHead(200);
    return res.end(JSON.stringify({
      answer,
      provider: active.provider,
      model: active.model,
      truth: "VERIFIED_RESPONSE"
    }));
  } catch (error) {
    // Log only sanitized upstream diagnostics; never log API keys, headers, prompts, or provider response bodies.
    console.warn("Inference upstream failure", JSON.stringify({
      provider: active.provider,
      model: active.model,
      status: Number.isInteger(error?.status) ? error.status : null,
      errorName: typeof error?.name === "string" ? error.name : "Error",
      errorCode: typeof error?.cause?.code === "string" ? error.cause.code : null
    }));
    const status = error?.status === 429 ? 429 : 502;
    res.writeHead(status);
    return res.end(JSON.stringify({
      error: error?.message === "EMPTY_MODEL_RESPONSE"
        ? "EMPTY_MODEL_RESPONSE"
        : error?.status === 429
          ? "PROVIDER_QUOTA_OR_RATE_LIMIT"
          : "INFERENCE_CONNECTION_FAILED",
      message: error?.status === 429
        ? "رفض مزوّد الاستدلال الطلب بسبب الحصة أو حد المعدل. لم يُنتج رد."
        : "تعذر إكمال طلب الاستدلال. لم يُنتج رد."
    }));
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Hussam AI inference bridge listening on ${PORT}`);
});
