# BUILD Phase 1 — Yemenization Execution Map
## Controlled implementation map — 2026-09-24

**Status:** PRE-IMPLEMENTATION / NON-BLOCKING  
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

The Yemen layer should converge on these controlled capabilities:

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

## 4. Implementation order after certification lock

The implementation sequence is intentionally narrow:

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

The repository already contains most of the structural foundation required for BUILD Phase 1. The next work is therefore **not another foundation rewrite**. It is controlled evidence acquisition, source admission, capability activation and UX integration after the external certification boundary is satisfied.

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
