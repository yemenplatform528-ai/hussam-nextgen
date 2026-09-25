# Phase 2 — Production Certification Runbook

## Rule

Phase 2 is **external certification**, not another engineering rebuild.
A gate closes only from real, attributable evidence for the exact release SHA.
Configuration, unit tests, mocks, screenshots, public provider capability pages,
or developer-declared PASS do not close a gate.

## G01 Identity / OIDC
Requires a real IdP tenant/client, exact redirect URI, secret injection, real
browser login/callback/session/tenant authorization/logout/refresh, and a
sanitized evidence artifact. Do not commit client secrets.

## G02 PostgreSQL / Migration / Restore
Requires a real PostgreSQL target and a distinct restore target. Execute the
repository backup/restore drill, record backup size/time, restore time, measured
RPO/RTO, Alembic revision, integrity checks, and artifact hash.

## G03 Payments
Select a provider/rail only after commercial, regulatory, technical and
operational ownership is established. Public capability is discovery evidence,
not certification. Execute a real controlled payment, signed webhook, duplicate
delivery/idempotency test, reconciliation and settlement evidence.

Current public discovery confirms that Kuraimi exposes Haseb e-commerce payment
and Kuraimi Jawal/MFloos channels; Jawali and Yemen Wallet also publish
purchase/payment capabilities. None of these public pages is treated as
Hussam certification. Certification still requires a real agreement/account,
technical interface, credentials, webhook and reconciliation evidence.

## G04 Accounting
Use Hussam Finance as the authoritative ledger. Execute the real order →
payment/COD → journal → settlement → reversal → reconciliation → audit chain.
External accounting software is optional and never becomes the core authority.

## G05 Logistics
Use one real carrier path suitable for the launch market. Prove shipment
creation, signed tracking events, lifecycle transitions, delivery, COD
collection and settlement/reconciliation. Carrier choice remains an adapter.

## G06 Browser / Mobile
Run production-like desktop and mobile journeys against the exact release
candidate, including identity, tenant boundary, marketplace checkout,
payment/COD, fulfillment and customer-visible completion.

## G07 Security
Collect real deployment evidence: HTTPS/security headers, distributed
rate-limit behavior, dependency/image scans, secret exposure checks, and an
appropriate security assessment. Do not substitute unit tests for deployment
evidence.

## G08 DR / Observability
Execute backup → restore → measured RPO/RTO → metrics → alert → induced failure
→ recovery. Keep the restore target separate from production.

## G09 Operations
Name the actual operational owner, escalation path and rollback target. Execute
a real deployment/rollback and incident drill and preserve the evidence.

## G10 Legal / Compliance
Engineering templates are ready for review, not legal approval. Obtain
approval for the actual operating entity, market, consumer/seller terms,
privacy/retention, payments/COD, returns/disputes, IP, prohibited goods and
other applicable requirements.

## Evidence contract

Each envelope must contain:
- gate key;
- exact release SHA;
- environment;
- source/owner;
- performed_at;
- PASS result;
- non-empty checks;
- reviewer;
- artifact path;
- artifact SHA-256.

The phase-2 validator is fail-closed and returns non-zero unless all ten gates
are CLOSED.

## Current boundary

Phase 2 cannot truthfully be marked 10/10 until the real external credentials,
accounts, environments, provider/carrier contracts, operational ownership and
legal approval are available. The project must not fabricate these inputs.
