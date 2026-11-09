# Hussam AI secure rollout checklist

This checklist is for the owner/operator. Do not paste secrets into Git, issues, chat, CI logs, screenshots, or deployment notes.

## Preconditions

- Review the security change and confirm all required CI checks pass for the exact commit being deployed.
- Confirm the intended Render service is `hussam-ai-inference-bridge` and the static portal origin is `https://hussam-ai-standalone-portal.onrender.com`.
- Keep the existing production deployment available for rollback until browser checks pass.
- Do not enable billing or change provider credentials as part of this rollout without explicit authorization.

## Required server environment

Configure these only in the backend service's secret environment settings, never in the static portal:

- `HUSSAM_ACCESS_PASSWORD`: a newly generated owner-only password with at least 16 characters.
- `HUSSAM_SESSION_SECRET`: a cryptographically random secret with at least 32 characters.
- `ALLOWED_ORIGIN`: `https://hussam-ai-standalone-portal.onrender.com` (exact origin, no trailing slash).
- `HUSSAM_GEMINI_FREE_TIER_ENABLED`: leave unset or set to `false` by default. Set to `true` only after the owner verifies in the provider account that the selected Gemini model is eligible for the free tier and quota is available; a key alone does not prove zero cost.
- `HUSSAM_ALLOW_BILLABLE_AI`: leave unset or set to `false`; OpenAI is disabled by default and may be enabled only after a separate explicit owner approval.
- One already-authorized inference provider credential, if live model responses are expected. Do not create or enable paid billing as part of this step.

Generate a session secret locally with a cryptographic generator such as `openssl rand -base64 48`. Generate/store the owner password with a password manager. Do not print either value in CI logs. Do not reuse a source-control, database, or provider credential as the session secret.

## Session and logout semantics

- The backend issues a signed stateless bearer token with a maximum lifetime of 30 minutes. Login and chat API responses set `Cache-Control: no-store` and `Pragma: no-cache`.
- Browser logout clears the token from the current page's JavaScript memory, hides the protected chat/dashboard, and returns to the login panel. Automatic expiry and any authenticated chat or dashboard-inference response with HTTP 401 do the same.
- This is **local logout, not server-side revocation**. A copied token remains valid until its 30-minute expiry or until the signing secret is rotated. Never claim immediate revocation.
- Chat history is stored in this browser profile's localStorage; it is not encrypted by this application. Local logout does not erase saved history. Anyone with access to the same browser profile may be able to inspect it; export or clear local history before sharing the device.
- Login throttling applies an eight-attempt, 15-minute per-client in-process bucket. There is deliberately no shared global login ceiling: an unauthenticated caller must not be able to consume a global budget and lock the owner out. The per-client key is best-effort only because forwarded IP headers may be caller-controlled and process-local counters are not shared across replicas. Before public production exposure, enforce distributed login rate limits at a trusted edge/WAF that overwrites client-IP metadata, and verify the trust boundary with deployment-specific tests. Do not treat the application bucket as a substitute for that edge control.

## Deploy sequence

1. Apply server environment values before deploying the auth-protected backend. The backend intentionally returns `ACCESS_CONTROL_NOT_CONFIGURED` when the access password or session secret is missing or too short.
2. Deploy the reviewed security branch to the backend only after the required CI checks pass. Keep the static portal and backend origin values aligned.
3. Verify `/health` reports `status: online`, `accessControlConfigured: true`, and the configured provider. `liveModelVerified` remains false until a real generation succeeds.
4. Before public exposure, configure and verify trusted edge/WAF distributed rate limiting for `/api/session/login`; confirm the edge overwrites client-IP metadata and rejects bursts without trusting caller-supplied forwarding headers. In a clean browser session, verify login succeeds only from the exact allowed portal origin, wrong passwords fail, the issued session advertises a 30-minute expiry, and the application per-client throttle returns HTTP 429 for repeated attempts from one client without a shared global lockout.
5. Send one non-sensitive prompt and verify a successful response contains `truth: VERIFIED_RESPONSE`. If the provider reports quota exhaustion or an upstream error, stop; do not repeatedly retry or switch to a paid provider.
6. Verify logged-out users cannot open chat/dashboard or import/export history. Verify the logout button clears the in-memory token and returns to login, and that automatic expiry does the same. A copied token remains valid until its 30-minute expiry or signing-secret rotation; this is not immediate revocation. Verify reloading the page requires login again. Verify a disallowed origin receives HTTP 403 and a missing/invalid/expired bearer token receives HTTP 401.
7. Check sanitized service logs for errors without exposing prompts, tokens, passwords, provider keys, or response bodies.
8. If any required check fails, roll back the backend to the previous deployment and remove/rotate any exposed secret. Do not claim the assistant is live until the real generation check passes.

## Truth states

- `OBSERVED`: the health endpoint responded.
- `accessControlConfigured: true`: required auth settings exist; this does not prove the browser login flow works.
- `VERIFIED_RESPONSE`: a provider returned a non-empty answer to a real chat request.
- Production rollout is not complete until the browser, origin, authentication, and real-generation checks above pass.
