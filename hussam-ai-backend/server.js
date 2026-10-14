import http from "node:http";

const PORT = Number(process.env.PORT || 10000);
const API_KEY = process.env.OPENAI_API_KEY || "";
const MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "https://hussam-ai-standalone-portal.onrender.com";

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
  if (req.method === "GET" && url.pathname === "/health") {
    res.writeHead(200);
    return res.end(JSON.stringify({
      service: "hussam-ai-inference-bridge",
      status: "online",
      inferenceConfigured: Boolean(API_KEY),
      model: MODEL,
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
  if (!API_KEY) {
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
  const messages = body.messages;
  if (!Array.isArray(messages) || messages.length < 1 || messages.length > 40 ||
      messages.some(m => !m || !["system", "user", "assistant"].includes(m.role) ||
        typeof m.content !== "string" || m.content.length > 20_000)) {
    res.writeHead(400);
    return res.end(JSON.stringify({ error: "INVALID_MESSAGES" }));
  }

  try {
    const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: MODEL,
        messages,
        temperature: 0.65,
        max_tokens: 800
      }),
      signal: AbortSignal.timeout(60_000)
    });
    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      const status = upstream.status === 429 ? 429 : 502;
      res.writeHead(status);
      return res.end(JSON.stringify({
        error: upstream.status === 429 ? "PROVIDER_QUOTA_OR_RATE_LIMIT" : "PROVIDER_REQUEST_FAILED",
        message: upstream.status === 429
          ? "رفض مزوّد الاستدلال الطلب بسبب الحصة أو حدّ المعدل. لم يُنتج رد."
          : "لم ينجح طلب مزوّد الاستدلال. لم يُنتج رد."
      }));
    }
    const answer = data?.choices?.[0]?.message?.content;
    if (typeof answer !== "string" || !answer.trim()) {
      res.writeHead(502);
      return res.end(JSON.stringify({ error: "EMPTY_MODEL_RESPONSE" }));
    }
    res.writeHead(200);
    return res.end(JSON.stringify({ answer: answer.trim(), model: MODEL, truth: "VERIFIED_RESPONSE" }));
  } catch (error) {
    res.writeHead(502);
    return res.end(JSON.stringify({
      error: "INFERENCE_CONNECTION_FAILED",
      message: "تعذر الاتصال بمزوّد الاستدلال أو انتهت المهلة. لم يُنتج رد."
    }));
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Hussam AI inference bridge listening on ${PORT}`);
});
