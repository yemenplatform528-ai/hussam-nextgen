# Hussam NextGen — Phase 2 External Dependency Activation Map
## 2026-09-25

## Decision
The previously agreed architecture is sufficient to complete external certification without reopening Sovereign Core, Marketplace, AI, HUS, Finance, or Yemen capability composition.
Phase 2 is an activation and evidence phase, not a second architecture phase.
Core authority stays fixed → external service is attached through the existing governed boundary → real execution occurs → evidence is bound to the exact release SHA → gate closes.

## G01 — Identity / OIDC
Existing solution: provider-neutral OIDC authorization-code boundary with discovery, state + nonce, signed short-lived state, code exchange, ID-token validation, issuer/subject binding, tenant authorization, HttpOnly session and logout.
Activation: select the real IdP outside the core; register the exact client and redirect URI; inject the secret through the deployment secret mechanism; execute real browser login/callback/session/logout; preserve tenant authorization evidence.
Changing the IdP must not require a core rewrite.

## G02 — PostgreSQL / Restore
Existing solution: PostgreSQL production contract, Alembic chain, readiness, and isolated backup/restore drill.
Activation topology: production/staging database → backup artifact → isolated restore target → application smoke/integrity verification.
Required evidence: starting revision, deployed head, backup artifact, restore target, restore duration, measured RPO/RTO, integrity result, artifact SHA-256 and reviewer.

## G03 — Real Payment
Existing solution: ProviderRegistryEntry → ProviderMarketCapability → PaymentRailRegistryEntry → PaymentAdapterRegistryEntry → payment service.
Activation: attach a real provider through the registry and provider-specific adapter boundary. Credentials remain external secret references.
Required real proof: identity/licensing, capability, Yemen market/currency, commercial basis, technical interface, authentication, signed webhook, idempotency, settlement/reconciliation, certification and operational owner, followed by a controlled real transaction.
Hussam Finance remains the authoritative ledger.

## G04 — Accounting
Existing solution: Finance/Ledger remains authoritative.
Activation proof: real order → payment/COD → journal → settlement → reversal/refund where applicable → reconciliation → audit.
No second accounting engine is introduced.

## G05 — Logistics
Existing solution: shipment creation, carrier, tracking, lifecycle transitions, COD amount and COD collection already belong to the logistics authority.
Activation: select a real carrier as an adapter.
Required proof: shipment creation, tracking identifier, lifecycle events, delivery, COD amount, collection, settlement/reconciliation and retry/failure behavior.

## G06 — Browser / Mobile
Use the existing Yemen Cross-Capability E2E contract against the real environment: Market → Geography → Catalog → Cart → Checkout → Payment/COD → Order → Fulfillment → Delivery/Collection → Readback.
Desktop and mobile evidence must refer to the same release SHA.

## G07 — Security
Attach real deployment evidence: dependency scan, image/container scan where applicable, secret scan, HTTPS/security headers, distributed rate-limit behavior and an appropriate external security assessment.
Unit tests do not substitute for deployment evidence.

## G08 — DR / Observability
Execute real backup, isolated restore, measured RPO/RTO, dashboard verification, alert delivery, controlled failure, recovery and post-recovery integrity.

## G09 — Operations
Activate named operational ownership, escalation route, deployment record, rollback target, real rollback execution, incident drill, recovery timing and post-incident record.

## G10 — Legal / Compliance
Use the existing jurisdiction-neutral policy contracts and readiness tooling as engineering templates only. The actual launch-scope policy set must receive human legal/compliance approval.

## Developer Platform rule
The Developer Platform is the long-term path for future providers and local capabilities. It supports configuration, declarative modules, provider adapters and controlled platform-code releases.
Extensions cannot bypass tenant isolation, mutate the authoritative ledger directly, bypass commerce/payment invariants, impersonate providers, or execute arbitrary shell/SQL/network operations from declarative modules.
Each extension carries immutable version, source/package hash, capability declarations, permissions, market/tenant scope, compatibility contract, source-bound test evidence, activation record and rollback target.
After final core lock, adding a Yemen payment rail, carrier, notification provider, business vertical or workflow therefore does not require reopening the immutable core release.

## Boundary
Phase 2 can close engineering-to-production activation contracts, adapter boundaries, capability resolution, evidence validation, provenance binding and the governed Developer Platform path.
Software cannot fabricate a real external IdP account, provider contract/account, carrier account, human legal approval, operational responsibility or real transaction/restore/incident result.
These are external facts required for certification, not architecture gaps.

## Phase 2 completion condition
G01 + G02 + G03 + G04 + G05 + G06 + G07 + G08 + G09 + G10 must all be CLOSED with valid evidence envelopes bound to one exact release SHA.
Only then does Phase 3 perform freeze, provenance verification, final artifact generation, immutable lock, branch cleanup and canonical-reference unification.