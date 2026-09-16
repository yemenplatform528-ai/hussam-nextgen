# Hussam NextGen Unified Platform — First Release Gate

This repository is one unified platform. The `1.0` label identifies the intended
first real product release; it is **not** a claim that the platform has already
launched.

The system will be considered released only when the complete capability map,
transactional invariants, security controls, integrations, operational tooling,
end-to-end tests, and external production gates are evidenced.

## Product boundary
- One platform, one codebase, one Sovereign Core.
- Marketplace, Retail, AI and HUS are capabilities over shared authorities.
- No historical milestone/version is a runtime product boundary.
- Yemen-specific behavior will be added through market configuration/adapters
  after the global capability model is complete.

## Required release gates
- Complete customer and seller journeys.
- Catalog, offers, pricing, checkout, orders and fulfillment.
- Payments, fees, settlement, refunds and reconciliation.
- Returns, reviews, disputes, customer service and seller health.
- Warehouses, transfers, pickup, service areas, tracking and delivery.
- Promotions, brands, advertising, B2B, bundles and subscriptions.
- Reports, notifications, bulk operations and integration APIs.
- AI/HUS governance with no authority bypass.
- Real identity/OIDC, production PostgreSQL, certified payment rails/webhooks,
  backups/restore, observability, browser/mobile E2E, security assessment,
  operational runbooks and real logistics/accounting integration.
