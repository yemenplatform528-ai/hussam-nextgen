# Y2 — Yemen Foundation

## Purpose

Y2 is the reusable market foundation for Yemen inside the unified Hussam NextGen platform. It is **not** a Yemen fork of Marketplace and it is **not** a second financial system.

The canonical repository baseline (`0001_initial_unified_platform`) is intentionally model-driven, so the Y2 tables are already present in the baseline schema. Revision `0005_y2_market_foundation` is therefore the **Y2 integrity-closure migration**: it is conditional and brings older baseline-compatible schemas to the same final integrity state without duplicating objects.

## Included

- Market context and lifecycle metadata
- Market currencies (`YER`, `USD`, `SAR`, `AED` for the Yemen market)
- Hierarchical geography: country → governorate → district → locality
- Market coverage
- Provider registry separated from provider rail/currency capability
- Market-scoped payment method catalog
- Marketplace address extension with structured geography, optional coordinates, confidence, and delivery instructions

## Integrity rules

### Database-enforced

- Market/currency uniqueness per market
- At most one `is_default` currency per market
- Valid market/geography/coverage foreign keys
- Coverage cannot point to a geography from another market
- Geography root/non-root parent shape
- Allowed geography levels and statuses
- Provider capability uniqueness
- Address coordinate bounds
- Address confidence values
- Address country-code shape
- Address structured geography must match its explicit `market_id` when both are supplied

### Application-lifecycle invariant

One rule intentionally remains above the relational layer because it spans independent lifecycle rows and must remain portable across SQLite/PostgreSQL without triggers:

1. `MarketContext.default_currency` must correspond to an enabled `MarketCurrency` before a market becomes operational.

The Marketplace/market administration service is responsible for enforcing this transition. The Foundation does not introduce database triggers or provider-specific execution logic merely to force it into the schema.

Geography parent market membership is database-enforced by the composite self-foreign-key `fk_market_geography_parent_market`; this prevents a child geography from referencing a parent belonging to another market.

## Provider semantics

`rail` and `currency` on `ProviderMarketCapability` are non-null. An empty string means the capability is not restricted to a particular rail/currency. This avoids SQL `NULL` uniqueness differences between database engines.

## Address semantics

The legacy text fields remain authoritative for backward compatibility. Structured fields are additive. Coordinates are optional and constrained to valid latitude/longitude ranges. Structured geography is market-aware when `market_id` is supplied.

## Explicit non-goals

- No Yemen marketplace fork
- No `YER_OLD` / `YER_NEW`
- No hard-coded national FX rate
- No wallet, bank, QR, ACH, FPS, card or payment-rail implementation
- No live provider credentials or production integrations
- No payment router
- No logistics router
- No COD settlement
- No AI work
- No HUS Compiler work
- No national Yemen geography dataset claim

## Acceptance

Y2 is engineering-locked only when:

1. Model metadata and migration schema agree.
2. SQLite tests pass with foreign-key enforcement enabled.
3. `upgrade → check → downgrade → upgrade → check` passes.
4. PostgreSQL DDL compiles successfully for every Y2 table/index/constraint.
5. Cross-market, uniqueness, address, and hierarchy negative cases are tested.
6. No G01–G10 production-closure scope is reopened.
7. Production external evidence remains a separate gate and is not falsely claimed by this foundation artifact.
