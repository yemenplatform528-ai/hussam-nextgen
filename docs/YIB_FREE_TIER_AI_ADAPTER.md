# YIB/WORLD free-tier model adapter: setup and verification

## What changed

The independent Node runtime now supports Google's Gemini Developer API as an optional provider. The adapter is deliberately **off by default**. It does not make a model live merely because a key exists, and the status endpoint reports `liveModelVerified: false` until an actual generation request succeeds.

Default model: `gemini-2.5-flash-lite`. Google lists text input/output for this model on its free tier; quotas and availability can change. See the [official Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing) and [model page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite).

## Required runtime environment

Set these variables in the hosting provider's private environment settings, never in source control:

- `GEMINI_API_KEY`: a private API key created in Google AI Studio.
- `YIB_GEMINI_FREE_TIER_ENABLED=true`: explicit opt-in to the Gemini adapter.
- Optional `GEMINI_MODEL`: defaults to `gemini-2.5-flash-lite`.

Paid OpenAI generation remains disabled unless `YIB_ALLOW_BILLABLE_AI=true`; do **not** enable that setting for a zero-cost deployment.

**Zero-cost guardrail:** a free-tier price label is not a universal guarantee against charges if a provider project has billing enabled or its terms change. Use a provider project with billing disabled and verify its quota/billing settings before putting a key into production. This runtime does not have access to the provider account's billing configuration and cannot verify it on your behalf. Never commit or paste the key into chat, GitHub, or this repository. Gemini free-tier data-use terms may permit provider use of submitted content to improve products; do not send sensitive personal data.

## Verification protocol

After configuring the private environment, redeploy the branch and check:

1. `GET /api/health` — should report `provider: "GEMINI"`, `modelConfigured: true`, and `liveModelVerified: false` until generation has been tested.
2. Authenticated `GET /api/provider/check` — checks model metadata only; it does **not** prove text generation works.
3. Send an ordinary test message through the authenticated `POST /api/chat` route. A non-empty successful provider response is the first evidence of live generation; inspect the returned `model` and `truth: "VERIFIED"`.
4. Repeat with a nonsense/Arabic question, then refresh and confirm the user message and answer remain in chat history.
5. Test a bad/expired key in a staging environment only; expect an explicit provider error, never a fabricated AI answer.
6. Check `GET /api/provider` again. Its current `liveModelVerified` flag is intentionally conservative and remains false; a successful chat response is the evidence of generation, not this metadata endpoint.

## Truth and limitations

- Code support added: `OBSERVED` in source control.
- Deployment of this branch: **not verified** by this document.
- Secret configured: **unknown** until checked in hosting settings.
- Live generation: **not verified** until a real request succeeds.
- Durable storage, restore, authentication and export still require independent runtime tests.
- This adapter is text generation, not autonomous access to external tools. Tool execution and external side effects remain separate capabilities and must fail closed.
