# BUILD Phase 1 — Yemenization Gap Assessment
## 2026-09-24

Status: IMPLEMENTATION BASELINE / CODE-REVIEWED

This assessment was produced from the current repository implementation after the Yemenization product contract was approved.

## 1. What already exists

The Marketplace implementation already contains most of the commerce journey:
- public product/listing discovery
- categories and seller discovery
- seller catalog/product/SKU/offer management
- buyer addresses
- cart
- checkout
- customer orders
- payment-session/payment-intent hooks
- seller order lifecycle
- fulfillment and shipment primitives
- shipping-rate and shipping-quote primitives
- COD-compatible order/payment lifecycle through the existing payment abstraction
- returns and disputes
- seller payout and settlement primitives
- reviews
- marketplace fees
- market-aware listing/category/catalog fields
- geography-aware buyer address fields including governorate, district and locality IDs

The existing app/core/models/market.py also provides market, geography, currency, money-unit, FX, provider, payment-rail, adapter, readiness-evidence and payment-method catalog primitives.

## 2. What Phase 1 actually needs

The project does NOT need another marketplace rewrite.

The remaining work is localization and integration around the existing journey:

### P1 — Yemen market activation data contract
Connect the existing MarketContext to a Yemen market profile without hard-coding Yemen behavior into generic services.

### P2 — Currency presentation
Add a single UI/API contract for explicit currency labels and money-unit presentation. Conversion must always carry source/context.

### P3 — Geography-first checkout
Use the existing governorate/district/locality fields consistently in discovery, seller service areas, addresses and shipping quotes.

### P4 — COD/payment-choice UX
Expose payment methods as checkout choices. COD must be first-class where the seller/service configuration supports it. External wallet/transfer methods remain optional.

### P5 — Delivery coverage
Connect seller/service-area coverage to existing MarketCoverage/geography primitives. Do not create a parallel carrier model.

### P6 — Connectivity behavior
Harden catalog, cart and order UX against intermittent connectivity. Order/payment submission must remain idempotent and visibly stateful.

### P7 — Yemen release surface
Create the Yemen-first API/UI presentation layer only after the contracts above are covered by tests.

## 3. Important implementation finding

The existing code already separates commerce order state, payment intent/session state, fulfillment state, provider identity, payout/settlement, and market context.

Therefore we should extend these boundaries instead of merging them.

The correct implementation is additive and adapter-based.

## 4. No unnecessary blockers

The following are NOT prerequisites for beginning the product build:
- a new wallet inside Hussam
- a new banking subsystem
- a national payment network
- a second accounting core
- a second logistics engine
- a Yemen-only runtime fork
- replacing the existing Marketplace
- forcing every buyer to use electronic payment

## 5. First implementation slice

The first code slice should be the smallest reusable Yemen commerce contract:
1. market-aware checkout context;
2. explicit currency/money-unit presentation;
3. payment-method availability including COD;
4. geography/service-area availability;
5. deterministic response fields for buyer UI.

No external provider credentials are required for this slice.

## 6. Acceptance criteria

A Yemen buyer-facing checkout response must be able to communicate:
- market;
- currency;
- seller;
- delivery destination;
- available delivery mode;
- available payment methods;
- COD availability;
- payment-required state;
- total with explicit currency.

A seller-facing configuration must be able to communicate:
- served geography;
- supported currency;
- accepted payment methods;
- delivery mode;
- order availability.

## 7. Safety rule

This is a product implementation assessment, not a production certification record.

It does not certify providers, payment rails, carriers, legal status, or production readiness.

It does not require changing the canonical Marketplace, AI or HUS architecture.

## Decision

Proceed with an additive Yemenization slice. Do not rewrite the Marketplace.