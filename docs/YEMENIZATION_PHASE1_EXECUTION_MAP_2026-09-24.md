# BUILD Phase 1 — Yemenization Execution Map
## Controlled implementation map — 2026-09-24

**Status:** ACTIVE BUILD PREPARATION / NON-BLOCKING CERTIFICATION  
**Purpose:** consolidate the existing Yemen Foundation, production-layer safeguards, payment evidence boundary, and market research into one execution map without mutating the certified core.

## 1. Existing foundation already present

Hussam already contains the reusable market primitives required for Phase 1:

- `MarketContext`
- `MarketCurrency`
- `MarketGeography`
- `MarketCoverage`
- `MarketMoneyUnit`
- `MarketExchangeRate`
- `ProviderRegistryEntry`
- `ProviderMarketCapability`
- `PaymentRailRegistryEntry`
- `PaymentAdapterRegistryEntry`
- `MarketReadinessEvidence`
- `PaymentMethodCatalogEntry`

The model boundary is deliberately market-scoped and provider-neutral. Yemen-specific behavior is data/configuration/adapters, not a second sovereign core.

## 2. Existing safety boundaries

### Geography

The repository already has:

- a provenance-first geography source review;
- a reviewed-artifact acceptance gate;
- a fail-closed importer;
- dry-run as the default;
- explicit `--apply` for mutation;
- SHA-256/source/license/retrieval metadata requirements;
- hierarchy validation for country → governorate → district → locality.

No national Yemen geography dataset is promoted merely because it is publicly available.

### Currency and FX

The foundation already separates:

- ISO currency identity;
- market money-unit variants;
- market/geography-scoped FX observations;
- FX source provenance and effective time.

No hard-coded national FX rate is permitted.

### Payments

The payment architecture already separates:

1. provider catalog;
2. market capability;
3. payment rail;
4. adapter;
5. certification/production status.

Public provider documentation is not treated as integration certification. Production activation remains fail-closed until legal, commercial, technical, credential, webhook, settlement, reconciliation, testing and operational evidence exist.

### Delivery

Market coverage and geography are already modeled. Phase 1 delivery work should therefore extend capability/zone semantics rather than introduce a second logistics model.

### Evidence

`MarketReadinessEvidence` and the production evidence protocol provide a common provenance/acceptance boundary. Research must not silently become production configuration.

## 3. Phase 1 target architecture

The Yemen layer should converge on these controlled capabilities across the whole platform, not only Marketplace:

1. **MarketContext** — market identity, locale, timezone, default currency and lifecycle.
2. **YemenGeography** — reviewed administrative hierarchy and locality metadata.
3. **CurrencyContext** — YER display rules, money-unit variants and sourced FX observations.
4. **PaymentCapability** — customer-visible payment methods backed by certified provider/rail capability.
5. **DeliveryCapability** — coverage and delivery zones tied to geography and operational capability.
6. **SellerLocalization** — seller-facing local requirements and service-area configuration.
7. **BuyerLocalization** — locality-aware discovery, checkout and address capture.
8. **LocalSearch/Discovery** — geography/category/provider-aware discovery without hard-coding one provider.
9. **ConnectivityAwareUX** — graceful degradation for weak/intermittent connectivity.
10. **Evidence/ProviderCertification** — every externally sourced activation remains reviewable and auditable.

## 4. Implementation order

The implementation sequence is additive and cross-system. External certification remains a separate release-control boundary; BUILD work may proceed without claiming certification closure.

### P1 — Geography admission
- acquire exact canonical artifact;
- preserve original bytes;
- verify license/provenance;
- hash artifact;
- dry-run importer;
- independent structural/P-code comparison;
- acceptance report;
- only then apply.

### P2 — Currency/display contract
- define YER display and rounding rules;
- define money-unit presentation without inventing legal-tender semantics;
- define FX observation freshness/source policy;
- define market/geography scope;
- add UI/API contract tests before enabling behavior.

### P3 — Delivery zones
- map operational coverage to reviewed geography;
- define pickup/service-area/delivery-zone semantics;
- keep carrier/provider execution behind capability adapters;
- fail closed when a route/capability is unknown.

### P4 — Payment capability activation
- keep COD as a method only where the operational service supports it;
- activate digital methods only after provider certification;
- expose capability, not provider implementation details, to the buyer;
- preserve idempotency/reconciliation invariants.

### P5 — Buyer/seller localization
- progressive address capture;
- local-language labels;
- locality-first discovery;
- seller service-area configuration;
- transparent unavailable payment/delivery states.

### P6 — Connectivity-aware UX
- cache safe read-only catalog/context data;
- avoid duplicate order/payment submission;
- make pending states explicit;
- retry idempotent operations only;
- never hide payment/order uncertainty.

### P7 — Final Yemen market release
- run the full regression suite;
- run browser/mobile evidence;
- re-run security and operational evidence;
- update release manifest;
- record reviewed source hashes;
- perform final release/audit lock.

## 5. What remains prohibited

Until the certification/release boundary is crossed:

- no production Yemen dataset import;
- no live payment credentials;
- no provider marked certified from public marketing;
- no carrier contract assumed;
- no hard-coded FX;
- no Marketplace/AI/HUS rewrite;
- no new Yemen-specific runtime fork;
- no closure of G01–G10 from research or configuration screenshots.

## 6. Current decision

The repository already contains most of the structural foundation required for BUILD Phase 1. The next work is therefore **not another foundation rewrite**. It is full-system Yemen compatibility, capability activation, connectivity-aware UX, integration adapters and the Developer Platform that lets internal developers add future capabilities from inside Hussam.

This map is a planning/control artifact. It does not authorize production activation by itself.


## 7. Research update — payment architecture boundary (2026-09-24)

Current Central Bank of Yemen material confirms that Yemen's payment environment is actively evolving: the regulator publishes rules for electronic-money services and payment-system providers, and in 2026 it reported continued work around the unified money-transfer network and digital-payment infrastructure. cite-source:turn0search0turn0search2turn0search7

This strengthens the architecture decision already made in Hussam:

- Hussam must integrate through certified capability adapters rather than hard-code one payment provider.
- The buyer-facing layer should expose available payment capabilities, while provider-specific routing remains behind the adapter boundary.
- Regulatory/licensing status is a live external prerequisite, not a static software assumption.
- The platform must preserve cash/COD as a capability where the operational market service supports it, while allowing regulated digital methods to be activated independently.

The Central Bank also reports ongoing work on RTGS/FPS infrastructure and interoperability, so the payment abstraction must remain extensible rather than assuming today's rails are the final national topology. cite-source:turn0search4turn0search9

These findings are research evidence only. They do not certify any provider, rail, credential, settlement path, or production integration.


## 8. Current regulatory architecture checkpoint — 2026-09-24

Current Central Bank of Yemen publications reinforce three implementation constraints:

- electronic-money and payment-system activity is subject to published regulatory instructions;
- the regulator maintains a current list of licensed banks and licensed exchange/remittance entities;
- 2026 regulatory work includes a national QR standard and interoperability work around electronic wallets, while the Central Bank has also published a prohibition on dealing with unlicensed electronic-payment entities/services. cite-source:turn0search0turn0search9turn0search10

Accordingly, Hussam's Phase 1 payment activation contract must carry at least:

- provider legal/regulatory status;
- supported capability and market;
- rail/standard identifier where applicable;
- contract/onboarding status;
- technical integration status;
- credential/test-environment status;
- settlement/reconciliation status;
- evidence artifact and review reference;
- activation/suspension timestamps.

A provider cannot become production-capable merely because it appears in a public marketplace study.

The current national payment direction also makes interoperability a first-class architectural requirement: the Central Bank describes the Unified Money Network as a key national payments component and is pursuing RTGS/FPS infrastructure and wallet interoperability. cite-source:turn0search5turn0search8turn0search10

This checkpoint is research/control guidance only; it does not activate any provider or payment rail.


## 9. BUILD execution checkpoint — checkout context slice (2026-09-24)

Completed on branch `feat/yemen-checkout-context`:

- Added `YemenCheckoutContextService` as an additive composition boundary.
- Exposes explicit market currency and money-unit presentation without performing FX conversion.
- Requires source/context for any future conversion and defaults automatic conversion to false.
- Exposes active market payment methods and derives COD availability from the market payment catalog.
- Resolves a buyer-owned, market-bound delivery address and reports geography coverage.
- Reuses existing seller shipping-rate and market-geography primitives to report delivery availability.
- Added deterministic SQLite tests for COD, currency presentation, address ownership and inactive-market rejection.
- Added client-safe API endpoint: `GET /platform/yemen/checkout-context/{market_code}`.

This slice does **not** execute payment, create orders, certify providers, calculate authoritative totals, or replace checkout. The existing marketplace domain remains authoritative for those operations.

The checkout route now resolves the same active-cart market used by the authoritative domain checkout before applying Yemen market/address/coverage validation. The buyer UI no longer sends client-supplied platform-fee policy data. Existing domain tests already cover server-owned shipping quotes and quote consumption; the next controlled slice is browser E2E against this contract, followed by explicit COD/payment behavior verification.


## 10. BUILD execution checkpoint — payment selection + COD fulfillment bridge (2026-09-24)

Completed and merged through controlled PRs:

- Checkout context was promoted from presentation-only context into an explicit payment-method selection boundary.
- `payment_method_code` is validated against the active market payment catalog at authoritative checkout.
- The selected method is persisted on the customer order and seller-facing marketplace order snapshot.
- COD is explicitly represented as a non-provider collection method; checkout does not fabricate a provider payment intent for COD.
- Buyer checkout now requires an explicit payment-method selection from the market runtime context.
- Browser E2E verifies Yemen checkout selection of COD.
- Fulfillment now carries the selected COD order total into the physical shipment as `cod_amount`.
- Existing logistics authority remains responsible for delivery-state transitions and COD collection.
- Focused end-to-end coverage verifies: COD selection → shipment COD amount → delivery → COD collection.
- Provider-backed payment execution remains behind the existing production gate and is not activated by this slice.

The controlled payment/fulfillment boundary is therefore now:

`Market Payment Catalog → Checkout Selection → Immutable Order Snapshot → Fulfillment Shipment COD Amount → Delivery → COD Collection`

No provider certification, live credentials, settlement integration, or external production evidence is implied by this checkpoint.

### Verification record

- PR #25: payment-method selection — CI green before merge.
- PR #26: COD fulfillment bridge — CI green before merge.
- Baseline audit: 0 failures / 0 warnings.
- Compileall: passed.
- Full pytest suite: passed on the PR head.
- Fresh SQLite migration: passed.
- Alembic schema drift: passed.
- PostgreSQL migration/schema/integration: passed.
- Container security scan: passed.

Next controlled capability slice: connectivity-aware mutation behavior, with special attention to offline drafts, explicit pending states, replay-safe idempotency, and prohibition of offline payment/ledger authority.


## 11. BUILD execution checkpoint — connectivity-safe checkout mutation (2026-09-24)

The next controlled connectivity slice is now implemented on branch `feat/yemen-connectivity-idempotency`:

- Checkout accepts an optional HTTP `Idempotency-Key`.
- The request hash is derived from the authenticated buyer identity plus the canonical checkout body; the same key cannot be reused for a different request.
- The existing `IdempotencyRecord` table is used as the persistence boundary; no new schema is required for this slice.
- Reservation and checkout order creation share one database transaction. A concurrent replay cannot create a second marketplace order.
- A replay after a committed checkout returns the original order IDs instead of executing checkout again.
- Failed first attempts release the reservation with the surrounding transaction, allowing a safe retry.
- The browser checkout stores a local draft only when the request cannot safely be sent; the draft is explicitly labeled as **not an order**.
- Offline checkout does not call the checkout API and therefore cannot create an order, payment intent, or ledger mutation.
- A failed online submission keeps the same idempotency key so a retry remains replay-safe if the first request actually reached the server.
- Browser E2E now verifies offline draft behavior, zero checkout calls while offline, and the presence of an idempotency key when connectivity returns.

The authoritative boundary is therefore:

`Offline UI draft → connectivity check → Idempotency-Key → server-authoritative checkout → immutable order snapshot`

This does not make payment, ledger posting, or provider execution available offline. It also does not certify any payment provider.

### Acceptance intent

The slice must remain fail-closed for:

1. duplicate idempotency keys with different request bodies;
2. duplicate order creation after browser/network retry;
3. offline API mutation;
4. offline payment/ledger authority;
5. client-supplied authoritative totals or fees.

The next controlled work after CI verification is conflict/sync proof for broader offline-capable mutations, followed by the remaining Yemen capabilities in the execution map.

## BUILD execution checkpoint — explicit mutation lifecycle + cart replay safety (2026-09-24)

The connectivity mutation foundation is now wired to a real non-financial Marketplace mutation.

- MutationRecord provides tenant/actor-scoped mutation keys, canonical request-hash binding, replay detection, and explicit DRAFT/PENDING/CONFIRMED/FAILED/CONFLICT lifecycle states.
- Migration 0036_mutation_records is baseline-safe: the canonical 0001 metadata bootstrap may already create the table, while genuinely incremental databases receive the table from 0036.
- Marketplace cart add/remove mutations accept Idempotency-Key and use the lifecycle service without moving domain authority out of MarketplaceService.
- A confirmed replay returns the stored cart result and does not apply the mutation twice.
- Reuse of the same mutation key with a different request is rejected.
- Payment, ledger, checkout authority, and provider operations remain outside the connectivity mutation lifecycle.
- PR #30 merged after full CI success.
- PR #31 merged after full CI success: baseline, PostgreSQL migration/schema-drift/integration, container security.
- The next controlled slice is synchronization/conflict evidence and UI lifecycle visibility, followed by Documents/Notifications and then Search/Pricing/CRM. Financial mutations remain server-authoritative and offline payment/ledger authority remains prohibited.

## 12. BUILD execution checkpoint — cart synchronization evidence (2026-09-24)

The connectivity slice now extends from server-side lifecycle primitives into the buyer UI without granting offline authority:

- Cart add/remove mutations generate an explicit `Idempotency-Key`.
- Online cart mutations send that key to the server lifecycle boundary.
- Offline cart mutations are stored as local drafts only; they are explicitly not server-confirmed state.
- On connectivity restoration, queued cart mutations are replayed using the same mutation key, allowing the server to return the existing result instead of double-applying the operation.
- The UI distinguishes pending local cart changes from confirmed server cart state.
- Durable `AuditRecord` entries are now written for mutation reservation, replay and lifecycle transition in the same database transaction boundary.
- Conflict handling remains explicit: a mutation key cannot be reused for a different request hash, and a conflict cannot silently move back to pending.
- Checkout/payment/ledger/provider authority remains server-side and is not included in the offline cart queue.

This closes the controlled cart synchronization loop:

`Offline-safe read → local mutation draft → Idempotency-Key → server reservation → domain mutation → CONFIRMED → audit evidence → replay-safe readback`

The next controlled slice is Documents + Notifications, followed by Search/Pricing/CRM, AI/HUS market-context verification, Developer Platform trusted-provenance hardening, Yemen E2E, and only then external G01–G10 evidence closure.


## 13. Controlled completion map — current engineering state (2026-09-24)

### Closed engineering slices

- Market runtime context and capability activation boundary.
- Yemen checkout context with explicit money, geography, payment and delivery context.
- Explicit payment-method selection and immutable order snapshot.
- COD fulfillment bridge through existing logistics authority.
- Connectivity-safe checkout with server-authoritative idempotency.
- Safe offline public-read cache.
- General mutation lifecycle with request-hash binding and explicit states.
- Replay-safe cart add/remove mutations.
- Mutation status/readback boundary.
- Offline cart mutation queue and replay using the same idempotency key.
- Durable audit evidence for reservation, replay and lifecycle transitions.
- Existing Documents, Notifications, Search, Pricing, CRM, AI/HUS and marketplace completion capabilities remain authoritative existing engines; Yemenization must wire their market context rather than duplicate them.

### Remaining engineering gates

1. Trusted CI provenance for Developer Platform test evidence.
2. Cross-capability Yemen E2E proving runtime behavior rather than configuration presence.
3. Production evidence collection for G01–G10.
4. Final release/baseline lock only after the preceding gates are independently satisfied.

### Non-negotiable authority boundaries

- Offline state is never financial authority.
- Client totals, FX, settlement, ledger posting and provider execution are never authoritative.
- Payment providers are not production-certified by public documentation alone.
- Developer-submitted test evidence is source-bound but must not be treated as trusted CI provenance until an independently verifiable CI artifact is bound to the source hash and run identity.
- Yemen capability configuration is control-plane data; domain behavior is executed by typed runtime/domain contracts.

### Current project status

**Engineering:** active and controlled; core architecture remains preserved.

**Yemenization Phase 1:** behavior wiring and verification in progress.

**Production certification:** not closed; G01–G10 require external evidence.

**Final lock:** intentionally deferred until evidence gates are closed.
