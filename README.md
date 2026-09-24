# Hussam NextGen Unified Platform

Hussam NextGen is one unified commerce platform designed to reach Amazon-class
marketplace capability while keeping Hussam's own Sovereign Core and domain
boundaries.

## Architecture

`Clients → API → Identity/Tenant Context → Domain Services → Shared Engines → Sovereign Core → Persistence`

The platform contains Marketplace, Retail, Growth, Network, AI and HUS
capabilities in one coherent system. Finance, Inventory, Payments, Logistics,
Identity, Policy and Audit remain authoritative shared services.

## Product goal

A unified customer marketplace with multi-seller offers, Featured Offer,
checkout, payments, orders, fulfillment, delivery, returns/refunds, reviews and
customer service, plus a full Seller Center and network operations.

## Engineering rule

This repository is developed as one continuous platform. The `1.0` label is reserved
for the first real product release after the complete capability and production gates
are satisfied. Yemenization is a governed compatibility layer over the shared engines,
not a parallel Yemen-only implementation.

## Current BUILD Phase 1

The active engineering path composes the Yemen market runtime across the existing
authorities for money, geography, payments, logistics, documents, notifications,
AI/HUS, reporting and governed Developer Platform capabilities. It preserves the
shared domain engines and adds provider-neutral local behavior through market
configuration and adapters.

See:
- `docs/PLATFORM_BLUEPRINT.md`
- `docs/CAPABILITY_MAP.md`
- `docs/PRODUCTION_GATES.md`
- `RELEASE_1_0.md`
