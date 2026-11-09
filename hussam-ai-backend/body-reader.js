export async function readRequestBody(req, maxBytes, timeoutCode = "REQUEST_BODY_TIMEOUT") {
  const chunks = [];
  let size = 0;
  let bodyTimeout;
  try {
    const bodyRead = (async () => {
      for await (const chunk of req) {
        const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        size += buffer.length;
        if (size > maxBytes) {
          const error = new Error("REQUEST_TOO_LARGE");
          error.code = "REQUEST_TOO_LARGE";
          throw error;
        }
        chunks.push(buffer);
      }
    })();
    const deadline = new Promise((_, reject) => {
      bodyTimeout = setTimeout(() => {
        const error = new Error(timeoutCode);
        error.code = timeoutCode;
        reject(error);
      }, Math.max(100, Number(process.env.HUSSAM_REQUEST_BODY_TIMEOUT_MS) || 15_000));
      bodyTimeout.unref?.();
    });
    await Promise.race([bodyRead, deadline]);
    return Buffer.concat(chunks, size).toString("utf8");
  } finally {
    if (bodyTimeout) clearTimeout(bodyTimeout);
  }
}
