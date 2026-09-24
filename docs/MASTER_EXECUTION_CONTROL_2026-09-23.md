# Hussam NextGen — Master Execution Control
## Controlled project state — 2026-09-24

### Authority
This document is the execution-control companion to the canonical engineering baseline. It does not replace source code, release manifests, or external certification evidence.

### Current source of truth
- Repository: `yemenplatform528-ai/hussam-nextgen`
- Default branch: `main`
- Current `main`: latest controlled commit on the default branch; this document is updated as part of the controlled merge history.
- Canonical engineering baseline remains: `473cb7785bf2853e884a3ed28ea17f18d5085efa`
- Certification-control delta remains separate from additive Yemenization/Developer Platform BUILD work.
- Marketplace, AI, HUS, finance and sovereign-core business behavior remain protected; Yemenization is implemented as governed compatibility/configuration layers rather than a parallel core.

### Verified engineering boundary
The latest CI before the migration-chain repair failed for one structural reason: two Alembic heads existed (`0030_platform_capability_registry` and `0030_yemen_market_operating_profile`). The failure occurred in the baseline audit and PostgreSQL migration job before the substantive test suite could run.
- Container-security for the affected run: SUCCESS.
- External runtime smoke for `71fe8bccfe72a036e91e7ef876f850c5ec6d8629`: SUCCESS (run `35927577864`).
- External readiness workflow for `71fe8bccfe72a036e91e7ef876f850c5ec6d8629`: SUCCESS (run `35927577911`).
- The migration-chain repair is now committed as `24e920917be944e3a9bc4b37d5010c41c4c147ce`, changing the capability registry revision to `0031_platform_capability_registry` and chaining it after `0030_yemen_market_operating_profile`.
- No green CI claim is made for `24e920917be944e3a9bc4b37d5010c41c4c147ce` until GitHub runs for that commit are actually observed.

### External readiness boundary
- FastAPI Cloud staging: `https://hussam-nextgen.fastapicloud.dev/`
- Neon staging resource: `hussam-nextgen-staging` — user-confirmed attached to FastAPI Cloud.
- Repository-owned readiness workflow remains separate from engineering CI.
- Public `/ready` remains fail-closed and its evidence boundary remains blocked by the previously observed Cloudflare 1010 access-control result.
- G01–G10 remain PENDING_EXTERNAL.

### Yemenization execution map
Yemenization is an active cross-system BUILD track. The full-system contract is `docs/YEMEN_PLATFORM_SYSTEM_ALIGNMENT_2026-09-24.md`. The internal developer extension contract is `docs/DEVELOPER_PLATFORM_PRODUCT_CONTRACT_2026-09-24.md`.

Current implemented control-plane sequence:
1. Developer Platform extension lifecycle and rollback.
2. Governed Yemen capability registry.
3. Migration chain repaired so the repository has one Alembic head.
4. Capability service/market activation bridge is now implemented and covered by service tests.
5. Next: wire activated capabilities into existing money, geography, payments, logistics, connectivity, documents, notifications, AI/HUS and UI response boundaries without duplicating authoritative engines.
6. Keep G01–G10 certification independent.

### Free-first constraint
Prefer free capabilities. No paid subscription, trial, credit purchase, or paid infrastructure is a prerequisite for the next engineering step unless a concrete external certification requirement makes it unavoidable.

### Release discipline
The project is not production-ready until all applicable external gates have real evidence envelopes, artifact hashes match, rollback is prepared, and the final release/audit lock is explicitly recorded.


## 2026-09-24 Capability Service Layer Checkpoint

- Added `app/core/services/capabilities.py` as the application boundary for capability discovery, registration validation, market-scope invariants, market activation lookup, and active-for-market checks.
- Developer Platform market-capability listing now delegates activation queries to the service layer; the activation endpoint already delegates capability discovery and scope validation to the same service.
- Added service-level coverage for registration, market scope, activation state, and market activation listing.
- The migration fix at `5f67986a456d106d82dde23952fe7e6e92138455` made `0032_market_capability_activation` idempotent after CI observed the activation table already present during migration.
- Subsequent implementation commits: `1be87feca44662e1dafe60e363a056bb343e7e9b`, `1d67cdbdff3bd01a76adf2c471921524bb303125`, `53c278662c9dc1dfcdef59f5bf24154225ee7078`.
- CI for `fbcd93224e981c4a965fdc4ef56a715ba61c3dba` is verified green: repository CI run `35929150853`, External Runtime Smoke `35929150800`, and External Readiness Certification `35929150899` all completed successfully.
- The runtime-context commits after that verified checkpoint are `706baaae51f8cae6acaa8be8b6a52d37cd4aaa46`, `e41ef77f1fa48044711928551e6dc527b3010c6d`, `92d26d7c51fd622288f6bfb80a39ac3176d845af`, and `e82d8364c4452d42d78cc488f3fa5b99ba8e8a16`; their workflow results remain to be observed.


## 2026-09-24 Market Runtime Context Checkpoint

- Added `MarketContextService` as the composition boundary for one governed market runtime context.
- The runtime context now composes existing authoritative data for:
  - market identity and configuration;
  - market currencies and cash/electronic support;
  - active market money units;
  - operational geography coverage;
  - active governed Yemen capability configurations.
- Extended `GET /api/v1/developer/market-context/{market_code}` to use this service instead of assembling capability-only data inside the route.
- Added persistence coverage for the complete runtime-context composition.
- No new financial engine, FX engine, geography engine, payment provider, or logistics engine was introduced.
- This is the first concrete wiring layer from the capability control plane into existing market/money/geography boundaries.


## 2026-09-24 Market Runtime Context — Payment Boundary

- Extended the governed runtime context with active market payment-method catalog entries.
- Payment methods are exposed as market configuration metadata only; provider execution, payment state transitions, settlement, and ledger behavior remain owned by the existing payment/finance domains.
- Added test coverage for a provider-free COD method in the composed market context.
- Latest engineering commit: `4b231f93bbb295b4745d08438f17f5899105ca4c`.


## 2026-09-24 CI Correction

- CI run `35929605196` exposed one test-fixture regression: the new market payment-context test referenced `payment_method` before defining it.
- Baseline audit and compileall remained clean; 370 tests passed and 1 failed.
- Corrected the fixture in `c07e107db0b63da479d4df7a781f19f429497b23`.
- The failure was test-only and did not indicate a production-domain defect.


## 2026-09-24 Governed Delivery + Connectivity Context Checkpoint

- The latest CI correction exposed a second fixture issue: the market-geography integrity contract requires every non-country geography node to have a parent. The test fixture now creates a Yemen country node and makes Taiz governorate a child of it.
- Correction commit: `da4db46d56de1c5780123e69e75631c49dcbedb4`.
- Added governed delivery and connectivity runtime sections to MarketContextService using existing capability activations only; no duplicate logistics or connectivity engine was introduced.
- Delivery configuration is sourced from active `yem_delivery_modes`; connectivity policy is sourced from active `yem_connectivity_policy`. Suspended or absent capabilities produce an empty configuration rather than silently enabling behavior.
- Added executable coverage for pickup/local/inter-city delivery modes and offline-draft/idempotent-mutation/pending-state policy metadata.
- Latest implementation commit: `d083a58f58daafb2612abb970332ae8b7851d7d9`; latest test commit: `67d5916f917fc29a8ad49f0c04161ae93cf5327e`.
- CI for `da4db46d56de1c5780123e69e75631c49dcbedb4` was observed queued; the latest `67d5916f917fc29a8ad49f0c04161ae93cf5327e` workflow runs had not yet appeared when this checkpoint was written. No green claim is made until runs are observed.


## 2026-09-24 Full-System Runtime Context — Documents / Notifications / AI-HUS

- Extended MarketContextService without creating parallel engines.
- Documents now receive governed market configuration plus the existing immutable/versioned business-document lifecycle metadata.
- Notifications now receive governed market channel configuration while remaining tenant-scoped and owned by the existing notification domain.
- AI/HUS now receive a reusable Yemen market context envelope (market, country, locale, timezone, default currency) plus governed policy metadata; this does not grant AI execution authority and does not replace HUS/domain contracts.
- Added executable coverage for Arabic-first document configuration, SMS/WhatsApp/in-app channel configuration, and Yemen AI/HUS context/governance metadata.
- Implementation commit: `fda59b421942ba57086a42f4ff322d7597d8b33e`.
- Test commit: `f5a923642e229ca9258eaa0d6433355f5de1c5b8`.
- GitHub workflow evidence for `bdb21ddebb74e8c0950b741cd872621ce44a2c05` is currently empty through the connected workflow-run query; therefore no green CI claim is made for this branch yet.
- Next controlled slice: expose this runtime context through deterministic client-facing response contracts, then verify CI before considering promotion toward `main`.


## 2026-09-24 Deep System Audit + Client Context Boundary

- Completed a repository-wide architecture inventory against the committed release manifest, API routes, models, engines, AI/HUS stack, migrations, tests, Yemenization contracts, Developer Platform contract and production gates.
- Added `docs/MASTER_SYSTEM_AUDIT_2026-09-24.md` as the current engineering study/control reference.
- Confirmed the existing platform already contains sovereign/core, finance, inventory, commerce, procurement, payments, logistics, documents, workflow, marketplace, AI and HUS authorities; Yemenization must compose them rather than replace them.
- Confirmed the committed `release-manifest.json` is a provenance snapshot and is not safe to treat as the final hash manifest for the newer Yemenization stream. Formal release locking must regenerate it from the exact repository state.
- Added tenant-authenticated `GET /api/v1/platform/market-context/{market_code}` as a stable client-facing contract.
- The client contract deliberately excludes owner/admin control-plane metadata and raw capability configuration while exposing the market, money, payment, geography, delivery, connectivity, documents, notifications, AI/HUS and active-capability state required by clients.
- Added executable tests for stable schema version, market activation, tenant-safe exposure and control-plane secret/configuration exclusion.
- Client route commit: `1bb6ee9451f9a3d1ad37c2429071ccce461f8493`.
- API registration commit: `252b9702dbe8664af8b71a830dc2d6c659e82ac4`.
- Client contract tests commit: `001464ee72a85300b1be00294337512fb02ea32f`.
- Next gate is CI verification on the resulting branch head before any promotion or merge decision.


## 2026-09-24 execution checkpoint — Developer evidence hardening
- Client market-context projection was hardened to an allow-listed contract; raw control-plane configuration and provider/internal metadata are excluded.
- Added executable secret-boundary coverage for the client runtime context.
- Developer Platform version creation now keeps test status server-controlled at `pending`; `passed` requires immutable test evidence fields: evidence hash, test-run identifier and timestamp.
- Added migration `0033_developer_test_evidence` and executable persistence coverage.
- CI run #108 for the preceding Yemen runtime-context slice completed successfully: baseline audit, compile, PostgreSQL migration/schema drift/integration and container-security all passed; the full baseline test job completed successfully in that run.
- The latest evidence-hardening commits are on PR #22 and require a fresh CI execution before merge. No production certification claim is made.


## 2026-09-24 execution checkpoint — migration convergence + verified CI
- Migration `0033_developer_test_evidence` was hardened to converge safely when test/dev schemas already contain the new columns, and to add the invariant correctly on both SQLite and PostgreSQL.
- CI run #113 exposed the duplicate-column migration defect; it was corrected rather than suppressed.
- CI run #114 then passed all baseline, PostgreSQL and container-security jobs.
- The temporary attempt to consume market runtime context directly in the existing browser UI exposed a pre-existing-style browser contract sensitivity; the UI files and E2E fixture were restored to their known-good tree, while the stable backend client contract remains in place.
- CI run #123 on branch head `b6b231ce5384ebe9b3eb9ed5d51a9f4a35a8bef8` passed: 375 tests including browser E2E, fresh SQLite migration/schema drift, PostgreSQL migration/schema drift/integration, baseline audit, dependency checks and container scan.
- Current decision: do not merge or lock the release yet. First complete the remaining Yemen runtime behavior wiring and Developer Platform evidence trust boundary, then regenerate release provenance and run the final exact-head CI.

- Developer test evidence is now immutable after the first recorded result; a failed evidence record cannot be promoted to passed evidence through the same endpoint.


## 2026-09-24 execution checkpoint — connectivity-safe checkout

- PR #28 `feat(yemen): make checkout connectivity-safe and replay-safe` was merged after its final CI run #165 completed successfully.
- Final PR head: `e24e4802956a547f94e9eb720cdc5e3e59d94df6`.
- Merge commit on `main`: `8339d0aba01367049c1ac243e68abaf93ac5bdc5`.
- The slice uses the existing `IdempotencyRecord` table; no schema migration was needed.
- Checkout idempotency is atomic with order creation: reservation, domain mutation and stored replay result share the same transaction.
- The request hash binds the authenticated buyer to the canonical checkout body; reusing a key for a different request is rejected.
- Browser checkout now has an explicit local draft boundary. Offline submission does not call the checkout API and the saved draft is explicitly not an order.
- Online retry reuses the same idempotency key, protecting against the common case where a server-side mutation succeeds but the client loses the response.
- Final PR CI evidence: baseline, PostgreSQL integration and container-security all passed.
- The previously open verification-only PR #21 was closed as obsolete; it was not merged.
- Post-merge `main` CI is not claimed here because the connected workflow query did not report a push-triggered run for merge commit `8339d0aba01367049c1ac243e68abaf93ac5bdc5`.
- G01–G10 remain `PENDING_EXTERNAL`. This checkpoint is engineering behavior evidence, not production certification.

### Next controlled track

Continue with the broader connectivity contract only after the checkout mutation boundary is stable:

1. offline-safe read/cache boundaries;
2. explicit mutation lifecycle states (`DRAFT`, `PENDING`, `CONFIRMED`, `FAILED`, `CONFLICT`);
3. replay and conflict proof for non-payment mutations;
4. sync/audit proof;
5. prohibition of offline financial authority;
6. then move through Documents → Notifications → Search/Pricing/CRM → AI/HUS context verification → Developer Platform trust/provenance hardening → full Yemen E2E → external G01–G10 → final release lock.
