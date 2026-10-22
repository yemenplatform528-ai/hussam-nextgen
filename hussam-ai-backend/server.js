import http from "node:http";
import { createHmac, timingSafeEqual } from "node:crypto";
import { isIP } from "node:net";

const PORT = Number(process.env.PORT || 10000);
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
const GEMINI_MODEL = process.env.GEMINI_MODEL || "gemini-3.6-flash";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";
const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";
const ALLOWED_ORIGIN = process.env.ALLOWED_ORIGIN || "https://hussam-ai-standalone-portal.onrender.com";
const HUSSAM_ACCESS_PASSWORD = process.env.HUSSAM_ACCESS_PASSWORD || "";
const HUSSAM_SESSION_SECRET = process.env.HUSSAM_SESSION_SECRET || "";
const SESSION_TTL_SECONDS = 12 * 60 * 60;

function sessionReady() {
  return HUSSAM_ACCESS_PASSWORD.length >= 16 && HUSSAM_SESSION_SECRET.length >= 32;
}
function signSession(payload) {
  const encoded = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = createHmac("sha256", HUSSAM_SESSION_SECRET).update(encoded).digest("base64url");
  return encoded + "." + signature;
}
function validSessionToken(token) {
  if (!sessionReady() || typeof token !== "string") return false;
  const split = token.lastIndexOf(".");
  if (split <= 0) return false;
  const encoded = token.slice(0, split);
  const supplied = Buffer.from(token.slice(split + 1));
  const expected = Buffer.from(createHmac("sha256", HUSSAM_SESSION_SECRET).update(encoded).digest("base64url"));
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return false;
  try {
    const payload = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    return Number.isInteger(payload.exp) && payload.exp > Math.floor(Date.now() / 1000);
  } catch { return false; }
}
function bearerToken(req) {
  const value = String(req.headers.authorization || "");
  return value.startsWith("Bearer ") ? value.slice(7) : "";
}
function sameSecret(a, b) {
  const aa = Buffer.from(String(a || ""));
  const bb = Buffer.from(String(b || ""));
  return aa.length > 0 && aa.length === bb.length && timingSafeEqual(aa, bb);
}
const rateBuckets = new Map();
function clientAddress(req) {
  // Render serves this public service through Cloudflare. Only accept a syntactically
  // valid CF-Connecting-IP value; otherwise fall back to the socket address.
  const forwarded = String(req.headers["cf-connecting-ip"] || "").trim();
  if (isIP(forwarded)) return forwarded;
  return req.socket.remoteAddress || "unknown";
}
function allowRate(key, limit, windowMs) {
  const now = Date.now();
  let bucket = rateBuckets.get(key);
  if (!bucket || now >= bucket.resetAt) bucket = { count: 0, resetAt: now + windowMs };
  if (bucket.count >= limit) {
    rateBuckets.set(key, bucket);
    return false;
  }
  bucket.count += 1;
  rateBuckets.set(key, bucket);
  if (rateBuckets.size > 100) {
    for (const [k, value] of rateBuckets) if (now >= value.resetAt) rateBuckets.delete(k);
  }
  return true;
}
let activeGenerations = 0;
let activeUploads = 0;

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

  // Strict one-model/one-request policy: do not fan out to other models when
  // quota or availability errors occur. This avoids multiplying upstream calls
  // and keeps the no-cost/quota boundary explicit. Model changes are operator-controlled.
  const models = model ? [model] : [];
  let lastError;
  for (const candidateModel of models) {
    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(candidateModel)}:generateContent`,
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
        error.model = candidateModel;
        error.providerStatus = typeof data?.error?.status === "string" ? data.error.status : null;
        error.providerMessage = typeof data?.error?.message === "string" ? data.error.message.slice(0, 300) : null;
        lastError = error;
        // One configured model means one upstream attempt. Never rotate through models
        // automatically: that can multiply quota consumption and obscure the real failure.
        throw error;
      }
      const answer = data?.candidates?.[0]?.content?.parts
        ?.map(part => typeof part.text === "string" ? part.text : "")
        .join("").trim();
      if (!answer) {
        const error = new Error("EMPTY_MODEL_RESPONSE");
        error.model = candidateModel;
        throw error;
      }
      return { answer, model: candidateModel };
    } catch (error) {
      throw error;
    }
  }
  throw lastError || new Error("GEMINI_MODELS_UNAVAILABLE");
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
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
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
      accessControlConfigured: sessionReady(),
      liveModelVerified: false,
      provider: active.provider,
      model: active.model,
      truth: "OBSERVED"
    }));
  }
  if (req.method === "POST" && url.pathname === "/api/session/login") {
    if (origin !== ALLOWED_ORIGIN) {
      res.writeHead(403);
      return res.end(JSON.stringify({ error: "ORIGIN_NOT_ALLOWED" }));
    }
    if (!allowRate("login:" + clientAddress(req), 8, 15 * 60_000)) {
      res.writeHead(429);
      return res.end(JSON.stringify({ error: "LOGIN_RATE_LIMITED", message: "تجاوزت محاولات الدخول المسموح بها مؤقتًا." }));
    }
    if (!sessionReady()) {
      res.writeHead(503);
      return res.end(JSON.stringify({ error: "ACCESS_CONTROL_NOT_CONFIGURED", message: "لم تُضبط متغيرات حماية الوصول في الخادم؛ الدخول مغلق افتراضيًا." }));
    }
    let loginRaw = "";
    for await (const chunk of req) {
      loginRaw += chunk;
      if (loginRaw.length > 8_192) {
        res.writeHead(413);
        return res.end(JSON.stringify({ error: "REQUEST_TOO_LARGE" }));
      }
    }
    let loginBody;
    try { loginBody = JSON.parse(loginRaw || "{}"); } catch {
      res.writeHead(400);
      return res.end(JSON.stringify({ error: "INVALID_JSON" }));
    }
    if (!loginBody || typeof loginBody !== "object" || Array.isArray(loginBody)) {
      res.writeHead(400);
      return res.end(JSON.stringify({ error: "INVALID_LOGIN_BODY" }));
    }
    if (!sameSecret(loginBody.password, HUSSAM_ACCESS_PASSWORD)) {
      res.writeHead(401);
      return res.end(JSON.stringify({ error: "INVALID_ACCESS_PASSWORD", message: "رمز الدخول غير صحيح." }));
    }
    const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
    const token = signSession({ exp });
    res.writeHead(200);
    return res.end(JSON.stringify({ authenticated: true, token, expiresIn: SESSION_TTL_SECONDS }));
  }
  if (req.method !== "POST" || url.pathname !== "/api/chat") {
    res.writeHead(404);
    return res.end(JSON.stringify({ error: "NOT_FOUND" }));
  }
  if (origin !== ALLOWED_ORIGIN) {
    res.writeHead(403);
    return res.end(JSON.stringify({ error: "ORIGIN_NOT_ALLOWED" }));
  }
  if (!sessionReady()) {
    res.writeHead(503);
    return res.end(JSON.stringify({ error: "ACCESS_CONTROL_NOT_CONFIGURED", message: "لم تُضبط متغيرات حماية الوصول في الخادم؛ المحادثة مغلقة افتراضيًا." }));
  }
  if (!validSessionToken(bearerToken(req))) {
    res.writeHead(401);
    return res.end(JSON.stringify({ error: "AUTHENTICATION_REQUIRED", message: "سجّل الدخول إلى مساحة الحسام قبل إرسال الرسائل." }));
  }
  if (!allowRate("chat:" + clientAddress(req), 20, 60_000)) {
    res.writeHead(429);
    return res.end(JSON.stringify({ error: "CHAT_RATE_LIMITED", message: "تم بلوغ حد الطلبات المؤقت لهذه الخدمة." }));
  }
  if (active.provider === "none") {
    res.writeHead(503);
    return res.end(JSON.stringify({
      error: "INFERENCE_NOT_CONFIGURED",
      message: "الخادم يعمل، لكن لم يُضبط اعتماد صالح لمزوّد الاستدلال. لم يتم توليد رد."
    }));
  }

  // Bound uploads separately from model generations. Slow clients must not occupy
  // scarce inference slots; reserve the generation slot only after a full valid body.
  if (activeUploads >= 8) {
    res.writeHead(429);
    return res.end(JSON.stringify({ error: "UPLOAD_CONCURRENCY_LIMITED", message: "هناك عدد كبير من الطلبات الواردة؛ أعد المحاولة بعد قليل." }));
  }
  activeUploads += 1;
  let raw = "";
  try {
    for await (const chunk of req) {
      raw += chunk;
      if (raw.length > 100_000) {
        activeUploads = Math.max(0, activeUploads - 1);
        res.writeHead(413);
        return res.end(JSON.stringify({ error: "REQUEST_TOO_LARGE" }));
      }
    }
  } catch {
    activeUploads = Math.max(0, activeUploads - 1);
    if (!res.headersSent) {
      res.writeHead(400);
      return res.end(JSON.stringify({ error: "REQUEST_BODY_INTERRUPTED" }));
    }
    return;
  }
  activeUploads = Math.max(0, activeUploads - 1);
  let body;
  try { body = JSON.parse(raw || "{}"); } catch {
    res.writeHead(400);
    return res.end(JSON.stringify({ error: "INVALID_JSON" }));
  }
  if (!validMessages(body.messages)) {
    res.writeHead(400);
    return res.end(JSON.stringify({ error: "INVALID_MESSAGES" }));
  }
  // No await between this final check and reservation, so the cap is atomic
  // within this Node event loop and only actual generations consume these slots.
  if (activeGenerations >= 2) {
    res.writeHead(429);
    return res.end(JSON.stringify({ error: "INFERENCE_CONCURRENCY_LIMITED", message: "الخدمة مشغولة بطلبات أخرى؛ لم يُرسل هذا الطلب إلى المزود." }));
  }
  activeGenerations += 1;

  try {
    const generated = active.provider === "gemini"
      ? await generateWithGemini(body.messages, active.model)
      : { answer: await generateWithOpenAI(body.messages, active.model), model: active.model };
    activeGenerations -= 1;
    res.writeHead(200);
    return res.end(JSON.stringify({
      answer: generated.answer,
      provider: active.provider,
      model: generated.model,
      truth: "VERIFIED_RESPONSE"
    }));
  } catch (error) {
    activeGenerations = Math.max(0, activeGenerations - 1);
    // Log only sanitized upstream diagnostics; never log API keys, headers, prompts, or provider response bodies.
    console.warn("Inference upstream failure", JSON.stringify({
      provider: active.provider,
      model: error?.model || active.model,
      status: Number.isInteger(error?.status) ? error.status : null,
      providerStatus: typeof error?.providerStatus === "string" ? error.providerStatus : null,
      providerMessage: typeof error?.providerMessage === "string" ? error.providerMessage : null,
      errorName: typeof error?.name === "string" ? error.name : "Error",
      errorCode: typeof error?.cause?.code === "string" ? error.cause.code : null,
      timedOut: error?.name === "TimeoutError"
    }));
    const upstreamStatus = Number.isInteger(error?.status) ? error.status : null;
    const isTimeout = error?.name === "TimeoutError";
    const isRateLimited = upstreamStatus === 429;
    const isUnavailable = upstreamStatus === 503 || error?.providerStatus === "UNAVAILABLE";
    const isAuthFailure = upstreamStatus === 401 || upstreamStatus === 403;
    const isModelUnavailable = upstreamStatus === 404;
    const status = isTimeout ? 504 : isRateLimited ? 429 : isUnavailable ? 503 : 502;
    const code = error?.message === "EMPTY_MODEL_RESPONSE"
      ? "EMPTY_MODEL_RESPONSE"
      : isTimeout
        ? "PROVIDER_TIMEOUT"
        : isRateLimited
          ? "PROVIDER_QUOTA_OR_RATE_LIMIT"
        : isUnavailable
          ? "PROVIDER_TEMPORARILY_UNAVAILABLE"
          : isAuthFailure
            ? "PROVIDER_AUTHENTICATION_FAILED"
            : isModelUnavailable
              ? "PROVIDER_MODEL_UNAVAILABLE"
              : "INFERENCE_CONNECTION_FAILED";
    const message = isTimeout
      ? "انتهت مهلة انتظار مزوّد الاستدلال قبل وصول رد. لم يُنتج رد؛ يلزم فحص اتصال الخدمة بالمزوّد."
      : isRateLimited
        ? "رفض مزوّد الاستدلال الطلب بسبب الحصة أو حد المعدل. لم يُنتج رد."
      : isUnavailable
        ? "مزوّد الاستدلال غير متاح مؤقتًا. لم يُنتج رد؛ حاول لاحقًا."
        : isAuthFailure
          ? "رفض مزوّد الاستدلال بيانات الاعتماد. راجع إعداد المفتاح في الخادم دون مشاركته."
          : isModelUnavailable
            ? "النموذج المحدد غير متاح لدى المزوّد. راجع اسم النموذج وإتاحته."
            : "تعذر إكمال طلب الاستدلال. لم يُنتج رد.";
    res.writeHead(status);
    return res.end(JSON.stringify({ error: code, message }));
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`Hussam AI inference bridge listening on ${PORT}`);
});
