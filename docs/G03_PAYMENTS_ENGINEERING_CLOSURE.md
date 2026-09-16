# G03 — Payments + Signed Webhooks + Reconciliation

## Status

**ENGINEERING_READY — PRODUCTION CERTIFICATION PENDING_EXTERNAL**

This document records engineering closure only. It does not claim that a real payment provider, real signed webhook, real settlement file, or production reconciliation run has been completed.

## Implemented controls

- Tenant-scoped payment intents with positive decimal amounts and unique references.
- Provider payment IDs are tenant/provider scoped and immutable after assignment.
- Signed webhook verification using HMAC-SHA256 over `timestamp.raw_body`.
- Five-minute replay protection for signed webhooks.
- Constant-time signature comparison.
- Webhook idempotency using `(tenant_id, provider, event_id)`.
- Provider and tenant consistency checks.
- Monotonic payment lifecycle protections.
- Capture only after provider payment identity is attached and authorized/processing state is present.
- Settlement requires exact amount and currency match.
- Refund lifecycle with cumulative refund cap and provider refund identity.
- Reconciliation records distinguish `matched`, `amount_mismatch`, `currency_mismatch`, and `unknown`.
- Accounting postings remain authoritative inside the existing finance engine.
- Payment events are emitted through the outbox boundary.

## External evidence still required

1. Real payment provider account/configuration in a controlled staging or production-like environment.
2. Secret-manager injection for the provider webhook secret; no raw secret in evidence.
3. Real provider payment creation/authorization/capture.
4. Real signed webhook delivery, including replay/tamper rejection.
5. Real settlement artifact and successful reconciliation.
6. Real refund request/completion where supported.
7. External artifacts with SHA-256 and reviewer decision.
8. Evidence protocol validation before G03 can be marked `CLOSED`.

## Security boundary

`/api/v1/payments/webhooks/signed` is the provider-facing signed webhook boundary. The request body includes the tenant routing identity and is authenticated by the provider-specific tenant secret. The production secret must be injected by a secret manager; the environment JSON mapping is an engineering/test configuration contract and is not itself production evidence.
