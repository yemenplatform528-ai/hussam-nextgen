# Yemen Marketplace — Product Core Engineering Lock

## Scope

This lock closes the market-scoped product core beneath the Yemen Marketplace:

`Catalog Group → Product → SKU → Offer → Listing → Inventory Availability → Publication → Discovery`

## Closed invariants

- Product, Offer, and Listing belong to an explicit Market.
- A seller may reuse the same Product slug, Offer/SKU identity, and Listing slug across different Markets without cross-market uniqueness collisions.
- Offer currency must be enabled in the Product/Offer Market.
- Category references must belong to the same Market when market-scoped.
- Product listings require a valid inventory item and warehouse for product-type listings.
- Managed offers require SKU inventory plus an active seller warehouse.
- Publication requires active seller + approved moderation; publication activates the linked offer/product.
- Public discovery is restricted to published + approved listings from active, verified sellers and is Market-scoped.
- Managed-stock discovery reports current available inventory and supports `in_stock` filtering.
- The atomic Product→SKU→Offer→Listing bundle now carries one Market context through the complete chain.

## Database lifecycle

Migration `0008_marketplace_catalog_market_uniqueness` closes market-scoped uniqueness for product/listing identifiers and offer/SKU identity. It is compatible with the model-driven baseline and supports SQLite batch migration plus PostgreSQL DDL.

## Verification

- Baseline audit: 0 failures / 0 warnings.
- Repository tests excluding browser E2E: 226 passed / 1 deselected.
- Browser E2E: 1 passed.
- Alembic upgrade/check: PASS.
- Alembic downgrade to 0007 and re-upgrade to 0008: PASS.
- Catalog market-scope regression test: PASS.

## Boundary

This lock does not claim live payment providers, national logistics coverage, AI, HUS Compiler, or external production evidence. Those remain later layers/gates.
